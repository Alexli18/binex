# QA Test Plan v3: Budget & Cost Tracking

**Project:** Binex — debuggable runtime for A2A agents
**Branch:** 007-budget-cost-tracking
**Date:** 2026-03-10
**QA Engineer:** Claude (AI-assisted)
**Previous QA:** v2 (branch 004-cli-dx, 125 test cases, 870 tests)

---

## 1. Baseline

| Metric | Value |
|--------|-------|
| Total tests | 1158 (all passing) |
| Lint | ruff clean (0 errors) |
| Known issues | 0 failing tests |
| Previous QA bugs | 2 found and fixed (v1), 0 new (v2) |
| New source files | 2 (cost.py model, cost.py CLI) |
| Modified source files | 16 |

---

## 2. Scope

### In scope
- **Cost Models** — CostRecord, BudgetConfig, NodeCostHint, RunCostSummary, ExecutionResult
- **Adapter Changes** — All 4 adapters (LLM, A2A, Local, Human) return ExecutionResult with cost
- **Store Changes** — cost_records table, record_cost(), list_costs(), get_run_cost_summary()
- **Orchestrator** — Cost accumulation, budget enforcement (stop/warn policies)
- **Replay Engine** — Cost recording for re-executed nodes
- **CLI** — `binex cost show/history`, run output cost/budget info
- **Dispatcher** — Backward-compatible ExecutionResult wrapping
- **Migration** — SQLite ALTER TABLE for total_cost column

### Out of scope
- Performance/load testing
- LLM output quality (non-deterministic)
- Third-party library internals (litellm, aiosqlite)

---

## 3. Existing Test Coverage

| Module | Test File | Tests | Assessment |
|--------|-----------|-------|------------|
| models/cost.py | test_cost_models.py | 38 | HIGH |
| stores (sqlite+memory) | test_cost_store.py | 30 | HIGH |
| adapters (all 4) | test_cost_adapters.py | 8 | MEDIUM |
| cli/cost.py + run.py | test_cost_cli.py | 12 | MEDIUM |
| orchestrator budget | test_budget_enforcement.py | 14 | HIGH |

**Total existing (feature):** ~102 tests

---

## 4. Test Categories & Cases

### CAT-1: Cost Models (38 tests) — EXISTING
File: `test_cost_models.py`
Coverage: CostRecord validation, BudgetConfig, NodeCostHint, RunCostSummary, ExecutionResult, WorkflowSpec budget, NodeSpec cost hint

### CAT-2: Cost Storage (30 tests) — EXISTING
File: `test_cost_store.py`
Coverage: SQLite/memory record_cost, list_costs, get_run_cost_summary, total_cost column, cross-store consistency

### CAT-3: Adapter Cost Extraction (8 tests) — EXISTING
File: `test_cost_adapters.py`
Coverage: LLM (with/without usage), A2A (with/without cost), Local, Human adapters

### CAT-4: Budget Enforcement (14 tests) — EXISTING
File: `test_budget_enforcement.py`
Coverage: Stop/warn policies, no budget, edge cases (exact equal, zero cost), cost recording, accumulation

### CAT-5: CLI Cost Commands (12 tests) — EXISTING
File: `test_cost_cli.py`
Coverage: cost show (text/JSON), cost history (text/JSON), run output cost/budget/over_budget

### CAT-6: QA Gap Coverage (46 tests) — NEW
File: `test_qa_v3_cost_tracking.py`

| ID | Test Case | Priority | Status |
|----|-----------|----------|--------|
| TC-GAP-001 | Dispatcher: legacy list[Artifact] → ExecutionResult wrap | P1 | PASS |
| TC-GAP-002 | Dispatcher: new adapter pass-through | P1 | PASS |
| TC-GAP-003 | Dispatcher: retry preserves ExecutionResult | P2 | PASS |
| TC-GAP-004 | Replay engine records cost for re-executed nodes | P1 | PASS |
| TC-GAP-005 | RunSummary.skipped_nodes default=0 | P2 | PASS |
| TC-GAP-006 | RunSummary.skipped_nodes set value | P2 | PASS |
| TC-GAP-007 | RunSummary.total_cost default=0 | P2 | PASS |
| TC-GAP-008 | CLI run JSON includes budget fields | P1 | PASS |
| TC-GAP-009 | CLI run JSON omits budget when not set | P1 | PASS |
| TC-GAP-010 | A2A adapter zero cost from response | P2 | PASS |
| TC-GAP-011 | A2A adapter string cost conversion | P2 | PASS |
| TC-GAP-012 | Parallel nodes under budget all complete | P1 | PASS |
| TC-GAP-013 | Parallel nodes without budget tracked | P1 | PASS |
| TC-GAP-014 | SQLite double-init idempotent | P2 | PASS |
| TC-GAP-015 | SQLite cost_records table created | P1 | PASS |
| TC-GAP-016 | SQLite total_cost column migration | P1 | PASS |
| TC-GAP-017 | CLI cost group registered in main | P1 | PASS |
| TC-GAP-018 | CLI cost show --help | P2 | PASS |
| TC-GAP-019 | CLI cost history --help | P2 | PASS |
| TC-GAP-020 | Failed node: no cost record | P1 | PASS |
| TC-GAP-021 | Partial failure: only successful node costs | P1 | PASS |
| TC-GAP-022 | Memory store protocol compliance | P2 | PASS |
| TC-GAP-023 | SQLite store protocol compliance | P2 | PASS |
| TC-GAP-024 | Very small cost preserved | P2 | PASS |
| TC-GAP-025 | Very large cost preserved | P2 | PASS |
| TC-GAP-026 | Memory store float accumulation (0.1 * 10) | P1 | PASS |
| TC-GAP-027 | SQLite store float accumulation (0.1 * 10) | P1 | PASS |
| TC-GAP-028–032 | Model re-exports from binex.models | P2 | PASS |
| TC-GAP-033 | cost history: run not found error | P1 | PASS |
| TC-GAP-034 | cost show JSON with budget data | P2 | PASS |
| TC-GAP-035 | cost history JSON empty records | P2 | PASS |
| TC-GAP-036 | Budget from dict (YAML-like input) | P1 | PASS |
| TC-GAP-037 | Budget warn policy from dict default | P2 | PASS |
| TC-GAP-038 | Node cost hint from dict | P2 | PASS |
| TC-GAP-039 | Valid CostSource parametrized (5 values) | P2 | PASS |
| TC-GAP-040 | Invalid CostSource rejected | P1 | PASS |
| TC-GAP-041 | ExecutionResult has artifacts and cost | P2 | PASS |
| TC-GAP-042 | ExecutionResult serializable (model_dump) | P2 | PASS |

---

## 5. Quality Gates

| Gate | Target | Actual | Status |
|------|--------|--------|--------|
| Test Execution | 100% | 100% (46/46 new) | PASS |
| Pass Rate | >= 95% | 100% | PASS |
| P0 Bugs | 0 | 0 | PASS |
| P1 Bugs | <= 3 | 0 | PASS |
| Total Tests | >= 1200 | 1204 | PASS |
| Lint (ruff) | 0 errors | 0 | PASS |
| All 1158 existing tests | PASS | PASS | PASS |

---

## 6. Summary

- **Baseline**: 1158 tests
- **Final**: 1204 tests (+46 new QA tests)
- **New bugs found**: 0
- **Lint errors found**: 0
- **All quality gates**: PASSED
- **Feature assessment**: Well-implemented, comprehensive test coverage
