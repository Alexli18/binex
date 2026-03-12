# QA Test Plan v4 — Advanced Debugging (009-advanced-debugging)

**Branch**: `009-advanced-debugging`
**Date**: 2026-03-12
**Baseline**: 1507 tests

## Scope

6 new features to test:

1. **Root-Cause Diagnosis** (`trace/diagnose.py`, `cli/diagnose.py`)
2. **Run Bisection** (`trace/bisect.py`, `cli/bisect.py`)
3. **Output Schema Validation** (`runtime/schema_validator.py`, `runtime/dispatcher.py`, `workflow_spec/validator.py`)
4. **Streaming LLM Output** (`adapters/llm.py`, `runtime/dispatcher.py`, `runtime/orchestrator.py`, `cli/run.py`)
5. **Enhanced Run Diff** (`trace/diff.py`, `trace/diff_rich.py`)
6. **Dashboard Integration** (`cli/explore.py`)

---

## Category 1: Root-Cause Diagnosis (TC-DIAG-001 – TC-DIAG-020)

### Unit: classify_error()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIAG-001 | classify_error with "Connection timed out" returns "timeout" | P1 |
| TC-DIAG-002 | classify_error with "rate limit exceeded" returns "rate_limit" | P1 |
| TC-DIAG-003 | classify_error with "unauthorized access" returns "auth" | P1 |
| TC-DIAG-004 | classify_error with "budget exceeded" returns "budget" | P1 |
| TC-DIAG-005 | classify_error with "connection refused" returns "connection" | P1 |
| TC-DIAG-006 | classify_error with "some random error" returns "unknown" | P1 |
| TC-DIAG-007 | classify_error case-insensitive: "TIMEOUT" returns "timeout" | P2 |

### Unit: find_root_cause()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIAG-008 | find_root_cause with no failed records returns None | P1 |
| TC-DIAG-009 | find_root_cause returns first failed node in DAG order | P1 |
| TC-DIAG-010 | find_root_cause fallback when failed node not in dag_order | P2 |

### Unit: detect_cascade()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIAG-011 | detect_cascade without DAG collects all failed/skipped except root | P1 |
| TC-DIAG-012 | detect_cascade with DAG does BFS and collects affected nodes | P2 |

### Unit: detect_latency_anomalies()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIAG-013 | detect_latency_anomalies with < 2 records returns empty | P1 |
| TC-DIAG-014 | detect_latency_anomalies flags nodes > 3x median | P1 |
| TC-DIAG-015 | detect_latency_anomalies skips nodes with 0 latency | P2 |

### Unit: generate_recommendations()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIAG-016 | generate_recommendations with root_cause produces advice | P1 |
| TC-DIAG-017 | generate_recommendations with anomalies produces performance warning | P1 |
| TC-DIAG-018 | generate_recommendations with None root_cause and no anomalies returns empty | P2 |

### Integration: diagnose_run()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIAG-019 | diagnose_run returns "clean" for all-completed run | P1 |
| TC-DIAG-020 | diagnose_run returns "issues_found" with root_cause for failed run | P1 |

### Unit: report_to_dict()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIAG-021 | report_to_dict serializes all fields correctly | P1 |
| TC-DIAG-022 | report_to_dict with None root_cause returns null | P2 |

### CLI: binex diagnose
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIAG-023 | diagnose --json outputs valid JSON | P1 |
| TC-DIAG-024 | diagnose plain text shows root cause and recommendations | P1 |
| TC-DIAG-025 | diagnose with non-existent run_id shows error | P1 |
| TC-DIAG-026 | diagnose --no-rich forces plain text output | P2 |

---

## Category 2: Run Bisection (TC-BSCT-001 – TC-BSCT-015)

### Unit: find_divergence()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-BSCT-001 | find_divergence with identical runs returns None | P1 |
| TC-BSCT-002 | find_divergence detects status divergence | P1 |
| TC-BSCT-003 | find_divergence detects content divergence below threshold | P1 |
| TC-BSCT-004 | find_divergence raises ValueError for missing run | P1 |
| TC-BSCT-005 | find_divergence raises ValueError for mismatched workflows | P1 |
| TC-BSCT-006 | find_divergence with custom threshold (0.5) | P2 |
| TC-BSCT-007 | find_divergence includes upstream_context | P2 |

### Unit: divergence_to_dict()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-BSCT-008 | divergence_to_dict with None divergence returns message | P1 |
| TC-BSCT-009 | divergence_to_dict with divergence returns all fields | P1 |

### CLI: binex bisect
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-BSCT-010 | bisect --json outputs valid JSON with divergence | P1 |
| TC-BSCT-011 | bisect plain text shows divergence info | P1 |
| TC-BSCT-012 | bisect --threshold 0.5 passes custom threshold | P2 |
| TC-BSCT-013 | bisect with non-existent run shows error | P1 |
| TC-BSCT-014 | bisect with no divergence shows "identical" message | P2 |
| TC-BSCT-015 | bisect --no-rich forces plain text | P2 |

---

## Category 3: Output Schema Validation (TC-SCHM-001 – TC-SCHM-015)

### Unit: validate_output()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-SCHM-001 | validate_output with valid dict returns valid=True | P1 |
| TC-SCHM-002 | validate_output with valid JSON string returns valid=True | P1 |
| TC-SCHM-003 | validate_output with invalid dict returns errors | P1 |
| TC-SCHM-004 | validate_output with None returns error | P1 |
| TC-SCHM-005 | validate_output with non-JSON string returns error | P1 |
| TC-SCHM-006 | validate_output with nested schema validation | P2 |

### Integration: dispatcher schema validation
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-SCHM-007 | dispatch with output_schema validates and returns on success | P1 |
| TC-SCHM-008 | dispatch with output_schema retries on validation failure | P1 |
| TC-SCHM-009 | dispatch raises SchemaValidationError after max retries | P1 |
| TC-SCHM-010 | dispatch adds feedback artifact on validation retry | P2 |
| TC-SCHM-011 | dispatch without output_schema skips validation | P1 |

### Workflow Validator: _check_output_schemas()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-SCHM-012 | validate_workflow accepts valid output_schema | P1 |
| TC-SCHM-013 | validate_workflow rejects non-dict output_schema | P1 |
| TC-SCHM-014 | validate_workflow rejects invalid JSON Schema | P1 |
| TC-SCHM-015 | validate_workflow accepts None output_schema (no validation) | P2 |

---

## Category 4: Streaming LLM Output (TC-STRM-001 – TC-STRM-010)

### Unit: LLMAdapter streaming
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-STRM-001 | execute with stream=True calls _streaming_completion | P1 |
| TC-STRM-002 | execute with stream=True falls back on streaming error | P1 |
| TC-STRM-003 | execute with stream=True and tools uses non-streaming | P1 |
| TC-STRM-004 | stream_callback receives tokens | P2 |

### Integration: dispatcher + orchestrator streaming
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-STRM-005 | dispatcher._call_adapter forwards stream to LLMAdapter | P1 |
| TC-STRM-006 | dispatcher._call_adapter non-LLM adapter ignores stream | P1 |
| TC-STRM-007 | orchestrator passes stream params to dispatcher | P1 |

### CLI: binex run --stream
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-STRM-008 | run --stream sets stream=True | P1 |
| TC-STRM-009 | run --no-stream sets stream=False | P1 |
| TC-STRM-010 | run without flag auto-detects from TTY | P2 |

---

## Category 5: Enhanced Run Diff (TC-DIFF-001 – TC-DIFF-010)

### Unit: diff helpers
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIFF-001 | _content_similarity with identical strings returns 1.0 | P1 |
| TC-DIFF-002 | _content_similarity with None/None returns 1.0 | P1 |
| TC-DIFF-003 | _content_similarity with one None returns 0.0 | P1 |
| TC-DIFF-004 | _content_similarity with different strings returns < 1.0 | P1 |
| TC-DIFF-005 | _compute_summary counts changed/unchanged nodes correctly | P1 |
| TC-DIFF-006 | _compute_summary computes latency_delta | P2 |
| TC-DIFF-007 | _compute_summary computes average content_similarity | P2 |

### Integration: diff_runs()
| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DIFF-008 | diff_runs returns summary with correct metrics | P1 |
| TC-DIFF-009 | diff_runs includes content_a, content_b, content_similarity per step | P1 |
| TC-DIFF-010 | diff_runs raises ValueError for missing run | P1 |

---

## Category 6: Dashboard Integration (TC-DASH-001 – TC-DASH-005)

| ID | Test Case | Priority |
|----|-----------|----------|
| TC-DASH-001 | explore menu shows diagnose/diff/bisect options | P1 |
| TC-DASH-002 | _pick_other_run lists recent runs of same workflow | P2 |
| TC-DASH-003 | diagnose command registered in CLI group | P1 |
| TC-DASH-004 | bisect command registered in CLI group | P1 |
| TC-DASH-005 | COMMAND_SECTIONS includes diagnose and bisect | P2 |

---

## Summary

| Category | Test Cases | P1 | P2 |
|----------|-----------|----|----|
| Root-Cause Diagnosis | 26 | 17 | 9 |
| Run Bisection | 15 | 9 | 6 |
| Schema Validation | 15 | 11 | 4 |
| Streaming | 10 | 8 | 2 |
| Enhanced Diff | 10 | 7 | 3 |
| Dashboard Integration | 5 | 3 | 2 |
| **Total** | **81** | **55** | **26** |

## Quality Gates

| Gate | Target |
|------|--------|
| Test Execution | 100% |
| Pass Rate | >= 80% |
| P0 Bugs | 0 |
| P1 Bugs | <= 5 |
| All existing tests pass | Yes |
| Ruff lint clean | Yes |
