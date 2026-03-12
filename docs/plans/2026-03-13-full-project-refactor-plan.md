# Full Project Refactor — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce complexity, split mega-files, separate UI from logic across the entire Binex codebase.

**Architecture:** Bottom-up refactoring in 5 layers. Each task is atomic with tests verified before/after. Structural splits preserve all public APIs via re-exports in `__init__` or original module.

**Tech Stack:** Python 3.11+, click, pydantic 2.0+, rich, litellm, pytest

**Baseline metrics:**
- 20 functions with CC >15 (complexipy)
- 1 file with MI=0.00 (explore.py)
- 1204 tests passing, 0 ruff errors

---

## Task 1: Layer 1-2 — stores/sqlite.py migration error handling

**Files:**
- Modify: `src/binex/stores/backends/sqlite.py:75-89`
- Test: `tests/unit/test_qa_phase4_core.py` (existing)

**Step 1: Read current migration code and understand silent catches**

Read `src/binex/stores/backends/sqlite.py` lines 75-89 to see the exact try/except blocks.

**Step 2: Add logging to silent exception catches**

Replace bare `except` clauses with `except Exception as exc: logger.warning(...)` to make migration errors visible without breaking existing behavior.

```python
import logging

logger = logging.getLogger(__name__)
```

In each migration try/except, change from:
```python
except Exception:
    pass
```
to:
```python
except Exception as exc:
    logger.debug("Migration already applied or failed: %s", exc)
```

**Step 3: Run tests to verify no regression**

Run: `pytest tests/ -x -q`
Expected: All 1204+ tests pass

**Step 4: Run ruff**

Run: `ruff check src/binex/stores/`
Expected: 0 errors

**Step 5: Commit**

```bash
git add src/binex/stores/backends/sqlite.py
git commit -m "refactor(sqlite): add logging to silent migration catches"
```

---

## Task 2: Layer 3 — Extract budget logic from orchestrator

**Files:**
- Create: `src/binex/runtime/budget.py`
- Modify: `src/binex/runtime/orchestrator.py`
- Test: existing tests via `pytest tests/ -x -q`

**Step 1: Create `runtime/budget.py` with extracted functions**

Extract these from `orchestrator.py`:
- `get_effective_policy(spec)` (lines 29-33)
- `get_node_max_cost(node, spec, accumulated)` (lines 36-46)
- `check_batch_budget(spec, accumulated_cost)` (lines 143-155) — was static method
- `skip_all_remaining(scheduler, initial_ready)` (lines 157-169) — was static method

```python
"""Budget management utilities for workflow execution."""
from __future__ import annotations

import logging
from binex.graph.scheduler import Scheduler
from binex.models.workflow import WorkflowSpec, NodeSpec

logger = logging.getLogger(__name__)


def get_effective_policy(spec: WorkflowSpec) -> str:
    """Return budget policy ('stop' or 'warn') for a workflow."""
    if spec.budget and spec.budget.policy:
        return spec.budget.policy
    return "stop"


def get_node_max_cost(
    node: NodeSpec,
    spec: WorkflowSpec,
    accumulated_workflow_cost: float,
) -> float | None:
    """Calculate effective max cost for a node."""
    if node.budget and node.budget.max_cost is not None:
        return node.budget.max_cost
    if spec.budget and spec.budget.max_cost:
        return spec.budget.max_cost - accumulated_workflow_cost
    return None


def check_batch_budget(spec: WorkflowSpec, accumulated_cost: float) -> str | None:
    """Check budget before scheduling a batch. Returns 'stop', 'warn', or None."""
    if not spec.budget or spec.budget.max_cost <= 0:
        return None
    if accumulated_cost <= spec.budget.max_cost:
        return None
    return spec.budget.policy


def skip_all_remaining(scheduler: Scheduler, initial_ready: list[str]) -> None:
    """Skip all ready and subsequently unblocked nodes."""
    for node_id in initial_ready:
        scheduler.mark_skipped(node_id)
    while not scheduler.is_complete() and not scheduler.is_blocked():
        remaining = scheduler.ready_nodes()
        if not remaining:
            break
        for node_id in remaining:
            scheduler.mark_skipped(node_id)
```

**Step 2: Update orchestrator.py to import from budget.py**

Replace the 4 functions/methods with imports:
```python
from binex.runtime.budget import (
    get_effective_policy,
    get_node_max_cost,
    check_batch_budget,
    skip_all_remaining,
)
```

Remove the standalone functions `get_effective_policy` and `get_node_max_cost` (lines 29-46).
Convert `_check_batch_budget` and `_skip_all_remaining` static methods to delegate:
- Replace `self._check_batch_budget(...)` calls with `check_batch_budget(...)`
- Replace `self._skip_all_remaining(...)` calls with `skip_all_remaining(...)`

Remove the static method definitions from the class.

**Step 3: Search all usages of moved functions**

Run: `grep -r "get_effective_policy\|get_node_max_cost\|_check_batch_budget\|_skip_all_remaining" src/`

Update any external imports (e.g., if tests import `from binex.runtime.orchestrator import get_effective_policy`).

**Step 4: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

**Step 5: Run ruff + complexipy**

Run: `ruff check src/binex/runtime/`
Run: `complexipy src/binex/runtime/ --max-complexity-allowed 15`

**Step 6: Commit**

```bash
git add src/binex/runtime/budget.py src/binex/runtime/orchestrator.py
git commit -m "refactor(runtime): extract budget logic to budget.py"
```

---

## Task 3: Layer 3 — Extract back-edge logic from orchestrator

**Files:**
- Create: `src/binex/runtime/back_edge.py`
- Modify: `src/binex/runtime/orchestrator.py`

**Step 1: Create `runtime/back_edge.py`**

Extract `_evaluate_back_edge` (lines 483-525) and `evaluate_when` (lines 530-553):

```python
"""Back-edge evaluation for review loops."""
from __future__ import annotations

import re
from collections.abc import Callable

import click

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact
from binex.models.workflow import WorkflowSpec

_WHEN_RE = re.compile(
    r"^\$\{node\.([a-zA-Z_][\w]*)\.output\}\s*(==|!=)\s*(.+)$"
)


def evaluate_when(
    when_str: str,
    node_artifacts: dict[str, list[Artifact]],
) -> bool:
    """Evaluate a when-condition string against node artifacts."""
    m = _WHEN_RE.match(when_str.strip())
    if not m:
        return False
    ref_node, op, expected = m.group(1), m.group(2), m.group(3).strip().strip("'\"")
    arts = node_artifacts.get(ref_node, [])
    actual = arts[-1].content.strip() if arts else ""
    if op == "==":
        return actual == expected
    return actual != expected


async def evaluate_back_edge(
    spec: WorkflowSpec,
    scheduler: Scheduler,
    dag: DAG,
    node_id: str,
    node_artifacts: dict[str, list[Artifact]],
    node_artifacts_history: dict[str, list[list[Artifact]]],
    pending_feedback: dict[str, list[Artifact]],
) -> None:
    """Evaluate back_edge after successful node execution."""
    back_edge = spec.nodes[node_id].back_edge
    if back_edge is None:
        return

    if not evaluate_when(back_edge.when, node_artifacts):
        return

    iteration = scheduler.get_execution_count(node_id)
    if iteration >= back_edge.max_iterations:
        decision = click.prompt(
            f"  Max iterations ({back_edge.max_iterations}) reached for '{node_id}'. "
            f"[a]ccept last draft · [f]ail workflow",
            type=click.Choice(["a", "f"]),
            show_choices=False,
        )
        if decision == "f":
            scheduler.mark_failed(node_id)
        return

    feedback_arts = [
        a for a in node_artifacts.get(node_id, [])
        if a.type == "feedback"
    ]
    if feedback_arts:
        pending_feedback[back_edge.target] = feedback_arts

    reset_nodes = scheduler.reset_chain(back_edge.target, node_id, dag)
    for nid in reset_nodes:
        old = node_artifacts.pop(nid, [])
        node_artifacts_history.setdefault(nid, []).append(old)
```

**Step 2: Update orchestrator.py**

Replace `evaluate_when` and `_evaluate_back_edge` with imports from `back_edge.py`.
Pass `self._pending_feedback` as parameter to `evaluate_back_edge()`.

**Step 3: Search all usages**

Run: `grep -r "evaluate_when\|_evaluate_back_edge" src/ tests/`

Update any external imports.

**Step 4: Run tests**

Run: `pytest tests/ -x -q`

**Step 5: Commit**

```bash
git add src/binex/runtime/back_edge.py src/binex/runtime/orchestrator.py
git commit -m "refactor(runtime): extract back-edge logic to back_edge.py"
```

---

## Task 4: Layer 3 — Extract shared node execution logic

**Files:**
- Create: `src/binex/runtime/_node_executor.py`
- Modify: `src/binex/runtime/orchestrator.py`
- Modify: `src/binex/runtime/replay.py`

**Step 1: Identify shared pattern**

Both `Orchestrator._execute_node` (lines 290-351) and `ReplayEngine._execute_node` (lines 208-279) share:
1. Collect input artifacts from dependencies
2. Create TaskNode
3. Dispatch and collect results
4. Store artifacts
5. Update scheduler status
6. Record ExecutionRecord

Differences:
- Orchestrator has: budget checks, retry loop, back-edge evaluation, pending feedback
- Replay has: agent swaps, no budget, no retries, no back-edges

**Step 2: Extract shared helpers**

Create `_node_executor.py` with shared utilities:

```python
"""Shared node execution helpers for orchestrator and replay."""
from __future__ import annotations

import time
import uuid

from binex.graph.dag import DAG
from binex.models.artifact import Artifact
from binex.models.execution import ExecutionRecord
from binex.models.task import TaskStatus
from binex.stores.execution_store import ExecutionStore


def now_ms() -> int:
    """Current monotonic time in milliseconds."""
    return int(time.monotonic() * 1000)


def collect_input_artifacts(
    dag: DAG,
    node_id: str,
    node_artifacts: dict[str, list[Artifact]],
    extra: list[Artifact] | None = None,
) -> list[Artifact]:
    """Collect input artifacts from upstream dependencies."""
    inputs: list[Artifact] = []
    for dep_id in dag.dependencies(node_id):
        inputs.extend(node_artifacts.get(dep_id, []))
    if extra:
        inputs.extend(extra)
    return inputs


async def record_execution(
    execution_store: ExecutionStore,
    *,
    run_id: str,
    node_id: str,
    agent_id: str,
    status: TaskStatus | str,
    input_artifacts: list[Artifact],
    output_artifacts: list[Artifact],
    latency_ms: int,
    trace_id: str,
    error: str | None,
) -> None:
    """Create and store an ExecutionRecord."""
    record = ExecutionRecord(
        id=f"rec_{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        task_id=node_id,
        agent_id=agent_id,
        status=status,
        input_artifact_refs=[a.id for a in input_artifacts],
        output_artifact_refs=[a.id for a in output_artifacts],
        latency_ms=latency_ms,
        trace_id=trace_id,
        error=error,
    )
    await execution_store.record(record)
```

**Step 3: Update orchestrator.py to use shared helpers**

Replace `_now_ms()` with `from binex.runtime._node_executor import now_ms`.
Replace inline `ExecutionRecord(...)` construction + `await self.execution_store.record(record)` with `await record_execution(...)`.
Replace input artifact collection loop with `collect_input_artifacts(...)`.

**Step 4: Update replay.py to use shared helpers**

Same replacements as orchestrator. Replace `int(time.monotonic() * 1000)` with `now_ms()`.

**Step 5: Run tests**

Run: `pytest tests/ -x -q`

**Step 6: Commit**

```bash
git add src/binex/runtime/_node_executor.py src/binex/runtime/orchestrator.py src/binex/runtime/replay.py
git commit -m "refactor(runtime): extract shared node execution helpers"
```

---

## Task 5: Layer 4 — Extract shared content comparison from bisect+diff

**Files:**
- Create: `src/binex/trace/_compare.py`
- Modify: `src/binex/trace/bisect.py`
- Modify: `src/binex/trace/diff.py`

**Step 1: Create `trace/_compare.py` with shared content helpers**

Both files have identical logic for fetching artifact content and computing similarity.

```python
"""Shared content comparison utilities for trace analysis."""
from __future__ import annotations

import difflib

from binex.stores.artifact_store import ArtifactStore


async def get_artifact_content(
    art_store: ArtifactStore,
    artifact_refs: list[str],
) -> str:
    """Fetch and concatenate content from artifact references."""
    parts: list[str] = []
    for ref in artifact_refs:
        art = await art_store.get(ref)
        if art:
            parts.append(str(art.content))
    return "\n".join(parts)


def content_similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two strings (0.0 to 1.0)."""
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()
```

**Step 2: Update bisect.py**

Replace `_get_content()` (lines 210-219) with import: `from binex.trace._compare import get_artifact_content`.
Replace inline `SequenceMatcher` calls in `_check_content_divergence` and `_check_content_similarity` with `content_similarity()`.

**Step 3: Update diff.py**

Replace `_get_artifact_content()` (lines 12-21) with import: `from binex.trace._compare import get_artifact_content`.
Replace `_content_similarity()` (lines 24-30) with import: `from binex.trace._compare import content_similarity`.

**Step 4: Run tests**

Run: `pytest tests/ -x -q`

**Step 5: Commit**

```bash
git add src/binex/trace/_compare.py src/binex/trace/bisect.py src/binex/trace/diff.py
git commit -m "refactor(trace): extract shared content comparison to _compare.py"
```

---

## Task 6: Layer 4 — Split bisect.py into 3 modules

**Files:**
- Create: `src/binex/trace/bisect_format.py`
- Create: `src/binex/trace/bisect_compare.py`
- Modify: `src/binex/trace/bisect.py`

**Step 1: Create `bisect_format.py` with serialization functions**

Move from bisect.py:
- `divergence_to_dict()` (lines 222-244)
- `bisect_report_to_dict()` (lines 501-549)

**Step 2: Create `bisect_compare.py` with comparison functions**

Move from bisect.py:
- `_check_status_divergence()` (lines 130-152)
- `_check_content_divergence()` (lines 155-189)
- `_compare_node()` (lines 350-380)
- `_determine_comp_status()` (lines 383-391)
- `_check_content_similarity()` (lines 394-417)
- `_generate_content_diff()` (lines 420-447)
- `_make_divergence()` (lines 450-465)

**Step 3: Update bisect.py to import from new modules**

bisect.py keeps:
- Dataclasses: `DivergencePoint`, `NodeComparison`, `ErrorContext`, `BisectReport`
- Core functions: `find_divergence()`, `bisect_report()`
- Helpers: `_get_upstream()`, `_load_and_validate_runs()`, `_build_node_map()`, `_build_error_context()`, `_ordered_task_ids()`

Re-export from bisect.py `__init__` style for backward compat:
```python
from binex.trace.bisect_format import divergence_to_dict, bisect_report_to_dict
from binex.trace.bisect_compare import (
    _check_status_divergence, _check_content_divergence,
)
```

**Step 4: Search all external usages**

Run: `grep -r "from binex.trace.bisect import\|from binex.trace import bisect" src/ tests/`

Ensure all imports still resolve.

**Step 5: Run tests**

Run: `pytest tests/ -x -q`

**Step 6: Commit**

```bash
git add src/binex/trace/bisect.py src/binex/trace/bisect_format.py src/binex/trace/bisect_compare.py
git commit -m "refactor(trace): split bisect.py into core/compare/format modules"
```

---

## Task 7: Layer 4 — Remove duplicated topo_sort from trace_rich.py

**Files:**
- Modify: `src/binex/trace/trace_rich.py`

**Step 1: Replace `_topo_sort` with DAG.topological_order**

The `_topo_sort()` function at lines 356-379 reimplements Kahn's algorithm. Replace with:

```python
from binex.graph.dag import DAG
```

At the call site (line ~125 in `format_trace_graph_rich`), build a DAG from nodes/edges and call `topological_order()`.

Note: Check if `_topo_sort` expects `dict[str, str]` for nodes (node_id -> label) vs `DAG.topological_order()` which returns `list[str]`. Adapt the call accordingly — may need to build a minimal WorkflowSpec or use DAG directly.

If the adaptation is non-trivial (different input formats), keep `_topo_sort` but add a comment noting the duplication. Don't over-engineer.

**Step 2: Run tests**

Run: `pytest tests/ -x -q`

**Step 3: Commit**

```bash
git add src/binex/trace/trace_rich.py
git commit -m "refactor(trace_rich): use DAG.topological_order instead of local topo_sort"
```

---

## Task 8: Layer 4 — diagnose.py constants extraction

**Files:**
- Modify: `src/binex/trace/diagnose.py`

**Step 1: Extract magic numbers to named constants**

```python
LATENCY_ANOMALY_THRESHOLD = 3.0  # ratio above median
MIN_SAMPLES_FOR_ANOMALY = 3      # minimum records needed
```

Replace `if ratio > 3.0:` with `if ratio > LATENCY_ANOMALY_THRESHOLD:`.

**Step 2: Run tests**

Run: `pytest tests/ -x -q`

**Step 3: Commit**

```bash
git add src/binex/trace/diagnose.py
git commit -m "refactor(diagnose): extract magic numbers to named constants"
```

---

## Task 9: Layer 5 — Split explore.py into 6 modules

This is the largest and most impactful task. Execute carefully with migration checklist.

**Files:**
- Create: `src/binex/cli/explore_utils.py`
- Create: `src/binex/cli/explore_browser.py`
- Create: `src/binex/cli/explore_ui.py`
- Create: `src/binex/cli/explore_actions.py`
- Create: `src/binex/cli/explore_replay.py`
- Modify: `src/binex/cli/explore.py`

**Step 1: Create `explore_utils.py` (~50 lines)**

Move utility functions that have no internal explore dependencies:
- `_short_id()` (lines 19-21)
- `_time_ago()` (lines 24-42)
- `_preview()` (lines 46-54)

```python
"""Shared utilities for explore dashboard."""
from __future__ import annotations
from datetime import datetime, UTC


def short_id(run_id: str) -> str:
    """Shorten a run ID for display."""
    return run_id[:12] if len(run_id) > 12 else run_id


def time_ago(dt: datetime) -> str:
    """Format a datetime as relative time string."""
    # ... exact code from lines 24-42


def preview(content: str | None, max_len: int = 50) -> str:
    """Truncate content for preview display."""
    # ... exact code from lines 46-54
```

**Step 2: Create `explore_browser.py` (~100 lines)**

Move run browsing functions:
- `_browse_runs()` (lines 87-109)
- `_render_runs_rich()` (lines 112-133)
- `_render_runs_plain()` (lines 136-147)
- `_select_run()` (lines 150-165)

Import `short_id`, `time_ago` from `explore_utils`.

**Step 3: Create `explore_ui.py` (~400 lines)**

Move all rendering/display functions:
- `_render_dashboard()` (lines 274-283)
- `_render_dashboard_rich()` (lines 286-333)
- `_render_dashboard_plain()` (lines 336-360)
- `_print_dashboard_menu()` (lines 363-385)
- `_wait_for_enter()` (lines 388-393)
- `_wait_for_enter_or_preview()` (lines 396-408)
- `_show_full_preview()` (lines 411-438)
- `_print_artifacts_table()` (lines 602-626)
- `_show_artifact_detail()` (lines 629-663)
- `_show_lineage()` (lines 666-696)
- `_render_node_list_rich()` (lines 742-759)
- `_render_node_list_plain()` (lines 762-768)
- `_render_node_rich()` (lines 771-827)
- `_render_node_plain()` (lines 830-845)
- `_render_diagnose_rich()` (lines 920-964)
- `_render_diagnose_plain()` (lines 967-984)

**Step 4: Create `explore_actions.py` (~300 lines)**

Move action handler functions:
- `_action_trace()` (lines 445-467)
- `_trace_node_drill_down()` (lines 470-488)
- `_action_graph()` (lines 491-512)
- `_enrich_graph_from_workflow()` (lines 515-527)
- `_merge_spec_into_graph()` (lines 530-537)
- `_action_debug()` (lines 540-557)
- `_action_cost()` (lines 560-566)
- `_action_artifacts()` (lines 569-599)
- `_action_node()` (lines 699-739)
- `_action_diagnose()` (lines 904-917)
- `_action_diff()` (lines 987-1007)
- `_action_bisect()` (lines 1010-1033)
- `_pick_other_run()` (lines 848-901)

Import rendering functions from `explore_ui`.

**Step 5: Create `explore_replay.py` (~200 lines)**

Move replay sub-flow:
- `_action_replay()` (lines 1036-1064)
- `_replay_select_start_node()` (lines 1067-1099)
- `_replay_collect_agent_swaps()` (lines 1102-1125)
- `_render_swap_hint()` (lines 1128-1153)
- `_replay_select_workflow()` (lines 1156-1171)
- `_replay_confirm()` (lines 1174-1202)
- `_replay_execute()` (lines 1205-1247)

**Step 6: Update `explore.py` to be the thin coordinator (~150 lines)**

Keep only:
- `_get_stores()` (lines 14-16)
- `explore_cmd()` (lines 57-68)
- `_explore()` (lines 71-84)
- `_dashboard()` (lines 168-203)
- `_dispatch_action()` (lines 206-245)
- `_dispatch_node()` (lines 248-255)
- `_dispatch_replay()` (lines 258-271)

Import everything else from the new modules.

**Step 7: MIGRATION CHECKLIST — verify all internal references**

Run:
```bash
grep -rn "from binex.cli.explore import\|from binex.cli import explore\|binex.cli.explore\." src/ tests/
```

Ensure every external reference still resolves. Key consumers:
- `src/binex/cli/main.py` — imports `explore_cmd`
- Tests that patch `binex.cli.explore._get_stores`

**Step 8: Run tests**

Run: `pytest tests/ -x -q`

**Step 9: Run complexity check**

Run: `complexipy src/binex/cli/explore*.py --max-complexity-allowed 15`
Run: `radon mi src/binex/cli/explore*.py -s`

**Step 10: Commit**

```bash
git add src/binex/cli/explore*.py
git commit -m "refactor(explore): split 1247-line mega-file into 6 focused modules"
```

---

## Task 10: Layer 5 — Extract CLI bisect formatting

**Files:**
- Create: `src/binex/cli/bisect_format.py`
- Modify: `src/binex/cli/bisect.py`

**Step 1: Move formatting helpers to `bisect_format.py`**

Move from `cli/bisect.py`:
- `_content_preview()` (lines 22-29)
- `_describe_change()` (lines 32-40)
- `_format_latency()` (lines 43-51)
- `_node_icon()` (lines 75-77)
- `_node_word()` (lines 80-85)
- `_print_node_details_plain()` (lines 229-267)
- `_extract_preview()` (lines 270-281)
- `_print_footer_plain()` (lines 284-291)
- `_render_verdict_rich()` (lines 314-346)
- `_format_diff_line_rich()` (lines 349-357)
- `_render_footer_rich()` (lines 360-373)

`cli/bisect.py` keeps:
- `_get_stores()`, `bisect_cmd()`, `_run_bisect()`
- `_print_plain()`, `_print_rich()` — but these call extracted formatting helpers

**Step 2: Update imports in bisect.py**

```python
from binex.cli.bisect_format import (
    _content_preview, _describe_change, _format_latency,
    _node_icon, _node_word, _print_node_details_plain,
    _extract_preview, _print_footer_plain,
    _render_verdict_rich, _format_diff_line_rich, _render_footer_rich,
)
```

**Step 3: Update explore.py if it imports from cli/bisect**

Check: `grep -rn "_print_rich\|_print_plain" src/binex/cli/explore`
These should still be in `cli/bisect.py`, so no change needed.

**Step 4: Run tests**

Run: `pytest tests/ -x -q`

**Step 5: Commit**

```bash
git add src/binex/cli/bisect.py src/binex/cli/bisect_format.py
git commit -m "refactor(cli/bisect): extract formatting helpers to bisect_format.py"
```

---

## Task 11: Layer 5 — Reduce CC in cost.py, dev.py, doctor.py

**Files:**
- Modify: `src/binex/cli/cost.py`
- Modify: `src/binex/cli/dev.py`
- Modify: `src/binex/cli/doctor.py`

**Step 1: cost.py — Extract method from `print_cost_text` (CC=21)**

Identify the longest if/elif chains or nested blocks and extract into helper functions. Typical pattern: extract per-node rendering into `_render_node_cost_line()`.

**Step 2: cost.py — Extract method from `_cost_history` (CC=22)**

Extract formatting logic for cost history entries.

**Step 3: dev.py — Extract checks from `dev_cmd` (CC=23)**

`dev_cmd` is a long sequential function. Extract:
- `_start_services()` — docker-compose up logic
- `_stop_services()` — docker-compose down logic
- `_show_status()` — health check display

**Step 4: doctor.py — Extract checks from `doctor_cmd` (CC=20)**

`doctor_cmd` runs sequential checks. Extract into a data-driven approach:

```python
_CHECKS = [
    ("Python", _check_binary, "python3"),
    ("Docker", _check_docker_running, None),
    # ...
]
```

Then loop:
```python
for name, check_fn, arg in _CHECKS:
    result = check_fn(arg) if arg else check_fn()
    results.append((name, result))
```

**Step 5: Run tests after each file change**

Run: `pytest tests/ -x -q`

**Step 6: Verify complexity**

Run: `complexipy src/binex/cli/cost.py src/binex/cli/dev.py src/binex/cli/doctor.py --max-complexity-allowed 15`
Expected: 0 functions above threshold

**Step 7: Commit**

```bash
git add src/binex/cli/cost.py src/binex/cli/dev.py src/binex/cli/doctor.py
git commit -m "refactor(cli): reduce CC in cost.py, dev.py, doctor.py to <15"
```

---

## Task 12: Layer 5 — Move prompt_roles.py to YAML data files

**Files:**
- Create: `src/binex/prompts/roles/*.yaml` (one per category or one big file)
- Modify: `src/binex/cli/prompt_roles.py`

**Step 1: Create YAML structure**

Create `src/binex/prompts/roles/` directory. Export existing `ROLES` list to YAML:

```yaml
# src/binex/prompts/roles/roles.yaml
- name: analyst
  category: analysis
  description: "Data analysis agent"
  system_prompt: |
    You are a data analyst...
  tags: [analysis, data]
# ... all roles
```

**Step 2: Rewrite `prompt_roles.py` as thin loader (~50 lines)**

```python
"""Prompt role templates — loaded from YAML data files."""
from __future__ import annotations

import importlib.resources
from dataclasses import dataclass
from pathlib import Path

import yaml

# ... PromptRole dataclass stays
# ... CATEGORY_ORDER, CATEGORY_ICONS stay as constants
# ... ROLES loaded from YAML:

def _load_roles() -> list[PromptRole]:
    """Load role definitions from bundled YAML."""
    roles_path = Path(__file__).parent.parent / "prompts" / "roles" / "roles.yaml"
    with open(roles_path) as f:
        data = yaml.safe_load(f)
    return [PromptRole(**item) for item in data]

ROLES: list[PromptRole] = _load_roles()

def get_role(name: str) -> PromptRole | None:
    return next((r for r in ROLES if r.name == name), None)

def get_roles_by_category(category: str) -> list[PromptRole]:
    return [r for r in ROLES if r.category == category]
```

**Step 3: Verify API preserved**

Run: `grep -rn "from binex.cli.prompt_roles import\|prompt_roles\." src/ tests/`

Ensure all existing imports still work: `get_role`, `get_roles_by_category`, `ROLES`, `CATEGORY_ORDER`, `CATEGORY_ICONS`, `TEMPLATE_CATEGORIES`.

**Step 4: Run tests**

Run: `pytest tests/ -x -q`

**Step 5: Commit**

```bash
git add src/binex/prompts/roles/ src/binex/cli/prompt_roles.py
git commit -m "refactor(prompts): move role templates from Python dict to YAML data files"
```

---

## Task 13: Layer 5 — Extract run progress wrappers

**Files:**
- Create: `src/binex/cli/run_progress.py`
- Modify: `src/binex/cli/run.py`
- Modify: `src/binex/cli/hello.py`

**Step 1: Create `run_progress.py` with shared progress wrappers**

Move `_install_verbose_wrapper` and `_install_live_wrapper` (or their equivalents) to a shared module. Both `run.py` and `hello.py` implement similar orchestrator monkey-patching for progress display.

**Step 2: Update run.py and hello.py to import from run_progress.py**

**Step 3: Run tests**

Run: `pytest tests/ -x -q`

**Step 4: Commit**

```bash
git add src/binex/cli/run_progress.py src/binex/cli/run.py src/binex/cli/hello.py
git commit -m "refactor(cli): extract shared progress wrappers to run_progress.py"
```

---

## Task 14: Layer 5 — Remove start.py re-exports

**Files:**
- Modify: `src/binex/cli/start.py`
- Modify: any tests that import via `start.py`

**Step 1: Identify all re-exports**

Lines 24-59 of `start.py` re-export ~25 functions from sub-modules.

**Step 2: Find test imports that use re-exports**

Run: `grep -rn "from binex.cli.start import" tests/`

**Step 3: Update test imports to point directly to sub-modules**

E.g., change `from binex.cli.start import _configure_node` to `from binex.cli.start_config import _configure_node`.

**Step 4: Remove re-export lines from start.py**

**Step 5: Run tests**

Run: `pytest tests/ -x -q`

**Step 6: Commit**

```bash
git add src/binex/cli/start.py tests/
git commit -m "refactor(cli/start): remove circular re-exports, tests import directly"
```

---

## Task 15: Layer 5 — Remaining CC reduction

**Files:**
- Modify: various CLI files with CC >15

**Step 1: Run complexipy to find remaining violations**

Run: `complexipy src/binex/ --max-complexity-allowed 15`

**Step 2: For each function with CC >15, apply extract-method pattern**

Typical approach:
- Long if/elif → extract branches to helper functions
- Nested loops → extract inner loop to helper
- Complex conditionals → extract to named boolean variables

**Step 3: Run tests after each file**

Run: `pytest tests/ -x -q`

**Step 4: Final validation**

Run:
```bash
complexipy src/binex/ --max-complexity-allowed 15
radon mi src/binex/ -s -n C
ruff check src/
pytest tests/ -x -q
```

Expected:
- 0 functions above CC 15
- 0 files with MI grade C
- 0 ruff errors
- All tests pass

**Step 5: Commit**

```bash
git add src/
git commit -m "refactor: reduce all remaining functions to CC <15"
```

---

## Execution Summary

| Task | Layer | Description | Risk | Est. Commits |
|------|-------|-------------|------|-------------|
| 1 | 1-2 | sqlite migration logging | Low | 1 |
| 2 | 3 | Extract budget.py | Medium | 1 |
| 3 | 3 | Extract back_edge.py | Medium | 1 |
| 4 | 3 | Shared _node_executor.py | Medium | 1 |
| 5 | 4 | Shared _compare.py | Low | 1 |
| 6 | 4 | Split bisect.py (trace) | Medium | 1 |
| 7 | 4 | Remove dupe topo_sort | Low | 1 |
| 8 | 4 | diagnose.py constants | Low | 1 |
| 9 | 5 | **Split explore.py** | **High** | 1 |
| 10 | 5 | Extract bisect formatting | Medium | 1 |
| 11 | 5 | CC reduction: cost/dev/doctor | Medium | 1 |
| 12 | 5 | prompt_roles → YAML | Medium | 1 |
| 13 | 5 | Shared run_progress.py | Low | 1 |
| 14 | 5 | Remove start.py re-exports | Low | 1 |
| 15 | 5 | Remaining CC reduction | Medium | 1 |

**Total: 15 tasks, ~15 commits**
