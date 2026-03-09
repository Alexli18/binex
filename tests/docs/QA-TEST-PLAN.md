# QA Test Plan: Binex Runtime

**Project:** Binex — debuggable runtime for A2A agents
**Branch:** 003-debug-command
**Date:** 2026-03-08
**QA Engineer:** Claude (AI-assisted)

---

## 1. Baseline

| Metric | Value |
|--------|-------|
| Total tests | 486 (all passing) |
| Test files | 52 unit + 1 integration |
| Code coverage | 96% (2298 lines, 87 uncovered) |
| Known issues | 0 failing tests (2 pre-existing failures in `test_cli_replay.py` resolved) |
| Lint | ruff configured |

---

## 2. Scope

Full QA coverage of the Binex runtime:
- Pydantic domain models (boundary values, serialization)
- DAG construction & scheduling (topological sort, cycles, edge cases)
- Agent adapters (local, LLM, A2A — error handling, timeout)
- Persistence stores (SQLite, filesystem — concurrency, corruption)
- Runtime orchestrator & dispatcher (retry, timeout, interpolation)
- Replay engine (agent swaps, caching, fork references)
- CLI commands (all flags, error messages, output formats)
- Trace & debug tools (timeline, lineage, diff, rich output)
- Registry (FastAPI endpoints, discovery, health)
- Workflow spec loader & validator (YAML/JSON, interpolation)
- Security (OWASP Top 10 applicable subset)

**Out of scope:**
- Performance/load testing
- UI testing (CLI-only project)
- Third-party library internals (litellm, aiosqlite, click)

---

## 3. Test Categories

### CAT-1: Models & Validation (P1 — High)

Pydantic models, boundary values, serialization/deserialization.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-MOD-001 | NodeSpec with empty/invalid `agent` strings (empty, whitespace, no prefix) | P1 | TODO | Verify Pydantic rejects or handles gracefully |
| TC-MOD-002 | WorkflowSpec with duplicate node IDs in `nodes` dict | P2 | TODO | Dict keys deduplicate — verify last-wins behavior |
| TC-MOD-003 | RetryPolicy with `max_retries=-1` and `max_retries=0` | P1 | TODO | Boundary: negative retries, zero retries |
| TC-MOD-004 | Artifact with invalid `status` (not "complete"/"partial") | P1 | TODO | Pydantic Literal validation |
| TC-MOD-005 | ExecutionRecord JSON roundtrip (serialize → deserialize → equal) | P2 | TODO | All fields including datetime, optional |
| TC-MOD-006 | RunSummary with `completed_nodes > total_nodes` | P2 | TODO | Boundary: logical inconsistency |
| TC-MOD-007 | TaskNode with `deadline_ms=0` and `deadline_ms=-1` | P1 | TODO | Boundary: zero/negative deadline |

### CAT-2: DAG & Scheduler (P0 — Critical)

Correctness of topological sorting, cycle detection, scheduling.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-DAG-001 | DAG with self-reference (node depends on itself) | P0 | TODO | Must detect as cycle |
| TC-DAG-002 | DAG with isolated nodes (no edges, multiple entry points) | P1 | TODO | All should be entry_nodes |
| TC-DAG-003 | Diamond dependency (A->B, A->C, B->D, C->D) | P0 | TODO | D should wait for both B and C |
| TC-DAG-004 | Scheduler: mark_failed blocks dependent nodes | P0 | PARTIAL | Extend existing test for deeper chains |
| TC-DAG-005 | Large DAG (50+ nodes) — correctness and no hangs | P2 | TODO | Stress test |
| TC-DAG-006 | DAG with non-existent dependency reference | P0 | TODO | Validator should catch; DAG behavior if not |

### CAT-3: Adapters (P0 — Critical)

All three adapter types, error handling, timeout behavior.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-ADP-001 | LLMAdapter with invalid model string (litellm error) | P0 | TODO | Verify clean error, no crash |
| TC-ADP-002 | LLMAdapter forwards config params (api_base, temperature, max_tokens) | P1 | PARTIAL | Extend to verify kwargs passed to litellm |
| TC-ADP-003 | A2AAgentAdapter with unreachable endpoint (connection error) | P0 | PARTIAL | Verify error type and message |
| TC-ADP-004 | A2AAgentAdapter /execute timeout (slow remote agent) | P1 | TODO | Verify timeout enforced by dispatcher |
| TC-ADP-005 | LocalPythonAdapter with raising callable (exception in agent) | P0 | PARTIAL | Verify exception propagation |
| TC-ADP-006 | Adapter cancel() on already-completed task | P2 | TODO | Should be no-op or clean error |

### CAT-4: Stores — Persistence (P0 — Critical)

SQLite + filesystem stores, concurrent access, edge cases.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-STO-001 | SqliteExecutionStore: create_run with duplicate run_id | P0 | TODO | Should error or upsert? |
| TC-STO-002 | SqliteExecutionStore: list_records for non-existent run_id | P1 | TODO | Should return empty list |
| TC-STO-003 | FilesystemArtifactStore: get() with corrupted JSON file | P0 | TODO | Should not crash; clean error |
| TC-STO-004 | FilesystemArtifactStore: concurrent store() same artifact_id | P1 | TODO | Race condition check |
| TC-STO-005 | SqliteExecutionStore: close() prevents aiosqlite hang | P0 | TODO | Verify cleanup works |
| TC-STO-006 | Factory: create_execution_store with unknown backend name | P1 | TODO | Should raise ValueError or similar |

### CAT-5: Runtime — Orchestrator & Dispatcher (P0 — Critical)

Full execution cycle, retry logic, timeout enforcement, error handling.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-RUN-001 | Orchestrator: single-node workflow (minimal case) | P0 | DONE | Existing test |
| TC-RUN-002 | Orchestrator: all nodes fail -> status=="failed" | P0 | DONE | Existing test |
| TC-RUN-003 | Dispatcher: retry with exponential backoff (verify delays) | P1 | TODO | Mock time, check attempt count |
| TC-RUN-004 | Dispatcher: timeout enforcement (task exceeds deadline_ms) | P0 | PARTIAL | Extend with exact timing |
| TC-RUN-005 | Orchestrator: ${node.*} interpolation with missing artifact | P0 | TODO | Should fail with clear error |
| TC-RUN-006 | Orchestrator: workflow with user_vars all resolved | P0 | DONE | Existing test |

### CAT-6: Replay Engine (P1 — High)

Replay with agent swaps, caching, fork references.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-REP-001 | Replay with non-existent from_step | P1 | TODO | Should error cleanly |
| TC-REP-002 | Replay with agent_swaps for non-existent agent key | P1 | TODO | Should error or ignore? |
| TC-REP-003 | Replay: cached artifacts correctly copied to new run | P1 | PARTIAL | Verify artifact content matches |
| TC-REP-004 | Replay: forked_from and forked_at_step set in RunSummary | P1 | PARTIAL | Verify values match originals |
| TC-REP-005 | Replay of non-existent run_id | P0 | TODO | Should return None or raise |

### CAT-7: CLI Commands (P1 — High)

All CLI commands, flags, output format, error handling.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-CLI-001 | `binex run` with non-existent YAML file | P1 | TODO | exit_code != 0, error message |
| TC-CLI-002 | `binex run --var` with invalid format (no "=") | P1 | TODO | Should reject with usage hint |
| TC-CLI-003 | `binex debug` with non-existent run_id | P1 | DONE | Existing test |
| TC-CLI-004 | `binex debug --json` — output is valid JSON | P1 | DONE | Existing test |
| TC-CLI-005 | `binex debug --rich` without rich installed | P2 | TODO | Graceful fallback or error |
| TC-CLI-006 | `binex replay --agent old=new` swap syntax | P1 | PARTIAL | Test multiple swaps |
| TC-CLI-007 | `binex validate` with cyclic workflow | P0 | DONE | Existing test |
| TC-CLI-008 | `binex scaffold` — generated structure is correct | P1 | DONE | Existing test |
| TC-CLI-009 | `binex doctor` — pass/fail scenarios | P1 | DONE | Existing test |
| TC-CLI-010 | `binex dev` — compose up/down flow | P2 | DONE | Existing test |

### CAT-8: Trace & Debug (P2 — Medium)

Timeline, lineage, diff, debug report, rich formatting.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-TRC-001 | Timeline with empty run (0 records) | P2 | PARTIAL | Verify output format |
| TC-TRC-002 | Lineage with circular derived_from (loop protection) | P1 | TODO | Must not infinite loop |
| TC-TRC-003 | Diff of two runs with different node counts | P2 | TODO | Handles missing nodes |
| TC-TRC-004 | Debug report with mix of completed/failed/running nodes | P2 | DONE | Existing test |
| TC-TRC-005 | Rich formatting with Unicode/special chars in error messages | P2 | TODO | No crashes, readable output |

### CAT-9: Registry (P2 — Medium)

FastAPI endpoints, agent discovery, health checks.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-REG-001 | Register agent with invalid endpoint URL | P2 | TODO | Validation on input |
| TC-REG-002 | Search by non-existent capability | P2 | DONE | Existing test |
| TC-REG-003 | Health check timeout scenarios | P2 | DONE | Existing test |
| TC-REG-004 | Discovery: /.well-known/agent.json unavailable | P2 | PARTIAL | Verify error handling |

### CAT-10: Workflow Spec — Loader & Validator (P1 — High)

YAML/JSON loading, variable interpolation, validation rules.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-WFS-001 | Workflow with unknown/extra fields (strict vs lenient) | P2 | TODO | Pydantic behavior |
| TC-WFS-002 | ${user.var} without provided value | P1 | TODO | Should warn or leave raw? |
| TC-WFS-003 | Workflow with empty `nodes: {}` | P1 | TODO | Validator should reject |
| TC-WFS-004 | Nested ${node.x.y} interpolation (unsupported?) | P2 | TODO | Define expected behavior |
| TC-WFS-005 | Large workflow (100+ nodes) loading performance | P3 | TODO | No timeout on load |

### CAT-11: Security — OWASP (P1 — High)

| ID | Test Case | Priority | OWASP | Status | Notes |
|----|-----------|----------|-------|--------|-------|
| TC-SEC-001 | YAML bomb / unsafe YAML load (billion laughs) | P0 | A03-Injection | TODO | Verify yaml.safe_load used |
| TC-SEC-002 | ${user.var} with shell metacharacters (`;rm -rf /`) | P0 | A03-Injection | TODO | No shell execution of vars |
| TC-SEC-003 | artifact_id with `../` path traversal in filesystem store | P0 | A01-Access | TODO | Must not escape base dir |
| TC-SEC-004 | run_id with SQL injection payload in sqlite store | P0 | A03-Injection | TODO | Parameterized queries |
| TC-SEC-005 | a2a:// endpoint with internal IP (SSRF) | P1 | A10-SSRF | TODO | Document expected behavior |
| TC-SEC-006 | Error messages don't expose internal file paths | P2 | A05-Misconfig | TODO | Review error outputs |

---

## 4. Uncovered Code Lines

Key gaps to close for 96% -> 100% coverage:

| File | Lines | Description |
|------|-------|-------------|
| `cli/run.py` | 140-157, 174-177 | Real workflow execution path (integration) |
| `runtime/replay.py` | 130-131, 154-158, 210-213 | Replay edge cases |
| `trace/diff.py` | 93, 95, 115, 117, 132 | Diff formatting branches |
| `workflow_spec/validator.py` | 69-74 | Specific validation branches |
| `cli/artifacts.py` | 42-43, 67, 75 | Artifact CLI error paths |
| `cli/trace.py` | 74, 82, 86, 88, 90 | Trace CLI branches |
| `stores/backends/memory.py` | 31, 35 | In-memory store edge cases |

---

## 5. Execution Plan

### Week 1: P0 — Critical (CAT-2, CAT-3, CAT-4, CAT-5, TC-SEC-001..004)

**Goal:** Cover all critical paths — DAG correctness, adapter failures, store robustness, security injections.

- [ ] TC-DAG-001..006 (DAG & Scheduler)
- [ ] TC-ADP-001..006 (Adapters)
- [ ] TC-STO-001..006 (Stores)
- [ ] TC-RUN-003..005 (Runtime gaps)
- [ ] TC-SEC-001..004 (Security critical)

**Expected new tests:** ~25
**Target coverage after:** 97%+

### Week 2: P1 — High (CAT-1, CAT-6, CAT-7, CAT-10, TC-SEC-005..006)

**Goal:** Models boundary, replay edge cases, CLI error paths, workflow loading, remaining security.

- [ ] TC-MOD-001..007 (Models)
- [ ] TC-REP-001..005 (Replay)
- [ ] TC-CLI-001, 002, 005, 006 (CLI gaps)
- [ ] TC-WFS-001..004 (Workflow Spec)
- [ ] TC-SEC-005..006 (Security remaining)
- [ ] TC-TRC-002 (Lineage loop protection)

**Expected new tests:** ~25
**Target coverage after:** 98%+

### Week 3: P2/P3 — Medium/Low (CAT-8, CAT-9, remaining)

**Goal:** Trace tools, registry edge cases, coverage gaps, regression.

- [ ] TC-TRC-001, 003, 005 (Trace)
- [ ] TC-REG-001, 004 (Registry)
- [ ] TC-WFS-005, TC-DAG-005 (Performance)
- [ ] Uncovered lines cleanup
- [ ] Full regression run

**Expected new tests:** ~15
**Target coverage after:** 99%+

---

## 6. Quality Gates

| Gate | Current | Target | Blocker? |
|------|---------|--------|----------|
| Test Execution | 100% (486/486) | 100% | Yes |
| Pass Rate | 100% | >= 80% | Yes |
| P0 Bugs | 0 | 0 | Yes |
| P1 Bugs | 0 | <= 5 | Yes |
| Code Coverage | 96% | >= 80% (target 99%) | Yes |
| Security (OWASP) | Not tested | 90% (5/6 mitigated) | Yes |

---

## 7. Bug Tracking

Bugs found during testing will be logged in `tests/docs/BUG-TRACKING.csv`:

```
Bug ID,Severity,Category,Title,Steps to Reproduce,Expected,Actual,Status
```

Severity scale: P0 (blocker, 24h fix) — P4 (cosmetic).

---

## 8. Test Execution Tracking

Progress tracked in `tests/docs/TEST-EXECUTION-TRACKING.csv`:

```
Test ID,Category,Priority,Status,Date Executed,Result,Bug ID,Notes
```

Status values: TODO, IN_PROGRESS, PASS, FAIL, BLOCKED, SKIPPED.

---

## 9. Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| YAML injection (TC-SEC-001) | High — arbitrary code | Low (if safe_load used) | Verify yaml.safe_load |
| Path traversal in artifacts (TC-SEC-003) | High — file access | Medium | Test with `../` payloads |
| SQL injection in stores (TC-SEC-004) | High — data breach | Low (if parameterized) | Verify query params |
| aiosqlite hang on missing close() | Medium — CLI hangs | High (documented issue) | Test close() patterns |
| Replay with corrupted original run | Medium — wrong results | Low | Test corrupted inputs |
| Large DAG performance | Low — slow execution | Low | Stress test with 50+ nodes |

---

## 10. Environment

- **Python:** 3.11+
- **Test runner:** pytest + pytest-asyncio
- **Coverage:** pytest-cov
- **Lint:** ruff
- **Stores:** InMemoryExecutionStore + InMemoryArtifactStore (unit), SQLite + Filesystem (integration)
- **CLI testing:** click.testing.CliRunner with `_get_stores()` patching
