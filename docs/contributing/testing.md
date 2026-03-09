# Testing

## Running Tests

Run the full suite:

```bash
python -m pytest tests/
```

The suite contains ~870 tests across ~75 unit test files and 1 integration test file.

Run a specific test file:

```bash
python -m pytest tests/unit/test_qa_phase4_core.py
```

Run tests matching a keyword:

```bash
python -m pytest tests/ -k "test_hello"
```

Run with verbose output:

```bash
python -m pytest tests/ -v
```

## Test Organization

```
tests/
├── conftest.py                     # Shared fixtures (sample workflows)
├── unit/                           # Unit tests (~75 files, ~860 tests)
│   ├── test_models_*.py            # Pydantic model validation
│   ├── test_cli_*.py               # CLI command tests
│   ├── test_dag.py                 # DAG construction and traversal
│   ├── test_scheduler.py           # Scheduler logic (dependency resolution)
│   ├── test_dispatcher.py          # Dispatcher and adapter routing
│   ├── test_qa_*.py                # QA regression tests (see below)
│   └── ...
└── integration/
    └── test_orchestrator.py        # End-to-end orchestrator tests
```

### QA Test Files

QA tests follow a structured plan and are organized by phase:

| File | Focus | Tests |
|------|-------|-------|
| `test_qa_models.py` | Pydantic models, validation | ~20 |
| `test_qa_stores.py` | Sqlite and filesystem stores | ~20 |
| `test_qa_dag_scheduler.py` | DAG and scheduler | ~15 |
| `test_qa_adapters_runtime.py` | Adapters, dispatcher | ~15 |
| `test_qa_cli_workflow.py` | CLI + workflow loading | ~15 |
| `test_qa_trace_registry.py` | Trace, registry | ~15 |
| `test_qa_replay.py` | Replay command | ~10 |
| `test_qa_phase2.py` | Agents, settings | 22 |
| `test_qa_phase3_cli.py` | CLI DX commands | 22 |
| `test_qa_phase4_core.py` | Runtime, stores, adapters | 27 |
| `test_qa_phase5a_security.py` | Security, E2E | 22 |
| `test_qa_phase5b_remaining.py` | Registry, trace, workflow, models | 21 |

## Async Test Configuration

All async tests are auto-detected. The `pyproject.toml` sets:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

This means you do **not** need the `@pytest.mark.asyncio` decorator. Simply define your test as `async def` and pytest-asyncio handles the rest:

```python
async def test_orchestrator_runs_two_nodes():
    orch = Orchestrator(
        artifact_store=InMemoryArtifactStore(),
        execution_store=InMemoryExecutionStore(),
    )
    # ... register adapters, run workflow
    summary = await orch.run_workflow(spec)
    assert summary.completed_nodes == 2
```

## Shared Fixtures

Defined in `tests/conftest.py`:

- **`sample_workflow_dict()`** — Minimal 2-node workflow (producer -> consumer) with local echo agents
- **`sample_research_workflow_dict()`** — 5-node research pipeline (planner -> 2 researchers -> validator -> summarizer)

Usage:

```python
def test_workflow_parsing(sample_workflow_dict):
    spec = WorkflowSpec(**sample_workflow_dict)
    assert len(spec.nodes) == 2
    assert "producer" in spec.nodes
```

## Mocking Patterns

### CLI Store Patching

CLI commands use a `_get_stores()` helper that returns real sqlite + filesystem stores by default. **Always patch this in tests** to avoid hitting disk:

```python
from click.testing import CliRunner
from unittest.mock import patch
from binex.cli.hello import hello_cmd
from binex.stores.backends.memory import InMemoryExecutionStore, InMemoryArtifactStore

def test_hello_command():
    stores = InMemoryExecutionStore(), InMemoryArtifactStore()
    with patch("binex.cli.hello._get_stores", return_value=stores):
        runner = CliRunner()
        result = runner.invoke(hello_cmd, [])
    assert result.exit_code == 0
    assert "Hello from Binex!" in result.output
```

The patch target follows the pattern `binex.cli.<module>._get_stores`, where `<module>` matches the command file (e.g., `run`, `debug`, `hello`, `trace`, `replay`).

### In-Memory Stores for Unit Tests

For non-CLI tests, use the in-memory store implementations directly:

```python
from binex.stores.backends.memory import InMemoryExecutionStore, InMemoryArtifactStore

async def test_store_roundtrip():
    store = InMemoryExecutionStore()
    await store.record(execution_record)
    result = await store.get_run(run_id)
    assert result is not None
```

### LiteLLM Mocking

Mock `litellm.acompletion` when testing LLM-backed nodes:

```python
from unittest.mock import AsyncMock, patch

async def test_llm_adapter():
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="result"))]

    with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
        result = await adapter.execute(task, inputs, trace_id)
    assert result[0].content == "result"
```

### Custom Test Adapters

For orchestrator tests, create simple adapter classes instead of mocking:

```python
class EchoAdapter:
    """Returns an artifact containing the node_id as content."""

    def __init__(self, content: str | None = None, *, fail: bool = False):
        self._content = content
        self._fail = fail
        self.call_count = 0

    async def execute(self, task, input_artifacts, trace_id):
        self.call_count += 1
        if self._fail:
            raise RuntimeError(f"Node {task.node_id} failed")
        content = self._content or f"result_from_{task.node_id}"
        return [
            Artifact(
                id=f"art_{task.run_id}_{task.node_id}",
                run_id=task.run_id,
                type="result",
                content=content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self):
        return AgentHealth.ALIVE
```

This pattern is used extensively in `test_qa_phase4_core.py` for testing orchestrator flows, retry logic, and DAG execution order.

### Writing YAML Workflow Files in Tests

Use `tmp_path` and `textwrap.dedent` to create temporary workflow files:

```python
import textwrap
from pathlib import Path

def _write_yaml(tmp_path: Path, content: str) -> Path:
    wf = tmp_path / "wf.yaml"
    wf.write_text(textwrap.dedent(content))
    return wf

def test_run_command(tmp_path):
    wf = _write_yaml(tmp_path, """\
        name: test
        nodes:
          node1:
            agent: "local://echo"
            system_prompt: do_stuff
            outputs: [result]
    """)
    # ... invoke CLI with str(wf)
```

## Linting

Run ruff to check for style and import issues:

```bash
ruff check src/
```

The project uses these ruff rules: `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `N` (naming), `W` (warnings), `UP` (pyupgrade). Line length is 99 characters.

## Code Coverage

To run tests with coverage:

```bash
python -m pytest tests/ --cov=src/binex --cov-report=term-missing
```

The current test suite achieves approximately 96% code coverage.
