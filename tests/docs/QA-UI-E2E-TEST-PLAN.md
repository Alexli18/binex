# Binex UI E2E Test Plan (Browser Layer)

**Version**: UI-E2E v1
**Suite**: `tests/e2e_playwright/` — pytest + Playwright (Chromium), Page Object Model
**Date**: 2026-08-06
**Total**: 25 test functions (53 collected items with parametrization)
**Tracking**: `UI-TEST-EXECUTION-TRACKING.csv`

## Scope

Browser-level end-to-end tests of the Web UI (`binex ui`): real server on
`:8420`, pre-built React frontend, store seeded with `binex hello`. Tests
interact only through the DOM (page objects, `data-testid` selectors) — no
API shortcuts. Engineering conventions (POM rules, fixtures, AAA) live in
`docs/contributing/testing.md`; this document is the QA-facing inventory.

## Test Categories

### Category 1: Smoke — Page Availability (TC-UI-001)

| ID | Title | Priority | pytest test |
|----|-------|----------|-------------|
| TC-UI-001 | All 13 routes render with expected heading (parametrized, incl. 404 page) | P0 | `test_recon.py::test_page_loads` |

### Category 2: Navigation & Sidebar (TC-UI-002 to TC-UI-006)

| ID | Title | Priority | pytest test |
|----|-------|----------|-------------|
| TC-UI-002 | Sidebar renders with all groups | P0 | `test_navigation.py::test_sidebar_renders` |
| TC-UI-003 | Sidebar group links visible | P1 | `test_navigation.py::test_sidebar_group_visible` |
| TC-UI-004 | Navigation between pages via sidebar | P0 | `test_navigation.py::test_sidebar_navigation` |
| TC-UI-005 | Sidebar collapse/expand | P2 | `test_navigation.py::test_sidebar_collapse_expand` |
| TC-UI-006 | Active nav item highlighted | P2 | `test_navigation.py::test_active_nav_state` |

### Category 3: Scaffold & Editor (TC-UI-007 to TC-UI-013)

| ID | Title | Priority | pytest test |
|----|-------|----------|-------------|
| TC-UI-007 | Scaffold from DSL string | P0 | `test_scaffold_flow.py::test_scaffold_flow_dsl` |
| TC-UI-008 | Scaffold from predefined template | P1 | `test_scaffold_flow.py::test_scaffold_flow_template` |
| TC-UI-009 | Scaffold blank workflow | P1 | `test_scaffold_flow.py::test_scaffold_flow_blank` |
| TC-UI-010 | Editor visual mode toggle | P0 | `test_visual_editor.py::test_editor_mode_toggle_visual` |
| TC-UI-011 | Editor YAML mode toggle | P0 | `test_visual_editor.py::test_editor_mode_toggle_yaml` |
| TC-UI-012 | Scaffold → Editor handoff flow | P1 | `test_visual_editor.py::test_scaffold_to_editor_flow` |
| TC-UI-013 | Save As modal | P1 | `test_visual_editor.py::test_editor_save_as_modal` |

### Category 4: Run Analysis (TC-UI-014 to TC-UI-018)

| ID | Title | Priority | pytest test |
|----|-------|----------|-------------|
| TC-UI-014 | RunDetail page renders for seeded run | P0 | `test_run_analysis.py::test_run_analysis_pages` |
| TC-UI-015 | Debug tab | P1 | `test_run_analysis.py::test_run_analysis_pages_debug` |
| TC-UI-016 | Trace tab | P1 | `test_run_analysis.py::test_run_analysis_pages_trace` |
| TC-UI-017 | Diagnose tab | P1 | `test_run_analysis.py::test_run_analysis_pages_diagnose` |
| TC-UI-018 | Lineage tab | P1 | `test_run_analysis.py::test_run_analysis_pages_lineage` |

### Category 5: Analysis & System Pages (TC-UI-019 to TC-UI-023)

| ID | Title | Priority | pytest test |
|----|-------|----------|-------------|
| TC-UI-019 | Diff + Bisect pages | P1 | `test_diff_bisect.py::test_diff_bisect_pages` |
| TC-UI-020 | Cost Dashboard | P1 | `test_cost_dashboard.py::test_cost_dashboard` |
| TC-UI-021 | System: Doctor | P1 | `test_system_pages.py::test_system_page_doctor` |
| TC-UI-022 | System: Plugins | P2 | `test_system_pages.py::test_system_page_plugins` |
| TC-UI-023 | System: Gateway | P2 | `test_system_pages.py::test_system_page_gateway` |

### Category 6: Export (TC-UI-024 to TC-UI-025)

| ID | Title | Priority | pytest test |
|----|-------|----------|-------------|
| TC-UI-024 | Export selected runs, CSV + JSON download (parametrized) | P0 | `test_export.py::test_export_selected_runs` |
| TC-UI-025 | Export "Last N runs" mode, file downloads | P0 | `test_export.py::test_export_last_n` |

## Bug Tracking

| Bug | Found by | Status |
|-----|----------|--------|
| [#112](https://github.com/Alexli18/binex/issues/112) — `/api/v1/export` had no `last_n` support | TC-UI-025 (pinned as `xfail(strict=True)`) | Fixed in PR #114, xfail removed |

Strict-xfail is the standing mechanism for known UI bugs: the failing test
stays in the suite pinned as `xfail(strict=True)`; the fix flips it to
XPASS(strict), forcing marker removal in the same change.
