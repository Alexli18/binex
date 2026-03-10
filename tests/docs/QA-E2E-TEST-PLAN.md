# Binex E2E Test Plan

**Version**: E2E v1
**Branch**: 007-budget-cost-tracking
**Baseline**: 1204 tests (unit + integration)
**Date**: 2026-03-10

## Scope

End-to-end tests covering **full user journeys** through the Binex runtime:
workflow loading -> DAG building -> scheduling -> dispatch -> cost tracking -> persistence -> CLI output.

All E2E tests use `local://` adapters (no external LLM/A2A calls) but exercise
the complete runtime stack including stores, orchestrator, dispatcher, and CLI.

## Test Categories

### Category 1: Complete Workflow Lifecycle (TC-E2E-001 to TC-E2E-008)

| ID | Title | Priority |
|----|-------|----------|
| TC-E2E-001 | Simple 2-node pipeline: run -> debug -> cost | P0 |
| TC-E2E-002 | 5-node fan-out/fan-in pipeline | P0 |
| TC-E2E-003 | Diamond DAG (A -> B, C -> D) | P1 |
| TC-E2E-004 | Workflow with failing node | P0 |
| TC-E2E-005 | Conditional execution (when clause) — approved path | P0 |
| TC-E2E-006 | Conditional execution (when clause) — rejected path | P0 |
| TC-E2E-007 | Replay from mid-pipeline step | P1 |
| TC-E2E-008 | Replay with agent swap | P1 |

### Category 2: Budget & Cost Tracking (TC-E2E-009 to TC-E2E-015)

| ID | Title | Priority |
|----|-------|----------|
| TC-E2E-009 | Cost accumulation across multiple nodes | P0 |
| TC-E2E-010 | Budget policy "stop" — skips remaining nodes | P0 |
| TC-E2E-011 | Budget policy "warn" — continues execution | P1 |
| TC-E2E-012 | Cost CLI show command after run | P1 |
| TC-E2E-013 | Cost CLI history command after run | P1 |
| TC-E2E-014 | Zero-cost local-only workflow | P2 |
| TC-E2E-015 | Cost precision with many nodes | P2 |

### Category 3: CLI Full Journey (TC-E2E-016 to TC-E2E-022)

| ID | Title | Priority |
|----|-------|----------|
| TC-E2E-016 | `binex hello` full cycle | P0 |
| TC-E2E-017 | `binex run` with --json output | P0 |
| TC-E2E-018 | `binex run` with --var substitution | P1 |
| TC-E2E-019 | `binex run` with --verbose | P2 |
| TC-E2E-020 | `binex validate` valid workflow | P1 |
| TC-E2E-021 | `binex validate` invalid workflow | P1 |
| TC-E2E-022 | `binex debug` with --json and --errors | P1 |

### Category 4: Error Handling & Edge Cases (TC-E2E-023 to TC-E2E-028)

| ID | Title | Priority |
|----|-------|----------|
| TC-E2E-023 | All nodes fail — workflow status "failed" | P1 |
| TC-E2E-024 | Partial failure (2/5 nodes fail) | P1 |
| TC-E2E-025 | Retry policy with backoff | P1 |
| TC-E2E-026 | Deadline timeout on slow node | P1 |
| TC-E2E-027 | Empty workflow (0 nodes) | P2 |
| TC-E2E-028 | Concurrent runs isolation | P2 |

### Category 5: Data Integrity (TC-E2E-029 to TC-E2E-033)

| ID | Title | Priority |
|----|-------|----------|
| TC-E2E-029 | Artifacts persist and retrievable after run | P0 |
| TC-E2E-030 | Execution records match node count | P0 |
| TC-E2E-031 | Cost records match executed node count | P1 |
| TC-E2E-032 | Run summary fields consistent with records | P1 |
| TC-E2E-033 | Lineage chain: derived_from references valid | P2 |

## Quality Gates

| Gate | Target |
|------|--------|
| All E2E tests pass | 100% |
| No P0 failures | 0 |
| No P1 failures | 0 |
| Total test count | Baseline + E2E count |

## Total: 33 E2E test cases
