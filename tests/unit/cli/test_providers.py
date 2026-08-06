"""Tests for provider configuration registry (T001)."""

from binex.cli.providers import PROVIDERS, ProviderConfig, get_provider


class TestProvidersRegistry:
    """Tests for the PROVIDERS registry."""

    def test_providers_has_exactly_9_entries(self):
        assert len(PROVIDERS) == 9

    def test_all_providers_have_required_fields(self):
        for name, config in PROVIDERS.items():
            assert isinstance(config, ProviderConfig)
            assert isinstance(config.name, str) and config.name
            assert isinstance(config.default_model, str) and config.default_model
            assert config.env_var is None or isinstance(config.env_var, str)
            assert isinstance(config.agent_prefix, str) and config.agent_prefix

    def test_ollama_has_no_env_var(self):
        assert PROVIDERS["ollama"].env_var is None

    def test_non_ollama_providers_have_env_var(self):
        for name, config in PROVIDERS.items():
            if name == "ollama":
                continue
            assert config.env_var is not None, f"{name} should have env_var set"

    def test_all_agent_prefixes_start_with_llm(self):
        for name, config in PROVIDERS.items():
            assert config.agent_prefix.startswith("llm://"), (
                f"{name} agent_prefix should start with 'llm://'"
            )

    def test_get_provider_existing(self):
        config = get_provider("openai")
        assert config is not None
        assert config.name == "openai"

    def test_get_provider_nonexistent(self):
        assert get_provider("nonexistent") is None

    def test_provider_default_models(self):
        expected = {
            "ollama": "ollama/llama3.2",
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "gemini": "gemini/gemini-2.0-flash",
            "groq": "groq/llama3-70b-8192",
            "mistral": "mistral/mistral-large-latest",
            "deepseek": "deepseek/deepseek-chat",
            "together": "together_ai/meta-llama/Llama-3-70b",
        }
        for name, model in expected.items():
            assert PROVIDERS[name].default_model == model, (
                f"{name} default_model mismatch"
            )

    def test_provider_env_vars(self):
        expected = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "together": "TOGETHER_API_KEY",
        }
        for name, env_var in expected.items():
            assert PROVIDERS[name].env_var == env_var

    def test_provider_names_match_keys(self):
        for key, config in PROVIDERS.items():
            assert key == config.name, f"Key '{key}' != config.name '{config.name}'"
