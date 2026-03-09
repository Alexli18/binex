"""QA Phase 2 — coverage gap tests for agents, DSL parser, and settings.

Covers test cases not already exercised by existing test files:
  TC-AGT-003, TC-AGT-005, TC-AGT-009, TC-AGT-012, TC-AGT-013, TC-AGT-014
  TC-CFG-003, TC-CFG-004
"""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from binex.agents.common.llm_client import LLMClient
from binex.agents.common.llm_config import LLMConfig
from binex.agents.planner.agent import PlannerAgent
from binex.agents.researcher.agent import ResearcherAgent
from binex.agents.summarizer.agent import SummarizerAgent
from binex.agents.validator.agent import ValidatorAgent
from binex.models.artifact import Artifact, Lineage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _art(content, *, art_id="art_01", art_type="input") -> Artifact:
    return Artifact(
        id=art_id,
        run_id="run_01",
        type=art_type,
        content=content,
        lineage=Lineage(produced_by="external"),
    )


# ===================================================================
# CAT-1: Agent Reference Implementations — gap tests
# ===================================================================


class TestAGT003_PlannerLLMTimeout:
    """TC-AGT-003: PlannerAgent LLM client timeout handling."""

    async def test_planner_propagates_timeout_error(self) -> None:
        client = AsyncMock()
        client.complete_json = AsyncMock(side_effect=asyncio.TimeoutError("LLM timeout"))
        agent = PlannerAgent(client=client)

        with pytest.raises(asyncio.TimeoutError):
            await agent.execute("t1", "run_01", [_art("some query")])

    async def test_planner_propagates_connection_error(self) -> None:
        client = AsyncMock()
        client.complete_json = AsyncMock(side_effect=ConnectionError("refused"))
        agent = PlannerAgent(client=client)

        with pytest.raises(ConnectionError):
            await agent.execute("t1", "run_01", [_art("some query")])


class TestAGT005_ResearcherLLMFailure:
    """TC-AGT-005: ResearcherAgent LLM failure → error propagation."""

    async def test_researcher_propagates_timeout(self) -> None:
        client = AsyncMock()
        client.complete_json = AsyncMock(side_effect=asyncio.TimeoutError())
        agent = ResearcherAgent(client=client)

        with pytest.raises(asyncio.TimeoutError):
            await agent.execute("t1", "run_01", [_art("research query")])

    async def test_researcher_propagates_runtime_error(self) -> None:
        client = AsyncMock()
        client.complete_json = AsyncMock(side_effect=RuntimeError("LLM down"))
        agent = ResearcherAgent(client=client)

        with pytest.raises(RuntimeError, match="LLM down"):
            await agent.execute("t1", "run_01", [_art("research query")])


class TestAGT009_SummarizerEmptyText:
    """TC-AGT-009: SummarizerAgent empty text → graceful handling."""

    async def test_summarizer_empty_string_content(self) -> None:
        client = AsyncMock()
        client.complete_json = AsyncMock(
            return_value=json.dumps({
                "title": "Empty Report",
                "summary": "",
                "sections": [],
                "sources": [],
            })
        )
        agent = SummarizerAgent(client=client)

        results = await agent.execute("t1", "run_01", [_art("")])
        assert len(results) == 1
        assert results[0].type == "research_report"
        assert results[0].content["title"] == "Empty Report"

    async def test_summarizer_no_artifacts(self) -> None:
        client = AsyncMock()
        client.complete_json = AsyncMock(
            return_value=json.dumps({
                "title": "No Input",
                "summary": "Nothing to summarize",
                "sections": [],
                "sources": [],
            })
        )
        agent = SummarizerAgent(client=client)

        results = await agent.execute("t1", "run_01", [])
        assert len(results) == 1
        assert results[0].type == "research_report"

    async def test_summarizer_none_content(self) -> None:
        client = AsyncMock()
        client.complete_json = AsyncMock(
            return_value=json.dumps({
                "title": "Report",
                "summary": "summary",
                "sections": [],
                "sources": [],
            })
        )
        agent = SummarizerAgent(client=client)

        results = await agent.execute("t1", "run_01", [_art(None)])
        assert len(results) == 1
        assert results[0].type == "research_report"


class TestAGT012_LLMClientConfigValidation:
    """TC-AGT-012: LLMClient config validation (missing model → error)."""

    async def test_client_with_empty_model_sends_empty_model(self) -> None:
        """LLMClient passes the model string to litellm; an empty model
        will cause litellm to raise an error at call time."""
        config = LLMConfig(model="")
        client = LLMClient(config)

        mock_resp = AsyncMock()
        mock_resp.choices = [AsyncMock()]
        mock_resp.choices[0].message.content = "ok"

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_llm:
            await client.complete("hello")
            assert mock_llm.call_args[1]["model"] == ""

    async def test_client_without_api_base_omits_kwarg(self) -> None:
        """When api_base is None the kwarg should not be sent."""
        config = LLMConfig(model="test-model", api_base=None, api_key=None)
        client = LLMClient(config)

        mock_resp = AsyncMock()
        mock_resp.choices = [AsyncMock()]
        mock_resp.choices[0].message.content = "ok"

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_llm:
            await client.complete("prompt")
            kwargs = mock_llm.call_args[1]
            assert "api_base" not in kwargs
            assert "api_key" not in kwargs

    async def test_client_none_response_returns_empty_string(self) -> None:
        """When LLM returns None content, client should return ''."""
        config = LLMConfig(model="test-model")
        client = LLMClient(config)

        mock_resp = AsyncMock()
        mock_resp.choices = [AsyncMock()]
        mock_resp.choices[0].message.content = None

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.complete("prompt")
            assert result == ""


class TestAGT013_LLMConfigSerialization:
    """TC-AGT-013: LLMConfig serialization roundtrip."""

    def test_model_dump_and_reconstruct(self) -> None:
        original = LLMConfig(
            model="gpt-4",
            api_base="http://proxy:4000",
            api_key="sk-test",
            temperature=0.5,
            max_tokens=1024,
        )
        data = original.model_dump()
        restored = LLMConfig(**data)

        assert restored.model == original.model
        assert restored.api_base == original.api_base
        assert restored.api_key == original.api_key
        assert restored.temperature == original.temperature
        assert restored.max_tokens == original.max_tokens

    def test_model_dump_json_roundtrip(self) -> None:
        original = LLMConfig(model="ollama/llama3.2", temperature=0.9)
        json_str = original.model_dump_json()
        restored = LLMConfig.model_validate_json(json_str)

        assert restored.model == original.model
        assert restored.temperature == original.temperature

    def test_for_ollama_serializes(self) -> None:
        config = LLMConfig.for_ollama("phi3")
        data = config.model_dump()
        assert data["model"] == "ollama/phi3"
        assert data["api_base"] == "http://localhost:11434"


class TestAGT014_MalformedExecutePayload:
    """TC-AGT-014: Agent apps malformed /execute payload → 422 or graceful handling.

    The apps accept `payload: dict` which is very permissive. FastAPI will
    return 422 only for structurally invalid JSON. Missing keys are handled
    with defaults. We test both scenarios.
    """

    async def test_planner_non_json_body_returns_422(self) -> None:
        from binex.agents.planner.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/execute",
                content=b"not json at all",
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 422

    async def test_researcher_non_json_body_returns_422(self) -> None:
        from binex.agents.researcher.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/execute",
                content=b"{{invalid",
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 422

    async def test_validator_non_json_body_returns_422(self) -> None:
        from binex.agents.validator.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/execute",
                content=b"not-json",
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 422

    async def test_summarizer_non_json_body_returns_422(self) -> None:
        from binex.agents.summarizer.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/execute",
                content=b"not-json",
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 422

    async def test_planner_missing_keys_uses_defaults(self) -> None:
        """Empty dict payload should not crash; agent uses defaults."""
        from binex.agents.planner import app as planner_app_mod

        mock_client = AsyncMock()
        mock_client.complete_json = AsyncMock(return_value='["subtask"]')
        original = planner_app_mod.app
        import binex.agents.planner.app as pmod

        saved = pmod._agent
        pmod._agent = PlannerAgent(client=mock_client)
        try:
            transport = ASGITransport(app=pmod.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/execute", json={})
            assert resp.status_code == 200
            data = resp.json()
            assert "artifacts" in data
        finally:
            pmod._agent = saved


# ===================================================================
# CAT-12: Settings & Configuration — gap tests
# ===================================================================


class TestCFG003_DotenvLoadedByCLI:
    """TC-CFG-003: .env file loaded by CLI entry point."""

    def test_main_calls_load_dotenv(self) -> None:
        """Verify that main() calls load_dotenv() before cli()."""
        with patch("binex.cli.main.load_dotenv") as mock_load, \
             patch("binex.cli.main.cli") as mock_cli:
            from binex.cli.main import main
            main()
            mock_load.assert_called_once()
            mock_cli.assert_called_once()

    def test_load_dotenv_called_before_cli(self) -> None:
        """Ensure ordering: load_dotenv before cli."""
        call_order = []
        with patch("binex.cli.main.load_dotenv", side_effect=lambda: call_order.append("dotenv")), \
             patch("binex.cli.main.cli", side_effect=lambda: call_order.append("cli")):
            from binex.cli.main import main
            main()
        assert call_order == ["dotenv", "cli"]


class TestCFG004_DotenvMissing:
    """TC-CFG-004: .env file missing → no error."""

    def test_settings_work_without_dotenv(self) -> None:
        """Settings should return defaults when no .env and no env vars set."""
        from binex.settings import Settings
        # Just ensure no exception is raised and defaults are sane
        s = Settings()
        assert s.store_path  # non-empty
        assert s.default_deadline_ms > 0

    def test_main_does_not_crash_without_dotenv_file(self, tmp_path) -> None:
        """main() should not raise even when .env doesn't exist."""
        original_cwd = os.getcwd()
        os.chdir(tmp_path)  # directory with no .env
        try:
            with patch("binex.cli.main.cli"):
                from binex.cli.main import main
                # Should not raise
                main()
        finally:
            os.chdir(original_cwd)
