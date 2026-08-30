# Testing

## Running Tests

Run the full suite:

```bash
python -m pytest tests/
```

The Python suite collects **3315 tests** across 260 test files. 53 of them are marked `e2e` and deselected by default (`addopts = "-m 'not e2e'"`); see [E2E Tests](#e2e-tests-playwright).

## Frontend tests (vitest)

The React app has its own unit suite — 175 tests across 27 files — plus a type check:

```bash
cd ui
npm ci
npx tsc --noEmit    # type errors are failures too
npx vitest run
```

Both run in CI (the `frontend` job in `ci.yml`, Node 20). They were not wired into CI until 2026-08 — a broken `reactflow` mock had been failing on `master` unnoticed for that reason. If you add a frontend test, check it runs here before pushing.

!!! tip "Mock reactflow partially, never exhaustively"
    `reactflow` needs browser APIs jsdom lacks, so its components have to be stubbed — but an exhaustive hand-written mock breaks the moment a component imports one more export. Use `vi.mock('reactflow', async (importOriginal) => ({ ...await importOriginal(), /* stubs */ }))` and override only the components that touch the DOM or the zustand store (`ReactFlow`, `ReactFlowProvider`, `Background`, `Controls`, `MiniMap`). Enums like `MarkerType` and `BackgroundVariant` then stay real. See `ui/src/components/editor/EditorCanvas.test.tsx`.

Run a specific test file:

```bash
python -m pytest tests/unit/qa/test_qa_phase4_core.py
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

## E2E Tests (Playwright)

Browser tests live in `tests/e2e_playwright/` and are marked `e2e`.

### Prerequisite: a running UI server

E2E tests expect the web UI on `http://localhost:8420`:

```bash
./scripts/build-ui.sh                  # build the frontend (once, or after frontend changes)
binex ui --port 8420 --no-browser      # start the server
```

### Running

```bash
pytest -m e2e            # all e2e tests
pytest -m e2e -n auto    # in parallel (pytest-xdist)
```

Plain `pytest tests/` does **not** run them: `pyproject.toml` sets `addopts = "-m 'not e2e'"`, so the marker is excluded by default. Passing `-m e2e` on the command line overrides it.

### Debugging a failure

Collect artifacts on failure (screenshots, video, trace go to `test-results/`):

```bash
pytest -m e2e --screenshot=only-on-failure --video=retain-on-failure --tracing=retain-on-failure
playwright show-trace test-results/<test-dir>/trace.zip
```

In CI the same artifacts are uploaded as `playwright-artifacts` on failure — download the zip and open the trace locally with `show-trace`.

Other useful modes:

```bash
pytest -m e2e -k test_name --headed    # watch the browser
PWDEBUG=1 pytest -m e2e -k test_name   # Playwright Inspector, step-by-step
```

### Page objects (`tests/e2e_playwright/pages/`)

- `sidebar.py` — `Sidebar` + `SidebarLink`/`SidebarGroup` enums
- `export_page.py` — `ExportPage` + `ExportFormat` enum

Fixtures `sidebar` and `export_page` are provided by `tests/e2e_playwright/conftest.py`. Three POM rules:

1. Selectors (`get_by_test_id`, roles) live only in page objects — no raw selectors in tests.
2. Page objects expose actions and `Locator`s, never assertions — checks belong in tests.
3. Use enums instead of strings for finite sets (sidebar links, export formats).

`conftest.py` also injects `TOUR_DISMISSED_STATE` as `storage_state` so the onboarding tour never overlays elements under test.

### Arrange-Act-Assert

Tests follow the Arrange-Act-Assert structure: set up state, perform the
action under test, verify the outcome. The three phases are separated by
a blank line — no comments needed; the whitespace *is* the annotation.
`test_export.py` is the reference example.

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

The unit + integration suite currently covers ~82% of `src/binex` (measured
2026-08, `--cov=binex` over `tests/unit tests/integration`). Not every
uncovered line is a gap — see the next section.

## Conscious Testing Boundaries

Some zeros and low percentages in the coverage report are decisions, not
neglect. The guiding rule: **the boundary runs through the terminal, not
through the file** — pure logic inside a boundary module is extracted into a
function and unit-tested; only the genuinely interactive or environment-bound
layer stays untested. If you touch one of these modules and find separable
logic, pull it out and test it rather than widening the boundary.

**Interactive TUI screens** — covered by manual QA scenarios plus smoke runs,
not unit tests. A unit test over a mocked `click.getchar()` loop asserts the
mock, not the terminal, and gives false confidence:

- `cli/explore_ui.py`, `cli/explore_actions.py`, `cli/explore_replay.py`,
  and the interactive loops of `cli/explore.py` (the `binex explore` dashboard)
- `cli/start_ui.py` and the prompt chains in `cli/start_constructor.py` /
  `cli/start_config.py` (the `binex start` wizard) — their computable steps
  are already covered via scaffold/template tests
- the live-render wrapper in `cli/run_progress.py` (rich `Live` table)
- the `_render_*` functions of `trace/diff_rich.py` (its pure helpers —
  delta formatting, error-change detection, row building — are unit-tested)
- rich panel styling in `cli/trace.py` (the event-grouping logic is tested)

**Launchers and entry points** — wrappers whose only behavior is starting
something else; a test would assert "the wrapper calls the library":

- `cli/collect.py` (uvicorn launcher for the OTel collector)
- `mcp_server/server.py::run_server()` (stdio transport is FastMCP's code,
  exercised only by a real MCP client; tool registration and delegation ARE
  unit-tested)
- `binex/__main__.py` (two-line delegation to `cli.main`)
- `scheduler/engine.py::start()` (signal handlers + sleep loop; `_tick`,
  rescan/skip logic and `_run_workflow` are unit-tested)

**Transport-only branches** — reachable only through a real network client:

- the `CancelledError` branch of the SSE generator in `ui/api/events.py`
  (client disconnect)

**Environment-gated paths** — dead in the default test environment because an
optional dependency is absent; not dead in the matrix:

- `telemetry.py` OTel emission paths (require the `telemetry` extra)
- protobuf decode paths in `importers/collector.py` (require
  `opentelemetry-proto`; the 415 gate is tested)
- `observe_crewai.py` attribution paths — covered by the dedicated
  `observe-crewai` CI job that installs `crewai`; only a local-environment
  boundary

Anything not listed here is expected to be tested; a new zero in the coverage
report is either a bug in the test setup or a candidate for this list — with
its one-sentence justification written down, not silently accepted.
