# FastAPI Testing Patterns

Comprehensive patterns for testing FastAPI applications with agent backends.

## Setup

### Dependencies

```bash
uv add --dev pytest pytest-asyncio httpx
```

### Basic conftest.py

```python
# tests/conftest.py
import os
import pytest
from httpx import ASGITransport, AsyncClient

# Set test environment BEFORE imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["TESTING"] = "true"

from app.main import app
from app.database import get_session
from app.auth import get_current_user


@pytest.fixture
async def client():
    """Async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
```

## Dependency Overrides

### Override Database

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# In-memory SQLite for tests
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)

TestAsyncSession = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_test_session():
    async with TestAsyncSession() as session:
        yield session


@pytest.fixture(autouse=True)
async def setup_database():
    """Create tables before each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.fixture
async def client():
    app.dependency_overrides[get_session] = get_test_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

### Override Authentication

```python
# Mock user
TEST_USER = {
    "sub": "test-user-123",
    "email": "test@example.com",
    "role": "user",
}


def get_test_user():
    return TEST_USER


@pytest.fixture
async def authenticated_client():
    """Client with mocked authentication."""
    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_current_user] = get_test_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client():
    """Client with admin privileges."""
    def get_admin_user():
        return {**TEST_USER, "role": "admin"}

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_current_user] = get_admin_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

## Testing Patterns

### CRUD Operations

```python
@pytest.mark.asyncio
async def test_create_resource(client: AsyncClient):
    """Test POST endpoint."""
    response = await client.post(
        "/api/tasks",
        json={"title": "New Task", "priority": "high"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Task"
    assert "id" in data


@pytest.mark.asyncio
async def test_read_resource(client: AsyncClient):
    """Test GET endpoint."""
    # Create first
    create_response = await client.post(
        "/api/tasks",
        json={"title": "Test"},
    )
    task_id = create_response.json()["id"]

    # Read
    response = await client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Test"


@pytest.mark.asyncio
async def test_update_resource(client: AsyncClient):
    """Test PUT/PATCH endpoint."""
    # Create
    create_response = await client.post(
        "/api/tasks",
        json={"title": "Original"},
    )
    task_id = create_response.json()["id"]

    # Update
    response = await client.put(
        f"/api/tasks/{task_id}",
        json={"title": "Updated"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"


@pytest.mark.asyncio
async def test_delete_resource(client: AsyncClient):
    """Test DELETE endpoint."""
    # Create
    create_response = await client.post(
        "/api/tasks",
        json={"title": "To Delete"},
    )
    task_id = create_response.json()["id"]

    # Delete
    response = await client.delete(f"/api/tasks/{task_id}")
    assert response.status_code == 200

    # Verify gone
    get_response = await client.get(f"/api/tasks/{task_id}")
    assert get_response.status_code == 404
```

### Query Parameters

```python
@pytest.mark.asyncio
async def test_list_with_pagination(client: AsyncClient):
    """Test pagination parameters."""
    # Create test data
    for i in range(25):
        await client.post("/api/tasks", json={"title": f"Task {i}"})

    # Get first page
    response = await client.get(
        "/api/tasks",
        params={"limit": 10, "offset": 0},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10


@pytest.mark.asyncio
async def test_list_with_filters(client: AsyncClient):
    """Test filter parameters."""
    await client.post("/api/tasks", json={"title": "High Priority", "priority": "high"})
    await client.post("/api/tasks", json={"title": "Low Priority", "priority": "low"})

    response = await client.get(
        "/api/tasks",
        params={"priority": "high"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["priority"] == "high"


@pytest.mark.asyncio
async def test_list_with_search(client: AsyncClient):
    """Test search parameter."""
    await client.post("/api/tasks", json={"title": "Meeting with team"})
    await client.post("/api/tasks", json={"title": "Code review"})

    response = await client.get(
        "/api/tasks",
        params={"search": "meeting"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "Meeting" in data[0]["title"]
```

### Error Handling

```python
@pytest.mark.asyncio
async def test_not_found(client: AsyncClient):
    """Test 404 response."""
    response = await client.get("/api/tasks/99999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_validation_error(client: AsyncClient):
    """Test 422 validation error."""
    response = await client.post(
        "/api/tasks",
        json={"title": ""},  # Empty title invalid
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient):
    """Test 401 without auth."""
    # Clear overrides to test actual auth
    app.dependency_overrides.clear()

    response = await client.get("/api/protected-resource")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_forbidden(authenticated_client: AsyncClient):
    """Test 403 with wrong permissions."""
    response = await authenticated_client.delete("/api/admin-only-resource/1")
    assert response.status_code == 403
```

### File Uploads

```python
@pytest.mark.asyncio
async def test_file_upload(client: AsyncClient):
    """Test file upload endpoint."""
    files = {"file": ("test.txt", b"Hello World", "text/plain")}

    response = await client.post("/api/upload", files=files)
    assert response.status_code == 200
    assert response.json()["filename"] == "test.txt"
```

### Authentication Headers

```python
@pytest.mark.asyncio
async def test_with_bearer_token():
    """Test with real auth header."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test-token"},
    ) as client:
        response = await client.get("/api/protected")
        assert response.status_code == 200
```

## Testing Agent Endpoints

### With Mocked LLM

```python
import respx
import httpx

@pytest.mark.asyncio
@respx.mock
async def test_agent_chat(client: AsyncClient):
    """Test agent chat endpoint with mocked LLM."""
    # Mock OpenAI
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "I'll help you with that task."
                    }
                }]
            }
        )
    )

    response = await client.post(
        "/api/agent/chat",
        json={"message": "Help me create a task"},
    )

    assert response.status_code == 200
    assert "help" in response.json()["response"].lower()
```

### Streaming Responses

```python
@pytest.mark.asyncio
@respx.mock
async def test_streaming_response(client: AsyncClient):
    """Test SSE streaming endpoint."""
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Hello"}}]}
        )
    )

    async with client.stream("POST", "/api/agent/stream", json={"message": "Hi"}) as response:
        assert response.status_code == 200
        chunks = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                chunks.append(line[6:])
        assert len(chunks) > 0
```

## Helper Functions

### Test Data Factories

```python
# tests/factories.py
from app.models import Task, Project

async def create_task(client: AsyncClient, **kwargs) -> dict:
    """Create a task and return its data."""
    data = {"title": "Test Task", **kwargs}
    response = await client.post("/api/tasks", json=data)
    assert response.status_code == 201
    return response.json()


async def create_project(client: AsyncClient, **kwargs) -> dict:
    """Create a project and return its data."""
    data = {"name": "Test Project", "slug": "test-project", **kwargs}
    response = await client.post("/api/projects", json=data)
    assert response.status_code == 201
    return response.json()


# Usage in tests
@pytest.mark.asyncio
async def test_with_factory(client: AsyncClient):
    project = await create_project(client, name="My Project")
    task = await create_task(client, project_id=project["id"])
    assert task["project_id"] == project["id"]
```

## Lifespan Events

If your app uses lifespan events:

```python
from asgi_lifespan import LifespanManager

@pytest.fixture
async def client():
    """Client with lifespan events."""
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
```

Install with: `uv add --dev asgi-lifespan`

## Best Practices

1. **Use autouse fixtures** for database setup/teardown
2. **Override dependencies** instead of mocking internals
3. **Test happy path and error cases** separately
4. **Use factories** for consistent test data creation
5. **Clear overrides** in fixture cleanup
6. **Test status codes AND response bodies**
7. **Use async client** for async endpoints
