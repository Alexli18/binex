# QA Test Plan v6 — Plugin System & Framework Adapters (E2E)

**Branch**: `012-framework-adapters`
**Features**: 011-plugin-system, 012-framework-adapters
**Date**: 2026-03-13
**Type**: End-to-End (real subprocess, real filesystem, no mocks)

## Scope

E2E validation of:
1. `binex plugins list` — CLI output (text + JSON)
2. `binex plugins check <workflow>` — dependency validation
3. Plugin discovery during `binex run`
4. Framework adapter resolution and error handling
5. Mixed-adapter workflows with plugin fallback

## Test Cases

### Category 1: Plugin CLI — `binex plugins list` (5 cases)

| ID | Description | Priority |
|----|-------------|----------|
| TC-E2E-P01 | `binex plugins list` shows 4 built-in adapters (local, llm, human, a2a) | P0 |
| TC-E2E-P02 | `binex plugins list` shows installed framework plugins (langchain, crewai, autogen) | P0 |
| TC-E2E-P03 | `binex plugins list --json` returns valid JSON with builtins and plugins arrays | P0 |
| TC-E2E-P04 | JSON output plugins contain correct fields: prefix, package, version | P1 |
| TC-E2E-P05 | `binex plugins list` exit code is 0 | P2 |

### Category 2: Plugin CLI — `binex plugins check` (6 cases)

| ID | Description | Priority |
|----|-------------|----------|
| TC-E2E-P06 | `binex plugins check` on workflow with only built-ins exits 0 | P0 |
| TC-E2E-P07 | `binex plugins check` on workflow with known plugin prefix exits 0 | P0 |
| TC-E2E-P08 | `binex plugins check` on workflow with unknown prefix exits 1 | P0 |
| TC-E2E-P09 | Output shows checkmark for resolved and cross for missing adapters | P1 |
| TC-E2E-P10 | `binex plugins check` on workflow with mixed built-in + plugin prefixes exits 0 | P1 |
| TC-E2E-P11 | `binex plugins check` on empty workflow (no nodes) shows message | P2 |

### Category 3: Plugin Discovery during `binex run` (3 cases)

| ID | Description | Priority |
|----|-------------|----------|
| TC-E2E-P12 | `binex run` with local:// nodes still works (plugin system doesn't break existing) | P0 |
| TC-E2E-P13 | `binex run` with unknown prefix gives clear error message | P0 |
| TC-E2E-P14 | `binex run --json` with local:// produces valid JSON with run_id and status | P1 |

### Category 4: Framework Adapter Discovery (4 cases)

| ID | Description | Priority |
|----|-------------|----------|
| TC-E2E-P15 | All 3 framework plugins appear in `binex plugins list --json` output | P0 |
| TC-E2E-P16 | `binex plugins check` resolves langchain:// prefix as plugin | P1 |
| TC-E2E-P17 | `binex plugins check` resolves crewai:// prefix as plugin | P1 |
| TC-E2E-P18 | `binex plugins check` resolves autogen:// prefix as plugin | P1 |

### Category 5: Error Handling & Edge Cases (4 cases)

| ID | Description | Priority |
|----|-------------|----------|
| TC-E2E-P19 | `binex plugins check` on nonexistent file gives error | P1 |
| TC-E2E-P20 | `binex plugins check` on invalid YAML gives error | P2 |
| TC-E2E-P21 | `binex run` with local-only workflow preserves full JSON output contract | P2 |
| TC-E2E-P22 | `binex plugins list` and `binex plugins check` are registered as CLI commands | P2 |

## Total: 22 test cases

## Quality Gates

| Gate | Target | Status |
|------|--------|--------|
| Test Execution | 100% | PENDING |
| Pass Rate | ≥80% | PENDING |
| P0 Bugs | 0 | PENDING |
| P1 Bugs | ≤5 | PENDING |
| All existing tests pass | Yes | PENDING |
| Ruff lint clean | Yes | PENDING |
