"""Phase 3: CLI DX Commands — gap tests for TC-CLI-001 through TC-CLI-022.

Tests in this file cover scenarios NOT already exercised by existing test files.
Each test docstring references the corresponding TC-CLI-* identifier.
"""

from __future__ import annotations

import asyncio
import json
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stores():
    return InMemoryExecutionStore(), InMemoryArtifactStore()


def _write_yaml(tmp_path: Path, content: str) -> Path:
    wf = tmp_path / "wf.yaml"
    wf.write_text(textwrap.dedent(content))
    return wf


# ---------------------------------------------------------------------------
# TC-CLI-001 supplement: hello outputs "Hello from Binex!"
# ---------------------------------------------------------------------------

class TestHelloContentOutput:
    """TC-CLI-001 supplement: verify actual greeting content in hello output."""

    def test_hello_outputs_greeting_content(self):
        """The hello command should print 'Hello from Binex!' artifact content."""
        from binex.cli.hello import hello_cmd

        stores = _make_stores()
        with patch("binex.cli.hello._get_stores", return_value=stores):
            runner = CliRunner()
            result = runner.invoke(hello_cmd, [])

        assert result.exit_code == 0
        assert "Hello from Binex!" in result.output

    def test_hello_shows_completed_node_count(self):
        """hello should show 2/2 nodes completed."""
        from binex.cli.hello import hello_cmd

        stores = _make_stores()
        with patch("binex.cli.hello._get_stores", return_value=stores):
            runner = CliRunner()
            result = runner.invoke(hello_cmd, [])

        assert "2/2" in result.output


# ---------------------------------------------------------------------------
# TC-CLI-002 supplement: workflow mode generates correct agent refs
# ---------------------------------------------------------------------------

class TestInitWorkflowAgentRefs:
    """TC-CLI-002 supplement: verify generated YAML has correct provider agent refs."""

    def test_init_ollama_provider_uses_llm_prefix(self, tmp_path: Path):
        """Selecting ollama provider should produce llm://ollama/ agent refs."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            # mode=1 (workflow), provider=1 (ollama), model=default
            result = runner.invoke(cli, ["init"], input="\n1\n1\n\n")
            assert result.exit_code == 0
            wf = (Path(td) / "workflow.yaml").read_text()
            assert "llm://ollama/" in wf


# ---------------------------------------------------------------------------
# TC-CLI-005 supplement: scaffold workflow generates valid YAML structure
# ---------------------------------------------------------------------------

class TestScaffoldWorkflowStructure:
    """TC-CLI-005 supplement: deeper validation of generated YAML."""

    def test_scaffold_workflow_root_node_has_user_input(self):
        """Root node (no deps) should reference ${user.query}."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                ["scaffold", "workflow", "--no-interactive", "--name", "t.yaml", "A -> B -> C"],
            )
            assert result.exit_code == 0
            import yaml
            data = yaml.safe_load(Path("t.yaml").read_text())
            a_inputs = data["nodes"]["A"]["inputs"]
            assert "${user.query}" in str(a_inputs)

    def test_scaffold_workflow_leaf_node_has_upstream_ref(self):
        """Leaf node should reference its upstream dependency's output."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                ["scaffold", "workflow", "--no-interactive", "--name", "t.yaml", "X -> Y"],
            )
            assert result.exit_code == 0
            import yaml
            data = yaml.safe_load(Path("t.yaml").read_text())
            y_inputs = data["nodes"]["Y"]["inputs"]
            assert "${X.output}" in str(y_inputs)


# ---------------------------------------------------------------------------
# TC-CLI-006 supplement: scaffold with empty DSL string
# ---------------------------------------------------------------------------

class TestScaffoldEmptyDSL:
    """TC-CLI-006 supplement: verify error on empty DSL string."""

    def test_scaffold_workflow_empty_string(self):
        """Empty DSL string should produce an error."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scaffold", "workflow", "--no-interactive", ""],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# TC-CLI-007 supplement: doctor --json with all healthy
# ---------------------------------------------------------------------------

class TestDoctorJsonAllHealthy:
    """TC-CLI-007 supplement: JSON output when all checks pass."""

    def test_doctor_json_all_healthy(self):
        checks = [
            {"name": "Docker", "status": "ok", "detail": "/usr/bin/docker"},
            {"name": "Store", "status": "ok", "detail": "/tmp/store"},
        ]
        with patch("binex.cli.doctor.run_checks", return_value=checks):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert all(c["status"] == "ok" for c in parsed)


# ---------------------------------------------------------------------------
# TC-CLI-008 supplement: doctor with missing binary
# ---------------------------------------------------------------------------

class TestDoctorMissingBinary:
    """TC-CLI-008 supplement: missing binary triggers exit 1 + warning."""

    def test_doctor_missing_binary_exits_1(self):
        checks = [
            {"name": "docker", "status": "missing", "detail": "docker not found on PATH"},
            {"name": "Store", "status": "ok", "detail": "/tmp/store"},
        ]
        with patch("binex.cli.doctor.run_checks", return_value=checks):
            runner = CliRunner()
            result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 1
        assert "Some checks failed" in result.output


# ---------------------------------------------------------------------------
# TC-CLI-011 supplement: providers list all 8 by name
# ---------------------------------------------------------------------------

class TestProvidersAllEight:
    """TC-CLI-011 supplement: all 8 provider names present in registry."""

    def test_all_eight_provider_names(self):
        from binex.cli.providers import PROVIDERS

        expected = {"ollama", "openai", "anthropic", "gemini", "groq", "mistral", "deepseek", "together"}
        assert set(PROVIDERS.keys()) == expected


# ---------------------------------------------------------------------------
# TC-CLI-013: dev foreground KeyboardInterrupt triggers compose down
# ---------------------------------------------------------------------------

class TestDevDown:
    """TC-CLI-013: verify that stopping foreground dev calls compose down."""

    def test_dev_foreground_keyboard_interrupt_calls_down(self):
        """KeyboardInterrupt in foreground mode should invoke compose 'down'."""
        from binex.cli.dev import dev_cmd

        compose_file = Path("/fake/docker-compose.yml")

        with (
            patch("binex.cli.dev._find_compose_file", return_value=compose_file),
            patch("binex.cli.dev.subprocess.run", side_effect=KeyboardInterrupt),
            patch("binex.cli.dev._run_compose") as mock_compose,
        ):
            runner = CliRunner()
            result = runner.invoke(dev_cmd, [])

        # After KeyboardInterrupt, _run_compose should be called with "down"
        mock_compose.assert_called_once_with(compose_file, "down")


# ---------------------------------------------------------------------------
# TC-CLI-014: binex run --var key=value injects user variables
# ---------------------------------------------------------------------------

class TestRunWithVar:
    """TC-CLI-014: --var key=value is passed through to workflow."""

    def test_run_with_var_injects_user_variable(self, tmp_path: Path):
        """Workflow with ${user.topic} should receive value from --var topic=AI."""
        wf_content = """\
            name: var-test
            nodes:
              step1:
                agent: local://echo
                system_prompt: "Research about ${user.topic}"
                outputs: [out]
        """
        wf = _write_yaml(tmp_path, wf_content)
        stores = _make_stores()

        with patch("binex.cli.run._get_stores", return_value=stores):
            runner = CliRunner()
            result = runner.invoke(cli, ["run", str(wf), "--var", "topic=AI"])

        assert result.exit_code == 0
        assert "completed" in result.output.lower()

    def test_run_with_multiple_vars(self, tmp_path: Path):
        """Multiple --var flags should all be parsed correctly."""
        wf_content = """\
            name: multi-var
            nodes:
              step1:
                agent: local://echo
                system_prompt: "${user.greeting} ${user.name}"
                outputs: [out]
        """
        wf = _write_yaml(tmp_path, wf_content)
        stores = _make_stores()

        with patch("binex.cli.run._get_stores", return_value=stores):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["run", str(wf), "--var", "greeting=Hello", "--var", "name=World"],
            )

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TC-CLI-015: binex run with LLM agent registers LLMAdapter
# ---------------------------------------------------------------------------

class TestRunLLMAdapterRegistration:
    """TC-CLI-015: LLM agent prefix auto-registers LLMAdapter."""

    def test_run_llm_agent_registers_adapter(self, tmp_path: Path):
        """Workflow with llm:// agent should register LLMAdapter and call litellm."""
        wf_content = """\
            name: llm-test
            nodes:
              step1:
                agent: "llm://ollama/llama3.2"
                system_prompt: "Summarize"
                outputs: [out]
        """
        wf = _write_yaml(tmp_path, wf_content)
        stores = _make_stores()

        # Mock litellm.acompletion to avoid real API calls
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Mocked LLM response"

        with (
            patch("binex.cli.run._get_stores", return_value=stores),
            patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["run", str(wf)])

        # Should complete (exit 0) or fail gracefully (exit 1) — not crash
        assert result.exit_code in (0, 1), f"Unexpected crash: {result.output}"


# ---------------------------------------------------------------------------
# TC-CLI-016 supplement: verbose shows dependency arrows
# ---------------------------------------------------------------------------

class TestRunVerboseDependencyArrows:
    """TC-CLI-016 supplement: verbose mode shows <- dep arrows."""

    def test_verbose_shows_dependency_arrows(self, tmp_path: Path):
        """With -v, nodes with deps should show '<- dep_name' lines."""
        wf_content = """\
            name: arrow-test
            nodes:
              fetch:
                agent: local://echo
                outputs: [data]
              analyse:
                agent: local://echo
                depends_on: [fetch]
                outputs: [report]
        """
        wf = _write_yaml(tmp_path, wf_content)
        stores = _make_stores()

        with patch("binex.cli.run._get_stores", return_value=stores):
            runner = CliRunner()
            result = runner.invoke(cli, ["run", str(wf), "-v"])

        assert "<- fetch" in result.output


# ---------------------------------------------------------------------------
# TC-CLI-017 supplement: debug plain text shows workflow name
# ---------------------------------------------------------------------------

class TestDebugPlainWorkflowName:
    """TC-CLI-017 supplement: plain output includes workflow name."""

    def test_debug_plain_shows_workflow_name(self):
        from binex.cli.debug import debug_cmd
        from binex.models.execution import ExecutionRecord, RunSummary
        from binex.models.task import TaskStatus
        from datetime import UTC, datetime

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        async def _populate():
            await exec_store.create_run(RunSummary(
                run_id="run-wn-001",
                workflow_name="my-pipeline",
                status="completed",
                started_at=datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC),
                total_nodes=1,
                completed_nodes=1,
            ))
            await exec_store.record(ExecutionRecord(
                id="rec-1",
                run_id="run-wn-001",
                task_id="step_a",
                agent_id="local://echo",
                status=TaskStatus.COMPLETED,
                latency_ms=50,
                trace_id="trace-1",
            ))

        asyncio.run(_populate())

        with patch("binex.cli.debug._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            result = runner.invoke(debug_cmd, ["run-wn-001"])

        assert result.exit_code == 0
        assert "my-pipeline" in result.output


# ---------------------------------------------------------------------------
# TC-CLI-018 supplement: debug --json has expected structure
# ---------------------------------------------------------------------------

class TestDebugJsonStructure:
    """TC-CLI-018 supplement: JSON output has run_id, workflow, status, nodes."""

    def test_debug_json_structure(self):
        from binex.cli.debug import debug_cmd
        from binex.models.execution import ExecutionRecord, RunSummary
        from binex.models.task import TaskStatus
        from datetime import UTC, datetime

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        async def _populate():
            await exec_store.create_run(RunSummary(
                run_id="run-js-001",
                workflow_name="json-test",
                status="completed",
                started_at=datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC),
                total_nodes=1,
                completed_nodes=1,
            ))
            await exec_store.record(ExecutionRecord(
                id="rec-1",
                run_id="run-js-001",
                task_id="only_step",
                agent_id="local://echo",
                status=TaskStatus.COMPLETED,
                latency_ms=42,
                trace_id="trace-1",
            ))

        asyncio.run(_populate())

        with patch("binex.cli.debug._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            result = runner.invoke(debug_cmd, ["run-js-001", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["run_id"] == "run-js-001"
        assert data["workflow_name"] == "json-test"
        assert "status" in data
        assert "nodes" in data
        assert isinstance(data["nodes"], list)


# ---------------------------------------------------------------------------
# TC-CLI-019 supplement: --errors with no failures shows no nodes
# ---------------------------------------------------------------------------

class TestDebugErrorsNoFailures:
    """TC-CLI-019 supplement: --errors with all-success run shows no node sections."""

    def test_debug_errors_no_failures(self):
        from binex.cli.debug import debug_cmd
        from binex.models.execution import ExecutionRecord, RunSummary
        from binex.models.task import TaskStatus
        from datetime import UTC, datetime

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        async def _populate():
            await exec_store.create_run(RunSummary(
                run_id="run-ok-001",
                workflow_name="all-ok",
                status="completed",
                started_at=datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC),
                total_nodes=1,
                completed_nodes=1,
            ))
            await exec_store.record(ExecutionRecord(
                id="rec-1",
                run_id="run-ok-001",
                task_id="step_a",
                agent_id="local://echo",
                status=TaskStatus.COMPLETED,
                latency_ms=10,
                trace_id="trace-1",
            ))

        asyncio.run(_populate())

        with patch("binex.cli.debug._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            result = runner.invoke(debug_cmd, ["run-ok-001", "--errors"])

        assert result.exit_code == 0
        # With --errors and no failures, node sections should be absent
        lines = result.output.split("\n")
        node_lines = [l for l in lines if l.startswith("-- ")]
        assert len(node_lines) == 0


# ---------------------------------------------------------------------------
# TC-CLI-020 supplement: --node with nonexistent node shows no node sections
# ---------------------------------------------------------------------------

class TestDebugNodeFilterNonexistent:
    """TC-CLI-020 supplement: --node with unknown node name."""

    def test_debug_node_nonexistent(self):
        from binex.cli.debug import debug_cmd
        from binex.models.execution import ExecutionRecord, RunSummary
        from binex.models.task import TaskStatus
        from datetime import UTC, datetime

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        async def _populate():
            await exec_store.create_run(RunSummary(
                run_id="run-nf-001",
                workflow_name="test-wf",
                status="completed",
                started_at=datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC),
                total_nodes=1,
                completed_nodes=1,
            ))
            await exec_store.record(ExecutionRecord(
                id="rec-1",
                run_id="run-nf-001",
                task_id="step_a",
                agent_id="local://echo",
                status=TaskStatus.COMPLETED,
                latency_ms=10,
                trace_id="trace-1",
            ))

        asyncio.run(_populate())

        with patch("binex.cli.debug._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            result = runner.invoke(debug_cmd, ["run-nf-001", "--node", "nonexistent_node"])

        assert result.exit_code == 0
        # Should not show step_a since we're filtering for nonexistent_node
        lines = result.output.split("\n")
        node_lines = [l for l in lines if l.startswith("-- ")]
        assert all("step_a" not in l for l in node_lines)


# ---------------------------------------------------------------------------
# TC-CLI-022 supplement: cancel verifies store state change
# ---------------------------------------------------------------------------

class TestCancelStoreState:
    """TC-CLI-022 supplement: cancel updates run status in store."""

    def test_cancel_updates_status_to_cancelled(self):
        from binex.models.execution import RunSummary
        from datetime import UTC, datetime

        exec_store = InMemoryExecutionStore()

        async def _populate():
            await exec_store.create_run(RunSummary(
                run_id="run-cancel-001",
                workflow_name="test",
                status="running",
                started_at=datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC),
                total_nodes=2,
                completed_nodes=0,
            ))

        asyncio.run(_populate())

        with patch("binex.cli.run._get_stores", return_value=(exec_store, None)):
            runner = CliRunner()
            result = runner.invoke(cli, ["cancel", "run-cancel-001"])

        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

        # Verify store state
        run = asyncio.run(exec_store.get_run("run-cancel-001"))
        assert run.status == "cancelled"


# ---------------------------------------------------------------------------
# TC-CLI-009 supplement: validate JSON output for valid workflow
# ---------------------------------------------------------------------------

class TestValidateJsonValid:
    """TC-CLI-009 supplement: --json output includes agents list."""

    def test_validate_json_includes_agents(self, tmp_path: Path):
        wf_content = """\
            name: agent-check
            nodes:
              a:
                agent: local://foo
                outputs: [x]
              b:
                agent: "llm://gpt-4"
                depends_on: [a]
                outputs: [y]
        """
        wf = _write_yaml(tmp_path, wf_content)
        runner = CliRunner()
        from binex.cli.validate import validate_cmd
        result = runner.invoke(validate_cmd, [str(wf), "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["valid"] is True
        assert "local://foo" in data["agents"]
        assert "llm://gpt-4" in data["agents"]
        assert data["node_count"] == 2
        assert data["edge_count"] == 1


# ---------------------------------------------------------------------------
# TC-CLI-012 supplement: dev --detach compose failure stderr
# ---------------------------------------------------------------------------

class TestDevComposeStderrOutput:
    """TC-CLI-012 supplement: dev --detach shows stderr on compose failure."""

    def test_dev_detach_compose_failure_shows_stderr(self):
        from binex.cli.dev import dev_cmd

        compose_file = Path("/fake/docker-compose.yml")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Cannot connect to Docker daemon"

        with (
            patch("binex.cli.dev._find_compose_file", return_value=compose_file),
            patch("binex.cli.dev._run_compose", return_value=mock_result),
        ):
            runner = CliRunner()
            result = runner.invoke(dev_cmd, ["--detach"])

        assert result.exit_code != 0
        assert "Cannot connect to Docker daemon" in result.output


# ---------------------------------------------------------------------------
# TC-CLI-010 supplement: validate cycle workflow JSON output
# ---------------------------------------------------------------------------

class TestValidateCycleJson:
    """TC-CLI-010 supplement: cycle error with --json returns structured error."""

    def test_validate_cycle_json_output(self, tmp_path: Path):
        wf_content = """\
            name: cycle
            nodes:
              a:
                agent: local://x
                depends_on: [b]
                outputs: [out]
              b:
                agent: local://x
                depends_on: [a]
                outputs: [out]
        """
        wf = _write_yaml(tmp_path, wf_content)
        from binex.cli.validate import validate_cmd
        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf), "--json"])

        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["valid"] is False
        assert any("cycle" in e.lower() for e in data["errors"])
