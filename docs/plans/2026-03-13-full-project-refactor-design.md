# Full Project Refactor — Design Document

**Date**: 2026-03-13
**Branch**: 009-advanced-debugging
**Approach**: Bottom-Up by layers, iterative execution

## Goals

1. Structural refactoring — split mega-files into focused modules
2. Reduce cognitive complexity — all functions below CC 15
3. Eliminate code duplication across layers
4. Separate UI/presentation from business logic in CLI layer

## Constraints

- All 1200+ existing tests must pass after each change
- API changes allowed but require explicit approval before implementation
- CLI commands remain stable (user-facing behavior unchanged)
- No performance regression >10%

## Metrics Baseline (2026-03-13)

- **Total**: 14,527 lines, 94 files
- **Lint**: 0 ruff errors
- **CC >15 (complexipy)**: 20 functions
- **MI grade C**: 1 file (cli/explore.py, MI=0.00)
- **Tests**: 1204 passing

## Layer 1-2: models, stores, adapters, graph, workflow_spec (~2300 lines)

Minimal changes — these layers are clean.

### stores/backends/sqlite.py (302 lines)
- Make migration error handling explicit (log warnings instead of silent catch)
- Consolidate `_row_to_*` static methods if possible

### adapters/llm.py (291 lines)
- Extract `_accumulate_cost` helper logic
- Consider extracting tool-loop into focused method

### graph/scheduler.py (101 lines)
- Add parameter validation to `reset_chain`

## Layer 3: runtime (~1074 lines)

### orchestrator.py (558 lines) → split into 3 modules

**New modules:**
- `runtime/budget.py` (~80 lines) — `BudgetManager` class
  - `check_batch_budget()`, `budget_pre_check()`, `budget_post_check()`, `skip_all_remaining()`
- `runtime/back_edge.py` (~40 lines) — `evaluate_back_edge()` function
- `runtime/orchestrator.py` (~400 lines) — coordinator, delegates to above

### replay.py + orchestrator.py → shared execution

**New module:**
- `runtime/_node_executor.py` (~100 lines) — shared `execute_node()` logic
  - Used by both `Orchestrator._execute_node` and `ReplayEngine._execute_node`
  - Eliminates ~90% code duplication

### Unchanged: dispatcher.py, schema_validator.py, lifecycle.py

## Layer 4: trace (~2073 lines)

### bisect.py (550 lines) → split into 3 modules

- `trace/bisect_core.py` (~200 lines) — `find_divergence`, `bisect_report`, validation
- `trace/bisect_format.py` (~150 lines) — `divergence_to_dict`, `bisect_report_to_dict`
- `trace/bisect_compare.py` (~100 lines) — shared comparison logic with diff.py

### trace_rich.py (380 lines)
- Remove duplicated `_topo_sort`, use `DAG.topological_order()` instead

### diagnose.py (290 lines)
- Extract magic numbers (3.0x threshold) to named constants
- Make advice mapping data-driven

### diff.py + bisect.py shared logic
- Extract content comparison into `trace/_compare.py` shared helper

### Unchanged: debug_report.py, debug_rich.py, lineage.py, tracer.py

## Layer 5: CLI (~7839 lines)

### explore.py (1247 lines) → split into 6 modules

| Module | Contents | ~Lines |
|--------|----------|--------|
| `cli/explore.py` | Entry + `_dashboard()` router | 150 |
| `cli/explore_browser.py` | Run list/selection UI | 100 |
| `cli/explore_actions.py` | All `_action_*()` handlers | 250 |
| `cli/explore_ui.py` | Dashboard/node/artifact rendering | 400 |
| `cli/explore_replay.py` | Replay sub-flow | 150 |
| `cli/explore_utils.py` | `_short_id`, `_time_ago`, helpers | 50 |

### bisect.py CLI (475 lines)
- Extract formatting → `cli/bisect_format.py` (~200 lines)

### cost.py (231 lines, CC=21-22)
- Extract method to reduce CC in `print_cost_text` and `_cost_history`

### dev.py (136 lines, CC=23) + doctor.py (176 lines, CC=20)
- Extract individual checks into helper functions

### start.py family (1764 lines, 4 files)
- Remove circular re-exports from `start.py`
- Tests import directly from sub-modules
- Point CC reduction in `_custom_interactive_wizard` (CC=18), `_step_mode_topology` (CC=18)

### run.py (402 lines)
- Extract progress wrappers → `cli/run_progress.py`
- Reuse in `hello.py` (eliminate duplication)

### prompt_roles.py (670 lines) → YAML data files
- Move templates to `src/binex/prompts/roles/*.yaml`
- `prompt_roles.py` becomes thin loader (~50 lines)
- API changes: `get_role(name)` loads from YAML instead of dict literal

### Remaining CLI files
- Point CC reduction where >15 (validate.py, init_cmd.py, dsl_parser.py, start_config.py, start_templates.py)
- No structural changes needed

## Execution Order

1. Layer 1-2: stores, adapters, graph (low risk, 1 commit)
2. Layer 3: runtime split (medium risk, 2-3 commits)
3. Layer 4: trace split (medium risk, 2-3 commits)
4. Layer 5a: explore.py split (high impact, 1 commit)
5. Layer 5b: prompt_roles → YAML (API change, 1 commit)
6. Layer 5c: bisect/cost/dev/doctor CC reduction (1-2 commits)
7. Layer 5d: start family cleanup + run progress extraction (1 commit)
8. Layer 5e: remaining CC reduction (1 commit)

## Success Criteria

- [ ] 0 functions with CC >15 (complexipy)
- [ ] 0 files with MI grade C (radon)
- [ ] No file >500 lines in src/binex/
- [ ] All 1200+ tests passing
- [ ] 0 ruff lint errors
- [ ] UI separated from business logic in CLI layer
