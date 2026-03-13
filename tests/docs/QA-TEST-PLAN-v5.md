# QA Test Plan v5 — A2A Gateway (010-a2a-gateway)

**Branch**: `010-a2a-gateway`
**Date**: 2026-03-13
**Baseline**: 1817 tests (148 gateway), lint: 0 errors

## Scope

Gap coverage for A2A Gateway module — 46 test cases across 10 categories.

## CAT-1: Config Validation (8 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-CFG-001 | Multiple env vars in single YAML value | P2 |
| TC-CFG-002 | Whitespace-only API key rejected | P1 |
| TC-CFG-003 | Empty YAML file loads as default GatewayConfig | P2 |
| TC-CFG-004 | FallbackConfig retry_count=0 boundary | P2 |
| TC-CFG-005 | HealthConfig interval_s=1, timeout_ms=1 boundary | P2 |
| TC-CFG-006 | Non-string types pass through _interpolate_recursive | P2 |
| TC-CFG-007 | Config search fallback to ./gateway.yaml | P2 |
| TC-CFG-008 | Invalid backoff literal rejected | P2 |

## CAT-2: Auth Edge Cases (3 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-AUTH-001 | Duplicate keys last writer wins | P2 |
| TC-AUTH-002 | Whitespace in API key not trimmed at auth | P2 |
| TC-AUTH-003 | NoAuth returns client_name=None | P3 |

## CAT-3: Registry Edge Cases (3 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-REG-001 | update_health unknown agent early return | P2 |
| TC-REG-002 | Degraded increments consecutive_failures | P2 |
| TC-REG-003 | Multi-capability agent found by any cap | P2 |

## CAT-4: Health Checker (4 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-HC-001 | start() twice idempotent | P1 |
| TC-HC-002 | stop() when task is None | P2 |
| TC-HC-003 | _check_loop survives check_all exception | P1 |
| TC-HC-004 | check_all empty registry | P2 |

## CAT-5: Router Edge Cases (2 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-RTR-001 | health=None → 999999 latency fallback | P2 |
| TC-RTR-002 | Degraded None latency vs measured latency sort | P2 |

## CAT-6: Fallback Edge Cases (4 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-FB-001 | No "artifacts" key defaults to [] | P2 |
| TC-FB-002 | No "cost" key defaults to None | P2 |
| TC-FB-003 | timeout_ms override from RoutingHints | P2 |
| TC-FB-004 | Empty agents list raises RuntimeError | P2 |

## CAT-7: App Endpoints (6 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-APP-001 | /health "unhealthy" all agents down | P1 |
| TC-APP-002 | /health "degraded" some down | P1 |
| TC-APP-003 | /health no registry (zero agents) | P2 |
| TC-APP-004 | /agents/{name} registry=None → 404 | P2 |
| TC-APP-005 | /agents/refresh no health_checker | P2 |
| TC-APP-006 | /route with routing hints in body | P2 |

## CAT-8: Gateway Core (4 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-GW-001 | Pass-through properties | P2 |
| TC-GW-002 | route() after start() uses shared client | P1 |
| TC-GW-003 | route() updates registry health on success | P2 |
| TC-GW-004 | stop() safe without start() | P2 |

## CAT-9: A2A Adapter (6 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-A2A-001 | _build_result empty artifacts | P2 |
| TC-A2A-002 | _build_result missing type → "unknown" | P2 |
| TC-A2A-003 | _build_result cost=None → source="unknown" | P2 |
| TC-A2A-004 | A2AAgentAdapter.health() all branches | P1 |
| TC-A2A-005 | A2AExternalGatewayAdapter.health() all branches | P1 |
| TC-A2A-006 | A2AExternalGatewayAdapter.cancel() no-op | P3 |

## CAT-10: CLI Edge Cases (3 cases)
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-CLI-001 | agents_cmd no capabilities → "none" | P2 |
| TC-CLI-002 | agents_cmd latency=None → "n/a" | P2 |
| TC-CLI-003 | agents_cmd custom --gateway URL | P2 |

## Summary
| Category | Cases | P1 | P2 | P3 |
|----------|-------|----|----|------|
| Config | 8 | 1 | 7 | 0 |
| Auth | 3 | 0 | 2 | 1 |
| Registry | 3 | 0 | 3 | 0 |
| Health | 4 | 2 | 2 | 0 |
| Router | 2 | 0 | 2 | 0 |
| Fallback | 4 | 0 | 4 | 0 |
| App | 6 | 2 | 4 | 0 |
| Gateway | 4 | 1 | 3 | 0 |
| A2A | 6 | 2 | 4 | 0 |
| CLI | 3 | 0 | 3 | 0 |
| **Total** | **46** | **8** | **34** | **2** |

## Quality Gates
| Gate | Target | Status |
|------|--------|--------|
| Test Execution | 100% | PENDING |
| Pass Rate | ≥80% | PENDING |
| P0 Bugs | 0 | PENDING |
| P1 Bugs | ≤5 | PENDING |
| Lint | 0 errors | PENDING |
