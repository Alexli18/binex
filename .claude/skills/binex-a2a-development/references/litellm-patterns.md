# LiteLLM Patterns for Binex

## Table of Contents
1. [Basic Async Completion](#basic-async-completion)
2. [Streaming](#streaming)
3. [Error Handling & Retries](#error-handling--retries)
4. [Provider-Agnostic Model Strings](#provider-agnostic-model-strings)

## Basic Async Completion

```python
from litellm import acompletion

response = await acompletion(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7,
    max_tokens=1024
)
text = response.choices[0].message.content
```

## Streaming

```python
from litellm import acompletion

response = await acompletion(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True
)
async for chunk in response:
    delta = chunk.choices[0].delta.content or ""
    print(delta, end="")
```

## Error Handling & Retries

```python
import litellm
from litellm import acompletion

litellm.num_retries = 3
litellm.request_timeout = 60

async def safe_completion(**kwargs):
    try:
        return await acompletion(**kwargs)
    except litellm.exceptions.RateLimitError:
        # Fallback to cheaper model
        kwargs["model"] = "openai/gpt-3.5-turbo"
        return await acompletion(**kwargs)
    except litellm.exceptions.Timeout:
        raise
```

## Provider-Agnostic Model Strings

LiteLLM uses `provider/model` format:

| Provider | Model String |
|----------|-------------|
| OpenAI | `openai/gpt-4o` |
| Anthropic | `anthropic/claude-sonnet-4-20250514` |
| Ollama (local) | `ollama/llama3` |
| Azure | `azure/<deployment-name>` |
| Vertex AI | `vertex_ai/gemini-1.5-pro` |

For Binex LLMAdapter, the model string comes from workflow YAML node config.
