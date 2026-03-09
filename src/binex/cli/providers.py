"""Provider configuration registry for multi-provider LLM support."""

from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    name: str  # Human-readable provider name
    default_model: str  # Default litellm model string
    env_var: str | None  # Required environment variable name
    agent_prefix: str  # Agent URI prefix for workflow YAML


PROVIDERS: dict[str, ProviderConfig] = {
    "ollama": ProviderConfig(
        name="ollama",
        default_model="ollama/llama3.2",
        env_var=None,
        agent_prefix="llm://ollama/",
    ),
    "openai": ProviderConfig(
        name="openai",
        default_model="gpt-4o",
        env_var="OPENAI_API_KEY",
        agent_prefix="llm://",
    ),
    "anthropic": ProviderConfig(
        name="anthropic",
        default_model="claude-sonnet-4-20250514",
        env_var="ANTHROPIC_API_KEY",
        agent_prefix="llm://",
    ),
    "gemini": ProviderConfig(
        name="gemini",
        default_model="gemini/gemini-2.0-flash",
        env_var="GEMINI_API_KEY",
        agent_prefix="llm://gemini/",
    ),
    "groq": ProviderConfig(
        name="groq",
        default_model="groq/llama3-70b-8192",
        env_var="GROQ_API_KEY",
        agent_prefix="llm://groq/",
    ),
    "mistral": ProviderConfig(
        name="mistral",
        default_model="mistral/mistral-large-latest",
        env_var="MISTRAL_API_KEY",
        agent_prefix="llm://mistral/",
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        default_model="deepseek/deepseek-chat",
        env_var="DEEPSEEK_API_KEY",
        agent_prefix="llm://deepseek/",
    ),
    "together": ProviderConfig(
        name="together",
        default_model="together_ai/meta-llama/Llama-3-70b",
        env_var="TOGETHER_API_KEY",
        agent_prefix="llm://together_ai/",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        default_model="openrouter/google/gemini-2.5-flash",
        env_var="OPENROUTER_API_KEY",
        agent_prefix="llm://openrouter/",
    ),
}


def get_provider(name: str) -> ProviderConfig | None:
    """Look up a provider by name. Returns None if not found."""
    return PROVIDERS.get(name)
