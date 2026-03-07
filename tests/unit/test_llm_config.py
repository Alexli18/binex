"""Tests for shared LLM config and client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from binex.agents.common.llm_config import LLMConfig
from binex.agents.common.llm_client import LLMClient


class TestLLMConfig:
    def test_default_config(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            config = LLMConfig(model="ollama/llama3.2")
            assert config.model == "ollama/llama3.2"
            assert config.temperature == 0.7
            assert config.max_tokens == 2048

    def test_env_overrides(self) -> None:
        env = {
            "BINEX_LLM_MODEL": "gpt-4",
            "BINEX_LLM_API_BASE": "http://proxy:4000",
            "BINEX_LLM_API_KEY": "sk-test",
            "BINEX_LLM_TEMPERATURE": "0.3",
            "BINEX_LLM_MAX_TOKENS": "4096",
        }
        with patch.dict("os.environ", env, clear=True):
            config = LLMConfig()
            assert config.model == "gpt-4"
            assert config.api_base == "http://proxy:4000"
            assert config.api_key == "sk-test"
            assert config.temperature == 0.3
            assert config.max_tokens == 4096

    def test_for_ollama(self) -> None:
        config = LLMConfig.for_ollama("mistral", "http://ollama:11434")
        assert config.model == "ollama/mistral"
        assert config.api_base == "http://ollama:11434"

    def test_for_litellm_proxy(self) -> None:
        config = LLMConfig.for_litellm_proxy("llama3.2", "http://proxy:4000")
        assert config.model == "llama3.2"
        assert config.api_base == "http://proxy:4000"


class TestLLMClient:
    @pytest.fixture
    def config(self) -> LLMConfig:
        return LLMConfig(model="test-model", api_base="http://test:4000", api_key="test-key")

    @pytest.fixture
    def client(self, config: LLMConfig) -> LLMClient:
        return LLMClient(config)

    async def test_complete(self, client: LLMClient) -> None:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = "Hello world"

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_llm:
            result = await client.complete("Say hello")
            assert result == "Hello world"
            mock_llm.assert_called_once()
            call_kwargs = mock_llm.call_args[1]
            assert call_kwargs["model"] == "test-model"
            assert call_kwargs["api_base"] == "http://test:4000"
            assert call_kwargs["api_key"] == "test-key"

    async def test_complete_with_system(self, client: LLMClient) -> None:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = "response"

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_llm:
            await client.complete("prompt", system="You are helpful")
            messages = mock_llm.call_args[1]["messages"]
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are helpful"
            assert messages[1]["role"] == "user"

    async def test_complete_json(self, client: LLMClient) -> None:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = '{"key": "value"}'

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_llm:
            result = await client.complete_json("Give me JSON")
            assert result == '{"key": "value"}'
            messages = mock_llm.call_args[1]["messages"]
            assert "JSON" in messages[0]["content"]

    async def test_default_config(self) -> None:
        client = LLMClient()
        assert client.config is not None
