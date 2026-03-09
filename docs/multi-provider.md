# Multi-Provider LLM Support

Binex supports mixing different LLM providers in a single workflow via [LiteLLM](https://docs.litellm.ai/) model naming. You can combine local models (Ollama), cloud APIs (OpenAI, Anthropic, Gemini), and remote A2A agents in one pipeline.

## Example: Multi-Provider Research Pipeline

The included `examples/multi-provider-demo.yaml` demonstrates a research pipeline that uses Ollama for planning/summarization and OpenRouter for parallel research:

```yaml
name: multi-provider-research
description: "Research pipeline: Ollama plans & summarizes, Gemini researches"

nodes:
  user_input:
    agent: "human://input"
    system_prompt: "What would you like to research?"
    outputs: [result]

  planner:
    agent: "llm://ollama/gemma3:4b"
    system_prompt: >
      You are a research planner. Given a topic, create a structured
      research plan with 3 specific subtopics to investigate.
      Output a numbered list of research tasks. Be concise.
    inputs:
      topic: "${user_input.result}"
    outputs: [result]
    depends_on: [user_input]

  researcher1:
    agent: "llm://openrouter/z-ai/glm-4.5-air:free"
    system_prompt: >
      You are a thorough researcher. Investigate the first subtopic
      from the research plan. Provide findings with specific facts.
      Keep response under 200 words.
    inputs:
      plan: "${planner.result}"
    outputs: [result]
    depends_on: [planner]

  researcher2:
    agent: "llm://openrouter/stepfun/step-3.5-flash:free"
    system_prompt: >
      You are a thorough researcher. Investigate the second subtopic
      from the research plan. Provide findings with specific facts.
      Keep response under 200 words.
    inputs:
      plan: "${planner.result}"
    outputs: [result]
    depends_on: [planner]

  summarizer:
    agent: "llm://ollama/gemma3:4b"
    system_prompt: >
      You are a summarizer. Combine the research findings into a clear,
      well-structured final summary. Include key findings and conclusions.
      Keep response under 300 words.
    inputs:
      research1: "${researcher1.result}"
      research2: "${researcher2.result}"
    outputs: [result]
    depends_on: [researcher1, researcher2]
```

The DAG topology is: `user_input -> planner -> [researcher1, researcher2] -> summarizer`. The two researchers run in parallel since they share the same dependency.

## Usage Modes

### 1. Direct — API keys in environment

Set provider API keys as environment variables and use standard LiteLLM model names in your workflow:

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GEMINI_API_KEY=...

binex run examples/multi-provider-demo.yaml
```

LiteLLM routes each model name to the correct provider automatically. You can also put keys in a `.env` file in your project root — Binex loads it via `python-dotenv` at startup.

### 2. Ollama — fully local, no API keys

For local-only workflows, Ollama requires no API keys. Just make sure Ollama is running:

```bash
# Start Ollama (if not already running)
ollama serve

# Pull the model you need
ollama pull gemma3:4b

# Run the workflow
binex run my-workflow.yaml
```

Use the `llm://ollama/<model>` prefix in your workflow nodes:

```yaml
nodes:
  writer:
    agent: "llm://ollama/gemma3:4b"
    system_prompt: "Write a short poem"
    outputs: [result]
```

### 3. Proxy — centralized routing via docker-compose

Run `docker-compose` with the included `litellm_config.yaml` for a single proxy endpoint:

```bash
# Set API keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GEMINI_API_KEY=...

cd docker
docker-compose up -d
```

The proxy exposes all configured models on `http://localhost:4000`. Route traffic through it using `config.api_base` on your workflow nodes or by setting `LITELLM_API_BASE` in your environment.

### 4. Per-node config overrides

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

Config values are forwarded to `litellm.acompletion()` and only included when not `None`.

## Supported Providers

Binex includes a built-in registry of 9 providers:

| Provider | Agent prefix | Default model | API key env var |
|----------|-------------|---------------|-----------------|
| Ollama | `llm://ollama/` | `ollama/llama3.2` | None (local) |
| OpenAI | `llm://` | `gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `llm://` | `claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| Gemini | `llm://gemini/` | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Groq | `llm://groq/` | `groq/llama3-70b-8192` | `GROQ_API_KEY` |
| Mistral | `llm://mistral/` | `mistral/mistral-large-latest` | `MISTRAL_API_KEY` |
| DeepSeek | `llm://deepseek/` | `deepseek/deepseek-chat` | `DEEPSEEK_API_KEY` |
| Together | `llm://together_ai/` | `together_ai/meta-llama/Llama-3-70b` | `TOGETHER_API_KEY` |
| OpenRouter | `llm://openrouter/` | `openrouter/google/gemini-2.5-flash` | `OPENROUTER_API_KEY` |

Any model name supported by LiteLLM works with the `llm://` prefix. See the [LiteLLM docs](https://docs.litellm.ai/docs/providers) for the full list.

## A2A Agents

Use the `a2a://` prefix to connect to remote A2A-compatible agent servers. The remote agent must expose `POST /execute` and `GET /health` endpoints:

```yaml
nodes:
  analyzer:
    agent: "a2a://http://localhost:8001"
    system_prompt: "Analyze data"
    inputs:
      data: "${user.data}"
    outputs: [analysis]
```

The A2A adapter sends `{task_id, skill, trace_id, artifacts}` to the remote endpoint and expects `{artifacts}` in the response.

## Troubleshooting

### Ollama not running

```
Error: Connection refused — http://localhost:11434
```

Make sure Ollama is running (`ollama serve`) and that you have pulled the model referenced in your workflow (`ollama pull <model>`). Ollama runs on port 11434 by default.

### API key missing or invalid

```
Error: AuthenticationError — Invalid API key
```

Check that the appropriate environment variable is set. You can use `binex doctor` to verify your environment:

```bash
binex doctor
```

Alternatively, put your keys in a `.env` file in your project root:

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Model not found

```
Error: Model 'xyz' not found
```

Verify the model name matches LiteLLM's expected format. Use the provider table above as a reference. For Ollama, ensure the model is pulled locally. For cloud providers, check that the model name is valid for your account/tier.

### Timeout or slow responses

If a node times out, you can increase the deadline in the workflow defaults or per-node:

```yaml
defaults:
  deadline_ms: 120000  # 2 minutes

nodes:
  slow_node:
    agent: "llm://gpt-4o"
    system_prompt: "Detailed analysis"
    outputs: [result]
    deadline_ms: 300000  # 5 minutes for this node
```
