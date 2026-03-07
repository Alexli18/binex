# RESPX Mocking Guide

Mock HTTPX requests for testing LLM API calls without hitting real endpoints.

## Installation

```bash
uv add --dev respx
```

## Basic Usage

### Decorator Style

```python
import respx
import httpx
import pytest

@pytest.mark.asyncio
@respx.mock
async def test_api_call():
    """Mock with decorator."""
    respx.get("https://api.example.com/data").mock(
        return_value=httpx.Response(200, json={"result": "success"})
    )

    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")

    assert response.json() == {"result": "success"}
```

### Context Manager Style

```python
@pytest.mark.asyncio
async def test_api_call():
    """Mock with context manager."""
    with respx.mock:
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"data": "value"})
        )
        # Make requests...
```

### Fixture Style (Recommended)

```python
@pytest.fixture
def respx_mock():
    """RESPX fixture for cleaner tests."""
    with respx.mock:
        yield respx

@pytest.mark.asyncio
async def test_with_fixture(respx_mock):
    respx_mock.get("https://api.example.com/").mock(
        return_value=httpx.Response(200)
    )
    # Make requests...
```

## Mocking LLM APIs

### OpenAI API

```python
@pytest.mark.asyncio
@respx.mock
async def test_openai_completion():
    """Mock OpenAI chat completion."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "gpt-4",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help you?"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                }
            }
        )
    )

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key="test-key")

    response = await client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )

    assert response.choices[0].message.content == "Hello! How can I help you?"
```

### OpenAI with Tool Calls

```python
@pytest.mark.asyncio
@respx.mock
async def test_openai_tool_call():
    """Mock OpenAI response with tool calls."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location": "London", "unit": "celsius"}'
                            }
                        }]
                    },
                    "finish_reason": "tool_calls"
                }]
            }
        )
    )

    # Your test code...
```

### Anthropic API

```python
@pytest.mark.asyncio
@respx.mock
async def test_anthropic_completion():
    """Mock Anthropic messages API."""
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "msg_123",
                "type": "message",
                "role": "assistant",
                "content": [{
                    "type": "text",
                    "text": "Hello! I'm Claude."
                }],
                "model": "claude-3-5-sonnet-20241022",
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 20
                }
            }
        )
    )

    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key="test-key")

    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}]
    )

    assert response.content[0].text == "Hello! I'm Claude."
```

## Advanced Patterns

### Sequential Responses

```python
@pytest.mark.asyncio
@respx.mock
async def test_multi_turn_conversation():
    """Mock multiple responses in sequence."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(200, json={
                "choices": [{"message": {"content": "First response"}}]
            }),
            httpx.Response(200, json={
                "choices": [{"message": {"content": "Second response"}}]
            }),
            httpx.Response(200, json={
                "choices": [{"message": {"content": "Third response"}}]
            }),
        ]
    )

    # First call returns "First response"
    # Second call returns "Second response"
    # etc.
```

### Error Responses

```python
@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_error():
    """Mock rate limit response."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            429,
            json={
                "error": {
                    "message": "Rate limit exceeded",
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded"
                }
            },
            headers={"Retry-After": "60"}
        )
    )

    with pytest.raises(RateLimitError):
        await make_api_call()

@pytest.mark.asyncio
@respx.mock
async def test_timeout():
    """Mock timeout."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("Connection timed out")
    )

    with pytest.raises(TimeoutError):
        await make_api_call()
```

### Pattern Matching

```python
@pytest.mark.asyncio
@respx.mock
async def test_pattern_matching():
    """Match requests by pattern."""
    # Match any OpenAI endpoint
    respx.post(url__startswith="https://api.openai.com/").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )

    # Match with regex
    respx.route(method="POST", url__regex=r".*openai.*").mock(
        return_value=httpx.Response(200)
    )
```

### Request Assertions

```python
@pytest.mark.asyncio
@respx.mock
async def test_request_validation():
    """Assert on request content."""
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "Hi"}}]})
    )

    await make_api_call(prompt="Test message")

    # Assert route was called
    assert route.called
    assert route.call_count == 1

    # Check request body
    request = route.calls[0].request
    body = request.content.decode()
    assert "Test message" in body

    # Check headers
    assert request.headers["Authorization"] == "Bearer test-key"
```

### Base URL Configuration

```python
@pytest.mark.asyncio
async def test_with_base_url():
    """Configure base URL for cleaner routes."""
    with respx.mock(base_url="https://api.openai.com/v1") as mock:
        mock.post("/chat/completions").mock(
            return_value=httpx.Response(200, json={"result": "ok"})
        )
        mock.post("/embeddings").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        # Make requests...
```

## Compatibility Notes

### httpx 0.28+ Issue

After httpx 0.28.0, you may need to specify the transport:

```python
with respx.mock(using="httpx") as mock:
    mock.get("https://api.example.com/").respond(200)
    # ...
```

### Wrapped Clients

If httpx.Client is wrapped in a class, create the client inside the mock context:

```python
# BAD - client created outside mock
client = httpx.AsyncClient()

@respx.mock
async def test_bad():
    # Mocking won't work!

# GOOD - client created inside mock
@respx.mock
async def test_good():
    async with httpx.AsyncClient() as client:
        # Mocking works!
```

## Best Practices

1. **Use specific URLs**: Don't over-mock with wildcards
2. **Test error paths**: Mock timeouts, rate limits, 500s
3. **Assert on requests**: Verify correct data was sent
4. **Use fixtures**: Cleaner than decorators for complex setups
5. **Clear between tests**: respx.mock handles this automatically
