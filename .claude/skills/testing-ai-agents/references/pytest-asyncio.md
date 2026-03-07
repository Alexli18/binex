# Pytest-Asyncio Patterns

Comprehensive patterns for async testing with pytest-asyncio.

## Configuration

### pyproject.toml

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Auto-detect async tests
asyncio_default_fixture_loop_scope = "function"  # Clean loop per test
testpaths = ["tests"]
markers = [
    "asyncio: mark test as async",
]
```

### conftest.py Event Loop

```python
import asyncio
import pytest

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session-scoped fixtures.

    Required when:
    - Using session-scoped async fixtures
    - Sharing database connections across tests
    - Expensive setup that should run once
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
```

## Async Fixtures

### Basic Async Fixture

```python
@pytest.fixture
async def async_client():
    """Simple async fixture with setup and teardown."""
    client = AsyncClient()
    await client.connect()
    yield client
    await client.disconnect()
```

### Fixture Dependencies

```python
@pytest.fixture
async def session(setup_database):
    """Fixture that depends on another fixture."""
    async with TestAsyncSession() as session:
        yield session

@pytest.fixture
async def populated_db(session):
    """Fixture that uses another fixture."""
    # Create test data
    task = Task(title="Test")
    session.add(task)
    await session.commit()
    yield session
```

## Test Patterns

### Basic Async Test

```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result == expected
```

### With Auto Mode (No Decorator Needed)

```python
# With asyncio_mode = "auto" in config
async def test_auto_async():
    """No @pytest.mark.asyncio needed!"""
    result = await async_op()
    assert result
```

### Testing Timeouts

```python
import asyncio

@pytest.mark.asyncio
async def test_timeout_raises():
    """Test that slow operations timeout correctly."""
    with pytest.raises(asyncio.TimeoutError):
        async with asyncio.timeout(0.1):
            await asyncio.sleep(1)

@pytest.mark.asyncio
async def test_operation_completes_in_time():
    """Test operation finishes before timeout."""
    async with asyncio.timeout(1.0):
        result = await fast_operation()
    assert result
```

### Testing Concurrent Operations

```python
import asyncio

@pytest.mark.asyncio
async def test_concurrent_requests():
    """Test multiple operations run concurrently."""
    results = await asyncio.gather(
        async_operation(1),
        async_operation(2),
        async_operation(3),
    )
    assert len(results) == 3
    assert all(r.success for r in results)
```

### Testing Race Conditions

```python
import asyncio

@pytest.mark.asyncio
async def test_race_condition_handling():
    """Test concurrent access to shared resource."""
    counter = Counter()
    event = asyncio.Event()

    async def increment():
        await event.wait()
        await counter.increment()

    # Start multiple tasks
    tasks = [asyncio.create_task(increment()) for _ in range(10)]

    # Release all at once
    event.set()
    await asyncio.gather(*tasks)

    assert counter.value == 10
```

### Class-Based Tests

```python
@pytest.mark.asyncio
class TestUserAPI:
    """Group related tests in a class."""

    async def test_create_user(self, client):
        response = await client.post("/users", json={"name": "Test"})
        assert response.status_code == 201

    async def test_get_user(self, client):
        response = await client.get("/users/1")
        assert response.status_code == 200
```

## Common Patterns

### Testing Async Context Managers

```python
@pytest.mark.asyncio
async def test_async_context_manager():
    async with DatabaseConnection() as conn:
        result = await conn.query("SELECT 1")
        assert result == 1
    # Connection closed automatically
```

### Testing Async Generators

```python
@pytest.mark.asyncio
async def test_async_generator():
    results = []
    async for item in stream_data():
        results.append(item)
        if len(results) >= 5:
            break
    assert len(results) == 5
```

### Mocking Async Functions

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mock():
    mock_response = {"status": "success"}

    with patch("app.client.fetch", new=AsyncMock(return_value=mock_response)):
        result = await process_data()
        assert result["status"] == "success"
```

## Gotchas

### 1. Event Loop Closed Error

**Problem**: "Event loop is closed" error in tests.

**Solution**: Use function-scoped event loop or session fixture:
```python
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

### 2. Fixture Not Found

**Problem**: Async fixture not available.

**Solution**: Use `@pytest_asyncio.fixture`:
```python
import pytest_asyncio

@pytest_asyncio.fixture
async def my_fixture():
    yield await setup()
```

### 3. Deadlocks

**Problem**: Tests hang indefinitely.

**Solution**: Add timeouts and check fixture dependencies:
```python
@pytest.mark.asyncio
@pytest.mark.timeout(5)  # Requires pytest-timeout
async def test_with_timeout():
    await potentially_slow_operation()
```

### 4. State Leakage

**Problem**: Tests affect each other.

**Solution**: Use function-scoped fixtures:
```python
@pytest.fixture  # Default is function scope
async def clean_database():
    await reset_db()
    yield
    await cleanup_db()
```

## Version Notes

- **pytest-asyncio 0.23+**: Use `asyncio_default_fixture_loop_scope`
- **Python 3.11+**: Use `asyncio.timeout()` instead of `asyncio.wait_for()`
- **Avoid**: `unittest.IsolatedAsyncioTestCase` with pytest (use pytest-asyncio instead)
