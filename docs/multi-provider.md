# Multi-Provider LLM Support

Binex supports mixing different LLM providers in a single workflow via [LiteLLM](https://docs.litellm.ai/) model naming.

## Usage Modes

### 1. Direct — API keys in environment

Set provider API keys as environment variables and use standard LiteLLM model names:

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GEMINI_API_KEY=...

binex run examples/multi-provider-research.yaml --var query="quantum computing"
```

LiteLLM routes each model name to the correct provider automatically.

### 2. Proxy — centralized routing via docker-compose

Run `docker-compose` with the included `litellm_config.yaml` for a single proxy endpoint:

```bash
# Set API keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GEMINI_API_KEY=...

cd docker
docker-compose up -d
```

The proxy exposes all configured models on `http://localhost:4000`. To route through the proxy, use `config.api_base` in your workflow nodes or set `LITELLM_API_BASE`.

### 3. Per-node config overrides

Use the optional `config` block on any node to set `temperature`, `max_tokens`, `api_base`, or `api_key`:

```yaml
nodes:
  planner:
    agent: "llm://gpt-4o"
    system_prompt: "Plan the research"
    inputs:
      query: "${user.query}"
    outputs: [plan]
    config:
      temperature: 0.3
      max_tokens: 4096

  researcher:
    agent: "llm://gemini/gemini-2.0-flash"
    system_prompt: "Research the topic"
    inputs:
      questions: "${planner.plan}"
    outputs: [findings]
    depends_on: [planner]
    config:
      api_base: "http://localhost:4000"  # route through proxy
```

## Supported model name formats

| Provider   | Model name example                  |
|------------|-------------------------------------|
| OpenAI     | `llm://gpt-4o`                      |
| Anthropic  | `llm://claude-sonnet-4-20250514`        |
| Google     | `llm://gemini/gemini-2.0-flash`     |
| Ollama     | `llm://ollama/llama3.2`             |
| Any LiteLLM| `llm://<litellm-model-name>`        |

## A2A agents

Use the `a2a://` prefix to connect to remote A2A-compatible agent servers:

```yaml
nodes:
  analyzer:
    agent: "a2a://http://localhost:8001"
    system_prompt: "Analyze data"
    inputs:
      data: "${user.data}"
    outputs: [analysis]
```
