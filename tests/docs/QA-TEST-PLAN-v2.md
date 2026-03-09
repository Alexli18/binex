# QA Test Plan v2: Binex Runtime

**Project:** Binex — debuggable runtime for A2A agents
**Branch:** 004-cli-dx
**Date:** 2026-03-08
**QA Engineer:** Claude (AI-assisted)
**Previous QA:** v1 (branch 003-debug-command, 65 test cases, 664 tests)

---

## 1. Baseline

| Metric | Value |
|--------|-------|
| Total tests | 756 (all passing) |
| Test files | 70 unit + 1 integration |
| Code coverage | ~97% (estimated, not measured) |
| Known issues | 0 failing tests |
| Lint | ruff configured (E, F, I, N, W, UP) |
| Previous QA bugs | 2 found and fixed (BUG-001 path traversal, BUG-002 lineage recursion) |

---

## 2. Scope

### In scope
Full QA coverage of the Binex runtime with focus on:
- **Delta testing** — новые/изменённые модули с предыдущего QA
- **Regression testing** — проверка что прежние баг-фиксы не регрессировали
- **New module testing** — agents (planner, researcher, validator, summarizer), registry extensions
- **Integration testing** — end-to-end workflow execution
- **Security testing** — OWASP Top 10 applicable subset (refresh)
- **CLI DX testing** — новые команды и улучшения (hello, init, scaffold DSL, providers, doctor)
- **Boundary/edge cases** — areas with low test density

### Out of scope
- Performance/load testing
- UI testing (CLI-only project)
- Third-party library internals (litellm, aiosqlite, click)
- LLM output quality testing (non-deterministic)

---

## 3. Test Coverage Analysis

### Current test density by module

| Module | Source Files | Test Files | Tests | Density | Gap Assessment |
|--------|-------------|------------|-------|---------|----------------|
| **models/** | 5 files | 8 files | ~128 | HIGH | Good coverage, check new fields |
| **stores/** | 5 files | 6 files | ~53 | MEDIUM | Need concurrent write tests |
| **adapters/** | 5 files | 5 files | ~65 | MEDIUM | Need timeout edge cases |
| **graph/** | 2 files | 2 files | ~20 | MEDIUM | Need large DAG tests |
| **runtime/** | 4 files | 4 files | ~36 | LOW | Need orchestrator error paths |
| **trace/** | 5 files | 6 files | ~46 | MEDIUM | Need empty/malformed input tests |
| **registry/** | 5 files | 5 files | ~59 | HIGH | Good, check concurrent access |
| **agents/** | 8 files | 4 files | ~22 | LOW | Only 22 tests for 8 source files |
| **cli/** | 14 files | 16 files | ~156 | HIGH | Good, verify new commands |
| **workflow_spec/** | 2 files | 2 files | ~23 | MEDIUM | Need malformed YAML edge cases |
| **settings.py** | 1 file | 1 file | ~4 | LOW | Minimal coverage |
| **Integration** | - | 1 file | 5 | LOW | Need more e2e scenarios |

---

## 4. Test Categories & Test Cases

### CAT-1: Agent Reference Implementations (P1 — High) — NEW

Testing planner, researcher, validator, summarizer agents.

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-AGT-001 | PlannerAgent — happy path (valid prompt → plan output) | P1 | TODO | |
| TC-AGT-002 | PlannerAgent — empty prompt → graceful error | P1 | TODO | |
| TC-AGT-003 | PlannerAgent — LLM client timeout handling | P1 | TODO | |
| TC-AGT-004 | ResearcherAgent — valid query → research artifact | P1 | TODO | |
| TC-AGT-005 | ResearcherAgent — LLM failure → error propagation | P1 | TODO | |
| TC-AGT-006 | ValidatorAgent — valid input → validation result | P1 | TODO | |
| TC-AGT-007 | ValidatorAgent — invalid input → rejection with reason | P2 | TODO | |
| TC-AGT-008 | SummarizerAgent — long text → summary artifact | P1 | TODO | |
| TC-AGT-009 | SummarizerAgent — empty text → graceful handling | P2 | TODO | |
| TC-AGT-010 | Agent FastAPI apps — /execute endpoint contract (all 4 agents) | P0 | TODO | |
| TC-AGT-011 | Agent FastAPI apps — /health endpoint returns 200 | P1 | TODO | |
| TC-AGT-012 | LLMClient — config validation (missing model → error) | P1 | TODO | |
| TC-AGT-013 | LLMConfig — serialization roundtrip | P2 | TODO | |
| TC-AGT-014 | Agent apps — malformed /execute payload → 422 | P1 | TODO | |

### CAT-2: Registry Service (P1 — High) — EXPANDED

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-REG-001 | POST /agents — register new agent → 201 | P0 | TODO | Verify existing test |
| TC-REG-002 | POST /agents — duplicate registration → correct behavior | P1 | TODO | |
| TC-REG-003 | GET /agents/search — filter by capability → results | P1 | TODO | |
| TC-REG-004 | GET /agents/search — no matches → empty list | P2 | TODO | |
| TC-REG-005 | Discovery — valid .well-known/agent.json → parsed | P1 | TODO | |
| TC-REG-006 | Discovery — endpoint unreachable → timeout/error | P1 | TODO | |
| TC-REG-007 | Health check — healthy agent → status OK | P1 | TODO | |
| TC-REG-008 | Health check — unhealthy agent → status failure | P1 | TODO | |
| TC-REG-009 | Index — add/remove/search agents (in-memory) | P1 | TODO | |
| TC-REG-010 | Registry __main__ — entry point runs (uvicorn config) | P2 | TODO | |

### CAT-3: CLI DX Commands (P1 — High) — NEW/EXPANDED

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-CLI-001 | `binex hello` — zero-config demo runs without error | P0 | TODO | |
| TC-CLI-002 | `binex init` — workflow mode → generates workflow YAML | P1 | TODO | |
| TC-CLI-003 | `binex init` — agent mode → generates agent scaffold | P1 | TODO | |
| TC-CLI-004 | `binex init` — full mode → generates both | P1 | TODO | |
| TC-CLI-005 | `binex scaffold workflow "A -> B -> C"` → valid YAML | P0 | TODO | |
| TC-CLI-006 | `binex scaffold` — invalid DSL syntax → helpful error | P1 | TODO | |
| TC-CLI-007 | `binex doctor` — all checks pass → green output | P1 | TODO | |
| TC-CLI-008 | `binex doctor` — missing dependency → warning | P1 | TODO | |
| TC-CLI-009 | `binex validate` — valid YAML → success | P0 | TODO | |
| TC-CLI-010 | `binex validate` — cyclic workflow → error | P1 | TODO | |
| TC-CLI-011 | `binex providers` — list all 8 providers | P2 | TODO | |
| TC-CLI-012 | `binex dev up` — docker-compose invocation | P2 | TODO | |
| TC-CLI-013 | `binex dev down` — stops containers | P2 | TODO | |
| TC-CLI-014 | `binex run` — with `--var key=value` → user var injected | P1 | TODO | |
| TC-CLI-015 | `binex run` — with `--provider ollama` → provider set | P1 | TODO | |
| TC-CLI-016 | `binex run -v` — verbose output with progress counters | P1 | TODO | |
| TC-CLI-017 | `binex debug <run_id>` — plain text output | P0 | TODO | |
| TC-CLI-018 | `binex debug <run_id> --json` — JSON output | P1 | TODO | |
| TC-CLI-019 | `binex debug <run_id> --errors` — only errors shown | P1 | TODO | |
| TC-CLI-020 | `binex debug <run_id> --node X` — single node output | P1 | TODO | |
| TC-CLI-021 | `binex debug <run_id> --rich` — rich formatted output | P2 | TODO | |
| TC-CLI-022 | `binex cancel <run_id>` — cancel running workflow | P1 | TODO | |

### CAT-4: DSL Parser (P1 — High) — NEW

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-DSL-001 | Linear chain: "A -> B -> C" → correct DAG | P0 | TODO | |
| TC-DSL-002 | Fan-out: "A -> B, C" → A depends on nothing, B,C depend on A | P0 | TODO | |
| TC-DSL-003 | Diamond: "A -> B, C -> D" → D depends on B and C | P1 | TODO | |
| TC-DSL-004 | Predefined patterns: all 9 → valid workflows | P1 | TODO | |
| TC-DSL-005 | Empty/whitespace input → error | P1 | TODO | |
| TC-DSL-006 | Single node: "A" → valid single-node workflow | P2 | TODO | |
| TC-DSL-007 | Duplicate node names → error or dedup | P2 | TODO | |

### CAT-5: Runtime — Orchestrator & Dispatcher (P0 — Critical) — REGRESSION

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-RUN-001 | Two-node linear workflow → both execute in order | P0 | TODO | Regression |
| TC-RUN-002 | Five-node pipeline → all execute sequentially | P0 | TODO | Regression |
| TC-RUN-003 | Workflow with failing node → error recorded, run fails | P0 | TODO | Regression |
| TC-RUN-004 | Diamond DAG → parallel execution of B, C | P0 | TODO | |
| TC-RUN-005 | Retry policy — node fails then succeeds → retried | P1 | TODO | |
| TC-RUN-006 | Timeout enforcement — slow node → TimeoutError | P1 | TODO | |
| TC-RUN-007 | ${node.*} interpolation at runtime → artifact value resolved | P1 | TODO | |
| TC-RUN-008 | ${user.*} interpolation at load time → value substituted | P1 | TODO | |
| TC-RUN-009 | Conditional when → node skipped if condition false | P1 | TODO | |
| TC-RUN-010 | Skipped node → dependents still execute | P1 | TODO | |

### CAT-6: Replay Engine (P1 — High) — REGRESSION

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-RPL-001 | Fork run → new run ID, copied artifacts | P0 | TODO | Regression |
| TC-RPL-002 | Agent swap → llm://A replaced with llm://B | P1 | TODO | |
| TC-RPL-003 | Cached artifacts → skipped nodes use cached results | P1 | TODO | |
| TC-RPL-004 | --from-step → replay from specific node | P1 | TODO | |
| TC-RPL-005 | Invalid run_id → error message | P2 | TODO | |

### CAT-7: Stores — Persistence (P0 — Critical) — REGRESSION

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-STR-001 | SqliteExecutionStore — record → get_run roundtrip | P0 | TODO | Regression |
| TC-STR-002 | SqliteExecutionStore — list_records with filters | P1 | TODO | |
| TC-STR-003 | SqliteExecutionStore — close() prevents aiosqlite hang | P0 | TODO | |
| TC-STR-004 | FilesystemArtifactStore — store → get roundtrip | P0 | TODO | Regression |
| TC-STR-005 | FilesystemArtifactStore — path traversal blocked | P0 | TODO | Regression (BUG-001) |
| TC-STR-006 | FilesystemArtifactStore — rglob scan finds stored artifacts | P1 | TODO | |
| TC-STR-007 | Store factories — correct backend returned | P1 | TODO | |
| TC-STR-008 | InMemory stores — concurrent operations | P2 | TODO | |

### CAT-8: Adapters (P1 — High) — REGRESSION + NEW

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-ADP-001 | LLMAdapter — successful completion → artifact | P0 | TODO | Regression |
| TC-ADP-002 | LLMAdapter — per-node config (temperature, api_base) forwarded | P1 | TODO | |
| TC-ADP-003 | LLMAdapter — None kwargs NOT forwarded to litellm | P1 | TODO | |
| TC-ADP-004 | A2AAgentAdapter — POST /execute → response artifacts | P0 | TODO | Regression |
| TC-ADP-005 | A2AAgentAdapter — endpoint unreachable → error | P1 | TODO | |
| TC-ADP-006 | HumanApprovalAdapter — approved → "approved" artifact | P1 | TODO | |
| TC-ADP-007 | HumanApprovalAdapter — rejected → "rejected" artifact | P1 | TODO | |
| TC-ADP-008 | LocalPythonAdapter — sync callable → result | P1 | TODO | |
| TC-ADP-009 | LocalPythonAdapter — async callable → result | P1 | TODO | |
| TC-ADP-010 | Multi-provider — all 8 providers registered | P1 | TODO | |

### CAT-9: Trace & Debug (P2 — Medium) — REGRESSION

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-TRC-001 | Timeline generation → text format | P1 | TODO | Regression |
| TC-TRC-002 | Timeline generation → JSON format | P1 | TODO | |
| TC-TRC-003 | Lineage tree — no circular refs (BUG-002 regression) | P0 | TODO | Regression |
| TC-TRC-004 | Diff — compare two runs → differences shown | P1 | TODO | |
| TC-TRC-005 | DebugReport — summary with errors/warnings | P1 | TODO | |
| TC-TRC-006 | Rich output — colored tables render | P2 | TODO | |

### CAT-10: Workflow Spec (P1 — High)

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-WFS-001 | Load valid YAML → WorkflowSpec | P0 | TODO | |
| TC-WFS-002 | Load valid JSON → WorkflowSpec | P1 | TODO | |
| TC-WFS-003 | ${user.*} interpolation → values substituted | P0 | TODO | |
| TC-WFS-004 | ${env.*} interpolation → env var values | P1 | TODO | |
| TC-WFS-005 | Cyclic workflow → validation error | P0 | TODO | |
| TC-WFS-006 | No entry node → validation error | P1 | TODO | |
| TC-WFS-007 | Unknown node reference → validation error | P1 | TODO | |

### CAT-11: Models & Validation (P1 — High) — REGRESSION

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-MDL-001 | WorkflowSpec — valid YAML → Pydantic model | P0 | TODO | |
| TC-MDL-002 | NodeSpec — when field parsing | P1 | TODO | |
| TC-MDL-003 | NodeSpec — config dict forwarding | P1 | TODO | |
| TC-MDL-004 | ExecutionRecord — JSON roundtrip | P1 | TODO | |
| TC-MDL-005 | TaskNode — RetryPolicy validation | P1 | TODO | |
| TC-MDL-006 | Artifact — status enum (complete/partial) | P1 | TODO | |
| TC-MDL-007 | AgentInfo — required fields validation | P1 | TODO | |
| TC-MDL-008 | Boundary values — max lengths, special characters | P1 | TODO | |

### CAT-12: Settings & Configuration (P2 — Medium) — NEW

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-CFG-001 | Settings — BINEX_* environment variables loaded | P1 | TODO | |
| TC-CFG-002 | Settings — default values when env vars missing | P1 | TODO | |
| TC-CFG-003 | .env file — loaded by CLI entry point | P1 | TODO | |
| TC-CFG-004 | .env file — missing file → no error | P2 | TODO | |

### CAT-13: Security (P0 — Critical) — REGRESSION

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-SEC-001 | YAML safe_load — no arbitrary code execution | P0 | TODO | |
| TC-SEC-002 | SQL injection — parameterized queries | P0 | TODO | |
| TC-SEC-003 | Path traversal — `../` blocked in artifact IDs | P0 | TODO | BUG-001 regression |
| TC-SEC-004 | Path traversal — `/` blocked in run IDs | P0 | TODO | |
| TC-SEC-005 | Path traversal — `\` blocked (Windows) | P1 | TODO | |
| TC-SEC-006 | Lineage — circular derived_from → no infinite loop | P0 | TODO | BUG-002 regression |
| TC-SEC-007 | Error messages — no internal path leaks | P1 | TODO | |
| TC-SEC-008 | Agent endpoints — validate A2A response schema | P1 | TODO | |

### CAT-14: Integration / E2E (P0 — Critical)

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-E2E-001 | Simple two-node workflow → complete execution | P0 | TODO | |
| TC-E2E-002 | Five-node pipeline → sequential execution | P0 | TODO | |
| TC-E2E-003 | Diamond pattern → parallel fan-out + fan-in | P0 | TODO | |
| TC-E2E-004 | Example YAML files — all 14 parse without error | P0 | TODO | |
| TC-E2E-005 | Conditional routing workflow → correct path taken | P1 | TODO | |
| TC-E2E-006 | Error handling workflow → retry + error recorded | P1 | TODO | |

---

## 5. Execution Plan

### Phase 1: Smoke Test & Regression (Day 1)
- Run full test suite → confirm 756/756 pass
- Measure code coverage
- Run ruff lint check
- Verify BUG-001 and BUG-002 regression tests still pass

### Phase 2: New Module Testing (Day 1-2)
- CAT-1: Agent Reference Implementations (14 test cases)
- CAT-4: DSL Parser (7 test cases)
- CAT-12: Settings & Configuration (4 test cases)

### Phase 3: CLI DX Deep Testing (Day 2-3)
- CAT-3: CLI DX Commands (22 test cases)
- Focus on new commands: hello, init, scaffold, doctor, providers

### Phase 4: Core Regression (Day 3-4)
- CAT-5: Runtime (10 test cases)
- CAT-6: Replay (5 test cases)
- CAT-7: Stores (8 test cases)
- CAT-8: Adapters (10 test cases)

### Phase 5: Security & Integration (Day 4-5)
- CAT-13: Security (8 test cases)
- CAT-14: Integration / E2E (6 test cases)
- CAT-9: Trace & Debug (6 test cases)
- CAT-10: Workflow Spec (7 test cases)
- CAT-11: Models (8 test cases)
- CAT-2: Registry (10 test cases)

---

## 6. Quality Gates

| Gate | Target | Blocker? |
|------|--------|----------|
| Test Execution | 100% test cases executed | Yes |
| Pass Rate | ≥ 95% | Yes |
| P0 Bugs | 0 open | Yes |
| P1 Bugs | ≤ 3 open | Yes |
| Code Coverage | ≥ 95% | Yes |
| Security Tests | 100% pass | Yes |
| Regression Tests | 0 regressions | Yes |
| Lint Clean | 0 ruff errors | No |

---

## 7. Test Case Totals

| Category | Test Cases | Priority |
|----------|-----------|----------|
| CAT-1: Agent Implementations | 14 | P1 |
| CAT-2: Registry Service | 10 | P1 |
| CAT-3: CLI DX Commands | 22 | P1 |
| CAT-4: DSL Parser | 7 | P1 |
| CAT-5: Runtime | 10 | P0 |
| CAT-6: Replay | 5 | P1 |
| CAT-7: Stores | 8 | P0 |
| CAT-8: Adapters | 10 | P1 |
| CAT-9: Trace & Debug | 6 | P2 |
| CAT-10: Workflow Spec | 7 | P1 |
| CAT-11: Models | 8 | P1 |
| CAT-12: Settings | 4 | P2 |
| CAT-13: Security | 8 | P0 |
| CAT-14: Integration / E2E | 6 | P0 |
| **TOTAL** | **125** | |

---

## 8. Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| New agents have low test density (22 tests / 8 files) | High | High | Priority testing in CAT-1 |
| Settings module barely tested (4 tests) | Medium | Medium | CAT-12 fills gap |
| Integration tests minimal (5 tests) | High | Medium | CAT-14 adds scenarios |
| Async cleanup (aiosqlite close) regression | High | Low | TC-STR-003 validates |
| Security regression on path traversal fix | Critical | Low | TC-SEC-003/004 validate |

---

## 9. Tracking

- **Test execution:** `tests/docs/TEST-EXECUTION-TRACKING-v2.csv`
- **Bug tracking:** `tests/docs/BUG-TRACKING-v2.csv`
- **Previous QA:** `tests/docs/QA-TEST-PLAN.md` (v1, 65 test cases)
