# Testing

## Running Tests

```bash
python -m pytest tests/
```

The suite contains ~870 tests across 75 unit test files and 1 integration test file. All async tests are auto-detected (`asyncio_mode = "auto"` in `pyproject.toml`), so no `@pytest.mark.asyncio` decorator is needed.

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Unit tests (~75 files)
│   ├── test_models_*.py
│   ├── test_cli_*.py
│   ├── test_dag.py
│   ├── test_scheduler.py
│   ├── test_dispatcher.py
│   └── ...
└── integration/
    └── test_orchestrator.py
```

## Fixtures

Defined in `conftest.py`:

- **`sample_workflow_dict()`** -- minimal 2-node workflow spec
- **`sample_research_workflow_dict()`** -- 5-node research pipeline

## Mocking Patterns

| What | How |
|---|---|
| CLI stores | `patch("binex.cli.<module>._get_stores", return_value=(exec_store, art_store))` |
| LiteLLM calls | `patch("litellm.acompletion", new_callable=AsyncMock)` |
| Unit-test stores | `InMemoryExecutionStore()`, `InMemoryArtifactStore()` |

## CLI Testing

```python
from click.testing import CliRunner
from unittest.mock import patch

runner = CliRunner()
with patch("binex.cli.run._get_stores", return_value=(exec_store, art_store)):
    result = runner.invoke(run_cmd, ["workflow.yaml"])
    assert result.exit_code == 0
```

Always patch `_get_stores` -- it returns the real sqlite + filesystem stores by default, which require `.binex/` on disk.

## Async Tests

```python
async def test_dispatch_calls_adapter():
    adapter = AsyncMock()
    adapter.execute.return_value = [Artifact(name="out", data="ok")]
    result = await dispatcher.dispatch(task, adapter)
    assert result[0].name == "out"
```

No decorator required. `pytest-asyncio` auto-mode handles discovery.
