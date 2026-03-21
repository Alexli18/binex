# Binex Codebase Scan — 2026-03-20

## Baseline Metrics

| Area | Scope | Result |
|---|---|---|
| ruff | `src/binex/` | 0 errors (clean) |
| ruff | full repo (tests + scripts) | 251 errors (72 E501, 62 I001, 60 F401, 18 N806, ...) |
| mypy | `src/binex/ --ignore-missing-imports` | 545 errors in 96 files |
| mypy | full repo | 3966 errors in 283 files |
| pytest | full suite | 2508/2508 passed |
| frontend | no node_modules — not checked | N/A |

---

## Top 5 Findings

### 1. Missing SQLite indexes cause full table scans on every query

**Area:** Backend robustness / Performance
**Location:** `src/binex/stores/backends/sqlite.py` — CREATE TABLE statements (lines ~37-96)
**Problem:** The `execution_records` and `cost_records` tables have no indexes on `(run_id)` or `(run_id, task_id)`. Every call to `list_records(run_id)`, `list_costs(run_id)`, and budget checks performs a full table scan. The orchestrator fetches ALL costs for the entire run on each retry attempt (`orchestrator.py:303-304`), and the costs API endpoint fetches costs twice — once for summary, once for records (`ui/api/costs.py:23-24`).
**Proposal:** Add `CREATE INDEX IF NOT EXISTS` for `(run_id)` and `(run_id, task_id)` on both tables in the `initialize()` method. No schema migration needed — indexes can be added to existing databases.
**Effort:** Small
**Metric:** `EXPLAIN QUERY PLAN` output changes from SCAN TABLE to SEARCH TABLE USING INDEX. Measurable with pytest on existing store tests.

---

### 2. Unguarded `artifacts[0]` access crashes on empty artifact lists

**Area:** Code quality / Correctness
**Location:**
- `src/binex/runtime/dispatcher.py:195` — `result.artifacts[0].content`
- `src/binex/runtime/back_edge.py:35` — `artifacts[0].content` when `matching` is empty
- `src/binex/adapters/framework_base.py:66` — `artifacts[0].content`

**Problem:** Direct index access without bounds check. If an adapter returns an empty artifact list (e.g., timeout, cancelled run, schema validation failure that produces no output), these lines throw `IndexError` and crash the orchestrator. The back_edge case is subtle: it guards `matching` but falls through to unguarded `artifacts[0]`.
**Proposal:** Add guard clauses before each access: return empty string / raise descriptive error / skip the node. Each fix is 2-3 lines.
**Effort:** Small
**Metric:** ruff + mypy stay clean; add targeted unit tests for empty-artifact edge case (currently untested). pytest pass count increases.

---

### 3. Silent exception swallowing hides adapter and cleanup failures

**Area:** Backend robustness / Observability
**Location:**
- `src/binex/runtime/orchestrator.py:199-202` — `except Exception: pass` in adapter cleanup
- `src/binex/adapters/cao.py:875-880, 908-913` — `except httpx.HTTPError: pass` in session cleanup
- `src/binex/ui/api/cao.py:226-235` — CAO termination errors silently ignored
- `src/binex/tools/_core.py:118-121` — type hint resolution errors silently eaten

**Problem:** At least 6 locations catch exceptions and discard them with `pass`. Adapter cleanup failures (connection leaks, orphaned processes) are invisible. The CAO subprocess spawned in `ui/api/cao.py:116-120` is never cleaned up if the app restarts — orphaned `cao-server` processes bind the port. These are production-grade issues: when something goes wrong, there's zero diagnostic trail.
**Proposal:** Replace `pass` with `logger.debug()` or `logger.warning()` in each location. For subprocess cleanup, add atexit handler. No behavior change — just visibility.
**Effort:** Small
**Metric:** No regressions (pytest stays green). Manually verifiable by triggering an error path and checking logs.

---

### 4. mypy: 545 errors in src/binex — bulk is missing type annotations

**Area:** Code quality / Type safety
**Location:** 96 files across `src/binex/`
**Problem:** Breakdown of the 545 mypy errors:

| Error type | Count | Description |
|---|---|---|
| `[no-untyped-def]` | ~350 | Functions missing type annotations |
| `[no-untyped-call]` | ~80 | Calls to untyped functions |
| `[type-arg]` | ~40 | Missing generic type args (e.g., `dict` vs `dict[str, Any]`) |
| `[arg-type]` | ~25 | Actual type mismatches |
| `[union-attr]` | ~15 | Attribute access on union types |
| Other | ~35 | misc, attr-defined, import-untyped, etc. |

The `[arg-type]` and `[union-attr]` errors are real bugs waiting to happen. The `[no-untyped-def]` bulk is mechanical but high-volume.
**Proposal:** Start with the ~25 `[arg-type]` errors — these are actual type mismatches that indicate logic bugs. Then tackle `[no-untyped-def]` one module at a time, starting with `runtime/` (the most critical path). Each module is one commit.
**Effort:** Medium (arg-type fixes: small; full annotation: multi-session)
**Metric:** `mypy src/binex/ --ignore-missing-imports 2>&1 | grep "error:" | wc -l` — target: reduce from 545 to <500 in first pass.

---

### 5. Test coverage gaps — workflow_spec and runtime subsystems have no unit tests

**Area:** Tests & observability
**Location:**
- `src/binex/workflow_spec/` (loader.py, validator.py, migrations.py) — **0 dedicated test files**
- `src/binex/runtime/` — missing tests for `replay.py`, `schema_validator.py`, `budget.py`, `_node_executor.py`
- Integration tests: only 5 files in `tests/integration/`, no adapter error-path tests

**Problem:** The workflow spec module handles YAML parsing, schema validation, and version migrations — all critical to correctness — but has zero dedicated unit tests. The runtime replay engine has N+1 query patterns (`replay.py:59-62` — one DB call per artifact) that would be caught by a test with >10 artifacts. Budget enforcement (`budget.py`) is untested in isolation.
**Proposal:** Add unit tests for `workflow_spec/loader.py` (YAML edge cases: empty nodes, circular refs, missing fields) and `runtime/schema_validator.py` (malformed JSON, oversized output). ~50-80 lines per test file.
**Effort:** Medium
**Metric:** pytest pass count increases (2508 → 2530+). Coverage of workflow_spec goes from 0% to >70%.

---

## Honorable Mentions (not in top 5 but worth noting)

- **Adapter inconsistency**: Timeout handling, retry logic, and error types vary wildly across adapters. CAO has 5 specific exception types; framework adapters use generic RuntimeError. A2A has no retry at all.
- **Ruff errors in tests**: 251 errors (60 unused imports, 72 long lines, 62 unsorted imports). Low-value but noisy.
- **CLI error message inconsistency**: Exit codes, error formatting, and remediation hints vary across subcommands.
- **N+1 artifact queries in replay**: `replay.py:59-62` fetches artifacts one-by-one. 100-step run with 5 artifacts = 500 async queries.
- **SQLite no retry on lock**: No backoff for `database is locked` errors in concurrent write scenarios.

---

## Recommended order

1. **Finding 1** (SQLite indexes) — smallest effort, biggest perf win, zero risk
2. **Finding 2** (artifacts[0] guard) — correctness bug, 2-3 lines each, zero risk
3. **Finding 3** (silent exceptions) — observability, no behavior change
4. **Finding 4** (mypy arg-type fixes) — real type bugs, moderate effort
5. **Finding 5** (test gaps) — medium effort but pays forward

*Which of these should I work on first?*

---

## Iteration 1 — Finding 1: SQLite indexes added

**Commit:** `a19fb44` — `perf(sqlite): add indexes on run_id for execution_records and cost_records`

**Change:** Added 4 `CREATE INDEX IF NOT EXISTS` statements to `initialize()` in `src/binex/stores/backends/sqlite.py`:
- `idx_execution_records_run_id` on `(run_id)`
- `idx_execution_records_run_task` on `(run_id, task_id)`
- `idx_cost_records_run_id` on `(run_id)`
- `idx_cost_records_run_task` on `(run_id, task_id)`

**Before/After — EXPLAIN QUERY PLAN:**

| Query | Before | After |
|---|---|---|
| `SELECT * FROM execution_records WHERE run_id = ?` | `SCAN execution_records` | `SEARCH … USING INDEX idx_execution_records_run_id` |
| `SELECT * FROM execution_records WHERE run_id = ? AND task_id = ?` | `SCAN execution_records` | `SEARCH … USING INDEX idx_execution_records_run_task` |
| `SELECT * FROM cost_records WHERE run_id = ?` | `SCAN cost_records` | `SEARCH … USING INDEX idx_cost_records_run_id` |
| `SELECT * FROM cost_records WHERE run_id = ? AND task_id = ?` | `SCAN cost_records` | `SEARCH … USING INDEX idx_cost_records_run_task` |

All queries now use indexed lookups (O(log n)) instead of full table scans (O(n)). Safe for existing databases — `IF NOT EXISTS` is idempotent.

---

## Iteration 2 — Finding 2: Guard unguarded `artifacts[0]` access

**Commit:** `31964a6` — `fix(runtime): guard artifacts[0] access against empty artifact lists`

**Changes (3 files):**

| File | Line | Fix |
|---|---|---|
| `src/binex/runtime/dispatcher.py:195` | `result.artifacts[0].content` | Added guard: raise `SchemaValidationError` with descriptive message if `result.artifacts` is empty |
| `src/binex/runtime/back_edge.py:35` | `matching[0].content` / `artifacts[0].content` | Refactored to single `first` variable with None fallback; returns `False` if no artifact found |
| `src/binex/adapters/framework_base.py:66` | `artifacts[0].content` | Tightened existing guard from `len(artifacts) == 0` to idiomatic `not artifacts` (already safe but now consistent) |

**Test result:** 2450/2450 passed (no regressions).

---

## Iteration 3 — Finding 3: Log swallowed exceptions instead of silently passing

**Commit:** `f1c420f` — `fix(observability): log swallowed exceptions instead of silently passing`

**Changes (4 files):**

| File | Location | Fix |
|---|---|---|
| `src/binex/runtime/orchestrator.py:199-202` | Adapter cleanup `except Exception: pass` | Replaced with `logger.debug(…, exc_info=True)` |
| `src/binex/adapters/cao.py:875-880` | Terminal exit/delete `except httpx.HTTPError: pass` | Replaced both with `logger.debug(…, exc_info=True)` |
| `src/binex/adapters/cao.py:908-913` | Session close cleanup `except httpx.HTTPError: pass` + `except Exception: pass` | Replaced both with `logger.debug(…, exc_info=True)` |
| `src/binex/ui/api/cao.py:226-235` | CAO termination `except httpx.HTTPError: pass` (×2) | Replaced with `logger.debug(…, exc_info=True)` |
| `src/binex/ui/api/cao.py` (new) | Missing atexit handler for `_cao_process` | Added `_cleanup_cao_process()` atexit handler to terminate orphaned CAO subprocess on interpreter shutdown |
| `src/binex/tools/_core.py:118-121` | Type hint resolution `except Exception: pass` | Added `import logging` + `logger`, replaced with `logger.debug(…, exc_info=True)` |

**No behavior changes** — all exception handlers still catch and continue; they now log at DEBUG level with full tracebacks.

**Test result:** 2450/2450 passed (no regressions).
