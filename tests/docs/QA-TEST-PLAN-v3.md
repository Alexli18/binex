# QA Test Plan v3: Binex Runtime

**Project:** Binex — debuggable runtime for A2A agents
**Branch:** 006-system-prompt-tools
**Date:** 2026-03-08
**QA Engineer:** Claude (AI-assisted)
**Previous QA:** v2 (branch 004-cli-dx, 125 test cases, 870 tests)

---

## 1. Baseline

| Metric | Value |
|--------|-------|
| Total tests | 930 (all passing) |
| Lint | ruff clean (0 errors) |
| Known issues | 0 failing tests |
| Previous QA bugs | 2 found and fixed (v1), 0 new (v2) |
| New source files | 10 |
| Modified source files | 11 |
| New example workflows | 5 |

---

## 2. Scope

### In scope
- **Tool System** — `@tool` decorator, schema generation, tool calling loop, `python://` URIs
- **Human Adapters** — HumanApprovalAdapter, HumanInputAdapter
- **Conditional Execution** — `when` conditions, `==`/`!=` operators, node skipping
- **Start Wizard** — template selection, DSL, provider, project generation, inline execution
- **Init Command** — 3 mode types (workflow/agent/full), file generation
- **Hello Command** — zero-config demo, in-memory workflow
- **Debug Command** — `--json`, `--errors`, `--node`, `--rich` options
- **Debug Report** — build_debug_report, formatters (plain/json/rich)
- **Provider Registry** — 8 providers, defaults, env vars, agent prefixes
- **DSL Parser** — 16 predefined patterns, custom DSL, edge cases
- **Example Workflows** — 5 new YAML files validation
- **Integration** — tool calling + LLM adapter, conditional routing E2E, human-in-the-loop flow
- **Security** — tool execution sandboxing, input validation, path traversal regression
- **Regression** — existing v1/v2 bugs, existing functionality

### Out of scope
- Performance/load testing
- LLM output quality (non-deterministic)
- Third-party library internals (litellm, click, rich)
- UI testing (CLI-only)

---

## 3. Existing Test Coverage (New Features)

| Module | Test File | Tests | Assessment |
|--------|-----------|-------|------------|
| tools.py | test_tools.py | 25 | MEDIUM — нужны edge cases |
| cli/hello.py | test_cli_hello.py | 4 | LOW — только happy path |
| cli/init_cmd.py | test_cli_init.py | 7 | LOW — нет mode=agent/full |
| cli/start.py | test_cli_start.py | 24 | MEDIUM — нужны error paths |
| cli/debug.py | test_cli_debug.py | 5 | LOW — нет rich/json |
| cli/dsl_parser.py | test_dsl_parser.py | 19 | HIGH — хорошо |
| cli/providers.py | test_providers.py | 10 | HIGH — хорошо |
| adapters/human.py | test_human_adapter.py | 16 | HIGH — хорошо |
| trace/debug_report.py | test_debug_report.py | 10 | MEDIUM — нужны edge cases |
| trace/debug_rich.py | test_debug_rich.py | 2 | LOW — минимально |
| when conditions | test_when_conditions.py | 16 | HIGH — хорошо |
| example YAMLs | test_example_yamls.py | 13 | MEDIUM — нужна структурная валидация |

**Total existing (new features):** 151 тестов

---

## 4. Test Categories & Test Cases

### CAT-1: Tool System (P0 — Critical) — 20 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-TOOL-001 | `@tool` decorator — function becomes ToolDefinition | P0 | TODO | |
| TC-TOOL-002 | `build_tool_schema()` — str param → "string" | P1 | TODO | |
| TC-TOOL-003 | `build_tool_schema()` — int/float/bool mapping | P1 | TODO | |
| TC-TOOL-004 | `build_tool_schema()` — list/dict mapping | P1 | TODO | |
| TC-TOOL-005 | `build_tool_schema()` — no type hint → "string" fallback | P2 | TODO | |
| TC-TOOL-006 | `build_tool_schema()` — function without params | P2 | TODO | |
| TC-TOOL-007 | `load_python_tool()` — valid `python://module.func` | P0 | TODO | |
| TC-TOOL-008 | `load_python_tool()` — invalid URI (no module) | P1 | TODO | |
| TC-TOOL-009 | `load_python_tool()` — module not found → ImportError | P1 | TODO | |
| TC-TOOL-010 | `load_python_tool()` — function not found → AttributeError | P1 | TODO | |
| TC-TOOL-011 | `_resolve_inline_tool()` — YAML dict with name/desc/params | P1 | TODO | |
| TC-TOOL-012 | `_resolve_inline_tool()` — missing name → error | P2 | TODO | |
| TC-TOOL-013 | `resolve_tools()` — mixed specs (URI + inline dict) | P0 | TODO | |
| TC-TOOL-014 | `resolve_tools()` — empty list → empty | P2 | TODO | |
| TC-TOOL-015 | `execute_tool_call()` — sync function success | P0 | TODO | |
| TC-TOOL-016 | `execute_tool_call()` — async function success | P0 | TODO | |
| TC-TOOL-017 | `execute_tool_call()` — exception → error string | P1 | TODO | |
| TC-TOOL-018 | `execute_tool_call()` — tool without handler → error msg | P1 | TODO | |
| TC-TOOL-019 | `to_openai_schema()` — valid JSON schema output | P1 | TODO | |
| TC-TOOL-020 | Tool calling loop — max_tool_rounds enforcement | P0 | TODO | |

### CAT-2: LLM Adapter Tool Integration (P0 — Critical) — 12 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-LLM-001 | LLMAdapter with tools — schema sent to litellm | P0 | TODO | |
| TC-LLM-002 | Tool call response — loop processes tool_calls | P0 | TODO | |
| TC-LLM-003 | Multi-round tool calling — 3 rounds then final | P1 | TODO | |
| TC-LLM-004 | max_tool_rounds exceeded — loop stops | P0 | TODO | |
| TC-LLM-005 | Unknown tool in tool_calls — error message returned | P1 | TODO | |
| TC-LLM-006 | Tool call with invalid JSON args — error handled | P1 | TODO | |
| TC-LLM-007 | No tool_calls in response — normal output | P1 | TODO | |
| TC-LLM-008 | Tools=[] — no tools param sent to litellm | P2 | TODO | |
| TC-LLM-009 | Tool result appended as tool message | P1 | TODO | |
| TC-LLM-010 | Async tool in calling loop | P1 | TODO | |
| TC-LLM-011 | Tool call with workflow_dir context | P2 | TODO | |
| TC-LLM-012 | Tool exception doesn't crash adapter | P0 | TODO | |

### CAT-3: Conditional Execution — when (P0 — Critical) — 15 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-WHEN-001 | `when: "${node.output} == value"` — match → execute | P0 | TODO | |
| TC-WHEN-002 | `when: "${node.output} == value"` — no match → skip | P0 | TODO | |
| TC-WHEN-003 | `when: "${node.output} != value"` — match → execute | P0 | TODO | |
| TC-WHEN-004 | `when: "${node.output} != value"` — no match → skip | P0 | TODO | |
| TC-WHEN-005 | Skipped node counted in summary | P1 | TODO | |
| TC-WHEN-006 | Skipped node resolves dependencies for downstream | P0 | TODO | |
| TC-WHEN-007 | Validator — invalid when syntax → warning | P1 | TODO | |
| TC-WHEN-008 | Validator — when refs non-existent node → warning | P1 | TODO | |
| TC-WHEN-009 | Validator — when refs node not in depends_on → warning | P1 | TODO | |
| TC-WHEN-010 | Validator — valid when syntax → no warning | P2 | TODO | |
| TC-WHEN-011 | Fan-out conditional — both branches | P1 | TODO | |
| TC-WHEN-012 | Fan-out conditional — one branch skipped | P0 | TODO | |
| TC-WHEN-013 | when with spaces in value | P2 | TODO | |
| TC-WHEN-014 | when with empty value | P2 | TODO | |
| TC-WHEN-015 | Multiple nodes with when — cascading skips | P1 | TODO | |

### CAT-4: Human Adapters (P1 — High) — 12 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-HUM-001 | HumanApprovalAdapter — user approves → "approved" | P0 | TODO | |
| TC-HUM-002 | HumanApprovalAdapter — user rejects → "rejected" | P0 | TODO | |
| TC-HUM-003 | HumanApprovalAdapter — artifact type="decision" | P1 | TODO | |
| TC-HUM-004 | HumanApprovalAdapter — input artifacts displayed | P2 | TODO | |
| TC-HUM-005 | HumanInputAdapter — captures free text | P0 | TODO | |
| TC-HUM-006 | HumanInputAdapter — artifact type="human_input" | P1 | TODO | |
| TC-HUM-007 | HumanInputAdapter — system_prompt as question | P1 | TODO | |
| TC-HUM-008 | HumanInputAdapter — upstream context displayed | P2 | TODO | |
| TC-HUM-009 | Both adapters — health() returns ALIVE | P1 | TODO | |
| TC-HUM-010 | Both adapters — cancel() is no-op | P2 | TODO | |
| TC-HUM-011 | Both adapters — lineage derived_from inputs | P1 | TODO | |
| TC-HUM-012 | Registration — "human://approve" and "human://input" | P0 | TODO | |

### CAT-5: Start Wizard (P1 — High) — 15 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-START-001 | Template selection — 4 templates available | P1 | TODO | |
| TC-START-002 | Custom DSL input — parsed correctly | P1 | TODO | |
| TC-START-003 | Provider selection — top 3 (ollama, openai, anthropic) | P1 | TODO | |
| TC-START-004 | Provider "other" — shows all 8 | P2 | TODO | |
| TC-START-005 | Model name defaults per provider | P1 | TODO | |
| TC-START-006 | API key prompt — paid providers only | P1 | TODO | |
| TC-START-007 | API key skip — ollama (local, no key) | P2 | TODO | |
| TC-START-008 | Project dir creation — files generated | P0 | TODO | |
| TC-START-009 | workflow.yaml content — nodes match DSL | P0 | TODO | |
| TC-START-010 | .env file — API key written | P1 | TODO | |
| TC-START-011 | .gitignore generated | P2 | TODO | |
| TC-START-012 | build_start_workflow() — valid WorkflowSpec | P0 | TODO | |
| TC-START-013 | Inline execution — run now option | P1 | TODO | |
| TC-START-014 | Error — invalid DSL → graceful handling | P1 | TODO | |
| TC-START-015 | Progress callback during execution | P2 | TODO | |

### CAT-6: Init Command (P1 — High) — 12 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-INIT-001 | Mode=workflow — generates workflow.yaml + .env + .gitignore | P0 | TODO | |
| TC-INIT-002 | Mode=agent — adds agents/ directory | P1 | TODO | |
| TC-INIT-003 | Mode=full — adds tests + docker-compose | P1 | TODO | |
| TC-INIT-004 | Provider selection — all 8 providers | P1 | TODO | |
| TC-INIT-005 | Provider skip — no provider selected | P2 | TODO | |
| TC-INIT-006 | Model override — custom model name | P1 | TODO | |
| TC-INIT-007 | Non-empty dir — confirmation prompt | P1 | TODO | |
| TC-INIT-008 | Template content — workflow nodes correct | P1 | TODO | |
| TC-INIT-009 | .env.example — API key placeholder | P2 | TODO | |
| TC-INIT-010 | docker-compose.yml — Ollama service | P2 | TODO | |
| TC-INIT-011 | agent.py template — valid Python | P2 | TODO | |
| TC-INIT-012 | test_workflow.py template — valid pytest | P2 | TODO | |

### CAT-7: Hello Command (P1 — High) — 8 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-HELLO-001 | Execution — 2-node workflow completes | P0 | TODO | |
| TC-HELLO-002 | Output — greeter and responder results shown | P1 | TODO | |
| TC-HELLO-003 | In-memory workflow — no files created | P1 | TODO | |
| TC-HELLO-004 | Echo handler — greeter/responder behavior | P1 | TODO | |
| TC-HELLO-005 | Progress output on stderr | P2 | TODO | |
| TC-HELLO-006 | Store cleanup — close() called | P1 | TODO | |
| TC-HELLO-007 | Adapter registration — local://echo | P1 | TODO | |
| TC-HELLO-008 | Next steps message displayed | P2 | TODO | |

### CAT-8: Debug Command & Report (P1 — High) — 15 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-DBG-001 | debug <run_id> — plain text output | P0 | TODO | |
| TC-DBG-002 | debug --json — JSON serializable output | P0 | TODO | |
| TC-DBG-003 | debug --errors — only failed/timed_out nodes | P1 | TODO | |
| TC-DBG-004 | debug --node <id> — single node filter | P1 | TODO | |
| TC-DBG-005 | debug --rich — colored output (rich installed) | P1 | TODO | |
| TC-DBG-006 | debug --rich — fallback (rich not installed) | P2 | TODO | |
| TC-DBG-007 | debug <missing_run> — exit code 1 | P0 | TODO | |
| TC-DBG-008 | build_debug_report() — all nodes included | P1 | TODO | |
| TC-DBG-009 | build_debug_report() — skipped node inference | P1 | TODO | |
| TC-DBG-010 | build_debug_report() — duration calculation | P2 | TODO | |
| TC-DBG-011 | NodeReport — latency, prompt, model fields | P2 | TODO | |
| TC-DBG-012 | format_debug_report() — content truncation 500 chars | P2 | TODO | |
| TC-DBG-013 | format_debug_report_json() — complete structure | P1 | TODO | |
| TC-DBG-014 | Rich panels — color mapping (green/red/yellow/dim) | P2 | TODO | |
| TC-DBG-015 | Combined flags — --errors --json | P2 | TODO | |

### CAT-9: Provider Registry (P2 — Medium) — 8 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-PROV-001 | All 8 providers registered | P1 | TODO | |
| TC-PROV-002 | Default models per provider | P1 | TODO | |
| TC-PROV-003 | Env vars — None for ollama, set for others | P1 | TODO | |
| TC-PROV-004 | Agent prefixes — correct format | P1 | TODO | |
| TC-PROV-005 | get_provider() — valid name → config | P1 | TODO | |
| TC-PROV-006 | get_provider() — invalid name → None | P1 | TODO | |
| TC-PROV-007 | Provider used in start/init — prefix applied | P2 | TODO | |
| TC-PROV-008 | ProviderConfig dataclass — fields validated | P2 | TODO | |

### CAT-10: DSL Parser (P2 — Medium) — 12 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-DSL-001 | Linear pattern: A → B → C | P1 | TODO | |
| TC-DSL-002 | Fan-out pattern: A → B, C, D | P1 | TODO | |
| TC-DSL-003 | Fan-in pattern: A, B, C → D | P1 | TODO | |
| TC-DSL-004 | Fan-out-fan-in: A → B, C → D | P1 | TODO | |
| TC-DSL-005 | Diamond pattern | P1 | TODO | |
| TC-DSL-006 | All 16 predefined patterns valid | P0 | TODO | |
| TC-DSL-007 | Custom DSL — arbitrary topology | P1 | TODO | |
| TC-DSL-008 | Empty DSL → error | P1 | TODO | |
| TC-DSL-009 | Malformed DSL (empty node names) | P2 | TODO | |
| TC-DSL-010 | Node ordering preservation | P2 | TODO | |
| TC-DSL-011 | Edge deduplication | P2 | TODO | |
| TC-DSL-012 | depends_on map correctness | P1 | TODO | |

### CAT-11: Example Workflows (P2 — Medium) — 10 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-EX-001 | hello-world.yaml — loads, validates | P1 | TODO | |
| TC-EX-002 | human-in-the-loop.yaml — when conditions valid | P1 | TODO | |
| TC-EX-003 | multi-provider-research.yaml — 3 providers parsed | P1 | TODO | |
| TC-EX-004 | conditional-routing.yaml — fan-out + when | P1 | TODO | |
| TC-EX-005 | error-handling.yaml — retry config parsed | P1 | TODO | |
| TC-EX-006 | All new examples — schema-valid | P0 | TODO | |
| TC-EX-007 | diamond.yaml — DAG valid | P2 | TODO | |
| TC-EX-008 | fan-out-fan-in.yaml — structure valid | P2 | TODO | |
| TC-EX-009 | secure-pipeline.yaml — loads | P2 | TODO | |
| TC-EX-010 | All examples — unique node names | P2 | TODO | |

### CAT-12: Security & Regression (P0/P1) — 10 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-SEC-001 | Tool python:// URI — no arbitrary code execution | P0 | TODO | |
| TC-SEC-002 | Tool execution — exceptions contained | P0 | TODO | |
| TC-SEC-003 | Path traversal regression — BUG-001 still fixed | P0 | TODO | Regression |
| TC-SEC-004 | Lineage recursion regression — BUG-002 still fixed | P0 | TODO | Regression |
| TC-SEC-005 | yaml.safe_load used (never yaml.load) | P0 | TODO | |
| TC-SEC-006 | SQL injection — parameterized queries | P0 | TODO | |
| TC-SEC-007 | Tool schema injection — no code eval in schema | P1 | TODO | |
| TC-SEC-008 | Human adapter — no command injection via input | P1 | TODO | |
| TC-SEC-009 | when condition — no eval/exec used | P0 | TODO | |
| TC-SEC-010 | Start wizard — file write in project dir only | P1 | TODO | |

### CAT-13: Integration & E2E (P1 — High) — 10 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-E2E-001 | Hello command — full lifecycle | P0 | TODO | |
| TC-E2E-002 | Run + debug — execute workflow then inspect | P1 | TODO | |
| TC-E2E-003 | Conditional routing — skip branch E2E | P0 | TODO | |
| TC-E2E-004 | Human approval → conditional branch | P1 | TODO | |
| TC-E2E-005 | Tool calling → LLM response | P1 | TODO | |
| TC-E2E-006 | Multi-provider workflow (mocked) | P2 | TODO | |
| TC-E2E-007 | Start → init → run pipeline | P2 | TODO | |
| TC-E2E-008 | Error handling workflow — retry/deadline | P1 | TODO | |
| TC-E2E-009 | All CLI commands registered in main group | P0 | TODO | |
| TC-E2E-010 | Workflow with all adapter types (local, llm, human) | P1 | TODO | |

### CAT-14: Model/Spec Changes (P1 — High) — 6 cases

| ID | Test Case | Priority | Status | Notes |
|----|-----------|----------|--------|-------|
| TC-MOD-001 | NodeSpec.tools field — default empty list | P1 | TODO | |
| TC-MOD-002 | NodeSpec.tools — serializes to YAML | P1 | TODO | |
| TC-MOD-003 | TaskNode.tools — mirrors NodeSpec | P1 | TODO | |
| TC-MOD-004 | NodeSpec.when — optional string field | P1 | TODO | |
| TC-MOD-005 | WorkflowSpec — tools field loaded from YAML | P1 | TODO | |
| TC-MOD-006 | Validator — _check_when_conditions integration | P1 | TODO | |

---

## 5. Test Execution Plan

### Phase 1: Аудит и gap-анализ (CAT-9, CAT-10, CAT-11, CAT-14)
**Цель:** Проверить хорошо покрытые модули, найти пробелы
**Тесты:** 36 cases
**Фокус:** Providers, DSL, examples, model changes

### Phase 2: Core Features (CAT-1, CAT-2, CAT-3)
**Цель:** Глубокое тестирование критических новых фич
**Тесты:** 47 cases
**Фокус:** Tool system, LLM integration, conditional execution

### Phase 3: CLI & Adapters (CAT-4, CAT-5, CAT-6, CAT-7, CAT-8)
**Цель:** Тестирование CLI UX и human adapters
**Тесты:** 62 cases
**Фокус:** Start, init, hello, debug, human adapters

### Phase 4: Security & Integration (CAT-12, CAT-13)
**Цель:** Безопасность, регрессия, E2E
**Тесты:** 20 cases
**Фокус:** OWASP, regressions, end-to-end flows

---

## 6. Quality Gates

| Gate | Target | Blocker |
|------|--------|---------|
| Test Execution | 100% (165/165) | Yes |
| Pass Rate | ≥ 95% | Yes |
| P0 Bugs | 0 open | Yes |
| P1 Bugs | ≤ 3 open | Yes |
| Total Tests | ≥ 1050 | No |
| Lint (ruff) | 0 errors | Yes |
| All 930 existing tests | PASS | Yes |

---

## 7. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tool execution — arbitrary code | HIGH | Verify import restrictions, contained errors |
| when condition — code injection | HIGH | Verify no eval/exec, regex-only parsing |
| Interactive prompts hard to test | MEDIUM | Mock click.prompt, CliRunner |
| Rich optional dependency | LOW | Test with and without import |
| Async store cleanup | MEDIUM | Verify close() called in all paths |

---

## 8. Deliverables

- [ ] QA Test Plan v3 (this document)
- [ ] TEST-EXECUTION-TRACKING-v3.csv
- [ ] BUG-TRACKING-v3.csv (if bugs found)
- [ ] New test files: `tests/unit/test_qa_v3_*.py`
- [ ] Final report with quality gates assessment
