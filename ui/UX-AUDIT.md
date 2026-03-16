# Binex Web UI -- UX Audit Report

## Executive Summary

The Binex Web UI is a feature-rich developer tool with 18 pages covering workflow editing, run monitoring, debugging, cost analysis, and system management. The core functionality is solid and the visual design is consistent, but the experience suffers from a fragmented navigation structure, missing empty-state guidance on the landing page, and a disconnected edit-run-debug loop that forces users to jump between unrelated pages. The biggest opportunities lie in improving onboarding for new users, tightening the daily workflow cycle, and reducing the number of clicks in the debugging journey.

## User Journey Analysis

### Journey A: Onboarding

**Current flow:**
1. User runs `binex ui`, browser opens at `/` (Dashboard).
2. Dashboard loads runs list via `useRuns()` hook.
3. If no runs exist, user sees "No runs found" -- a single line of plain gray text (line 186, `Dashboard.tsx`).
4. The sidebar shows 6 nav groups: Workflows, Runs, Costs & Budget, Export, System. The "Analysis" group is hidden because no run is selected.
5. User must self-discover that they should navigate to "Browse" or "Scaffold" to create a workflow, or click "New Run" which requires pre-existing workflows.

**Pain points:**
1. The empty Dashboard shows only "No runs found" with no call-to-action, no getting-started instructions, and no link to create a workflow. A new user is stranded.
2. The "New Run" button on Dashboard opens a modal that requires selecting a workflow from a dropdown -- if no workflows exist, the dropdown is empty with no explanation.
3. There is no welcome screen, onboarding wizard, or first-time-user detection.
4. The sidebar navigation groups are unclear to new users. "Browse" vs "Editor" vs "Scaffold" is not self-explanatory. Which one creates a new workflow?
5. No documentation link or help button anywhere in the UI.

**Recommendations:**
1. **[P1]** Add an empty-state hero component to Dashboard when zero runs exist. Include: a brief explanation of Binex, a "Create your first workflow" CTA button linking to `/scaffold`, and a link to documentation.
2. **[P1]** In the NewRunModal, when the workflow list is empty, show an inline message: "No workflows found. Create one first." with a link to `/scaffold`.
3. **[P2]** Add a "?" help icon in the sidebar header that links to documentation or shows a quick-start tooltip.
4. **[P3]** Consider a one-time onboarding overlay/tour for first-time users that highlights the Scaffold -> Editor -> Run -> Debug flow.

### Journey B: Daily Workflow (Edit -> Run -> Analyze)

**Current flow:**
1. Navigate to `/workflows` (Browse page) to see workflow files.
2. Click "Edit" on a workflow -- navigates to `/editor?file=...` (but the Editor does not read the `file` query param; it auto-selects the first workflow from the list). This is a bug: `WorkflowEditor.tsx` line 184 uses `selectedPath` state initialized to `null` and only sets it via the file sidebar or `useEffect` that picks `workflows[0]`.
3. Edit the YAML or use visual mode.
4. Click "Run" in the toolbar -- this auto-saves and navigates to `/runs/{id}/live`.
5. Live view shows real-time SSE events, node statuses, and event log.
6. When run completes, auto-redirects to `/runs/{id}` (RunDetail) after 1.5 seconds.
7. RunDetail shows DAG graph, artifacts tab, costs tab. No direct link to editor to fix issues and re-run.
8. To edit and re-run, user must navigate back to `/editor` manually via sidebar.

**Pain points:**
1. **WorkflowBrowse "Edit" button does not correctly open the file in the editor.** The Editor page reads `location.state.initialContent` from Scaffold navigation but does not read URL query params (`?file=`). Both the Edit and Validate buttons in `WorkflowBrowse.tsx` (lines 88-111) navigate to `/editor?file=...` but this param is never consumed by `WorkflowEditor.tsx`.
2. The Editor-to-Run flow is actually good (1 click: "Run" button auto-saves and starts). But there is no way to get back to the editor from RunDetail or RunLive pages.
3. RunDetail has no "Re-run" or "Edit Workflow" button. The user must manually navigate to the Editor via sidebar.
4. The run completion auto-redirect (1.5s delay in `RunLive.tsx` line 47) may be too fast for users to notice what happened, or too slow if they want to see results immediately.
5. No toast/notification system -- save confirmations, run start confirmations, and errors are handled inconsistently (some use `alert()` at line 362 of `WorkflowEditor.tsx`, some use inline error text).
6. The Editor's file sidebar (left panel) does not indicate which files have been recently run or their last run status.

**Recommendations:**
1. **[P1]** Fix WorkflowBrowse -> Editor navigation: the Editor should read the `file` query parameter from the URL and select that workflow. Currently this flow is broken.
2. **[P1]** Add "Edit Workflow" and "Re-run" buttons to RunDetail header. "Edit Workflow" should navigate to `/editor` with the workflow pre-selected. "Re-run" should start a new run of the same workflow.
3. **[P2]** Replace `alert()` calls (WorkflowEditor line 362) with a toast notification system. Use it consistently for save success, run start, and errors.
4. **[P2]** On RunLive page, add a "View Results" button that appears when run completes, instead of auto-redirecting.
5. **[P3]** Add workflow run status indicators in the Editor file sidebar (green/red dot next to file names showing last run status).
6. **[P3]** Add a "Run History" link on the Editor toolbar that shows recent runs of the currently-open workflow.

### Journey C: Debugging

**Current flow:**
1. User sees a failed run in Dashboard (red status badge in the runs table).
2. Clicks the run ID link to go to `/runs/{id}` (RunDetail).
3. RunDetail shows the DAG graph with node statuses. User can click a failed node to see error in the side panel.
4. To get deeper debugging, user must know that the "Analysis" section exists in the sidebar. The Analysis nav group only appears when a run is selected (i.e., URL contains `/runs/{id}`).
5. User navigates to Debug (`/runs/{id}/debug`) -- sees node list with errors-only filter, can select a node to see full details including error, artifacts, agent info, and system prompt.
6. From Debug page, user can: click "View Trace" to see Gantt timeline, click "Diagnose" for automated root cause analysis, or click "Replay" to replay a specific node.
7. Diagnose page shows severity, root causes, latency anomalies, and recommendations.
8. To fix the issue, user must navigate back to the Editor (no direct link from Debug/Diagnose pages).

**Pain points:**
1. The Analysis sidebar group is hidden until a run URL is active. If a user is on `/costs` or `/export` and wants to debug a recent run, they must first navigate to a run detail page, then the Analysis links appear. There is no way to get to Debug/Diagnose/Trace/Lineage without first going through a run detail page.
2. No direct "Debug" link on the Dashboard runs table. Users must go RunDetail -> sidebar -> Debug (2 clicks minimum).
3. The Debug page has cross-links to Trace and Diagnose (lines 264-276), which is good. But there is no link from Debug/Diagnose back to the Editor to fix the workflow.
4. The Replay modal (`ReplayModal` launched from `DebugPage.tsx` line 363) allows replaying a node, but the result of the replay is unclear -- there is no indication of where replay results go.
5. Error messages in node details are displayed as raw text. No syntax highlighting, no stack trace formatting, no copy-to-clipboard button.
6. The Lineage page (`/runs/{id}/lineage`) is useful but disconnected from Debug. There is no way to see lineage for a specific node from the Debug page.
7. Breadcrumbs exist on Debug, Diagnose, Trace, and Lineage pages (good), but they are plain text links, not a proper breadcrumb component with consistent styling.

**Recommendations:**
1. **[P1]** Add a "Debug" quick-action button directly in the Dashboard runs table for failed runs. One click to go straight to the Debug page.
2. **[P1]** Add "Edit Workflow" and "Fix & Re-run" buttons to the Debug page header. The edit button should open the Editor with the workflow pre-loaded; the re-run button should start a new run.
3. **[P2]** Make the Analysis sidebar section accessible without requiring a run URL. Add a "Select Run" dropdown at the top of Analysis pages that lets users pick any run.
4. **[P2]** Add a copy-to-clipboard button on error messages in DebugPage node detail panel.
5. **[P2]** Add a "View Lineage" button in the Debug page node detail panel, linking to the Lineage page filtered for that node's artifacts.
6. **[P3]** Format stack traces in error displays with syntax highlighting (detect Python tracebacks, format accordingly).
7. **[P3]** Unify breadcrumb styling into a shared component used across all run-scoped pages.

## Page-by-Page Issues

### 1. Dashboard (`/`) -- `Dashboard.tsx`
- **Empty state** (line 186): Just "No runs found" in gray text. No CTA, no guidance.
- **No pagination**: All runs loaded at once. Will become unusable with hundreds of runs.
- **No sorting**: Table columns are not sortable. Users cannot sort by date, status, or cost.
- **Run ID display**: Full UUID shown (line 206). Should be truncated with copy-on-click.
- **No relative timestamps**: Shows absolute date via `toLocaleString()` (line 222). "2 hours ago" would be more scannable.

### 2. RunDetail (`/runs/:runId`) -- `RunDetail.tsx`
- **Auto-redirect to live** (line 18-21): If a run is still running, immediately redirects to live view. No way to see partial results without being on the live page.
- **Empty edges array** (line 40): `graphEdges` is hardcoded to `[]`, meaning the DAG graph shows nodes without connections. This defeats the purpose of the DAG visualization.
- **No action buttons**: No "Re-run", "Edit Workflow", "Export" actions in the header.
- **No link to Analysis pages**: User must use sidebar to navigate to Debug/Trace/Diagnose.

### 3. RunLive (`/runs/:runId/live`) -- `RunLive.tsx`
- **Auto-redirect timing** (line 47): 1.5s delay after completion is arbitrary. Should offer user control.
- **No progress indicator**: No percentage or progress bar showing how many nodes are complete.
- **No link back to editor**: If run fails, the only option is "Back to Editor" which appears only for pre-creation failures (line 89-95), not for runs that fail mid-execution.
- **Event log**: No filtering, no search within events. Becomes unusable for workflows with many nodes.

### 4. WorkflowEditor (`/editor`) -- `WorkflowEditor.tsx`
- **Does not read URL query params**: `?file=` parameter from WorkflowBrowse navigation is ignored. Only reads `location.state.initialContent` from Scaffold.
- **`alert()` usage** (line 362): Uses browser `alert()` for run failure -- should use toast notification.
- **No undo/redo indicators in visual mode**: Monaco editor has built-in undo, but visual mode has no undo support.
- **Node ID counter** (line 87): Uses module-level mutable `nodeIdCounter` -- resets on page navigation, could cause ID collisions.
- **No keyboard shortcut hints**: Save (Cmd+S), Run (Cmd+Enter) shortcuts are not shown or implemented.

### 5. WorkflowBrowse (`/workflows`) -- `WorkflowBrowse.tsx`
- **Good empty state** (lines 47-53): Has icon, message, and suggestion text. One of the better empty states.
- **"Validate" button** (lines 100-111): Both "Edit" and "Validate" buttons navigate to the same URL. Validate does nothing different from Edit.
- **No file metadata**: Does not show file size, last modified date, or number of nodes in the workflow.
- **No delete action**: Cannot delete workflow files from the UI.

### 6. Scaffold (`/scaffold`) -- `Scaffold.tsx`
- **Good multi-mode design**: DSL, Template, and Blank modes are well-organized.
- **Template mode generates then switches to DSL mode** (line 80): After selecting a template pattern, `setMode('dsl')` is called, which is confusing -- user expected to stay in template view.
- **No preview of generated YAML**: The generated YAML is shown but there is no DAG preview within the Scaffold page. User must click "Open in Editor" to see the graph.
- **No validation of DSL expression**: Invalid DSL expressions are sent to the server; no client-side validation or syntax hints.

### 7. DebugPage (`/runs/:runId/debug`) -- `DebugPage.tsx`
- **Good master-detail layout**: Node list with detail panel is effective.
- **Good filtering**: Errors-only toggle and text filter.
- **Good cross-links**: Links to Trace and Diagnose in header.
- **Replay button**: Present but unclear what happens after replay completes.
- **No node dependency visualization**: The debug page shows a flat list of nodes, not the DAG. User cannot see which nodes depend on the failed node.

### 8. DiagnosePage (`/runs/:runId/diagnose`) -- `DiagnosePage.tsx`
- **Good automated analysis**: Root causes, latency anomalies, and recommendations.
- **Good severity badge**: Clear visual indicator.
- **No actionability**: Recommendations are text-only. No "Fix this" or "Jump to node" buttons.
- **No empty state for successful runs**: Shows "No issues detected" which is correct but could include a positive summary (total nodes, cost, duration).

### 9. TracePage (`/runs/:runId/trace`) -- `TracePage.tsx`
- **Good Gantt chart**: Interactive timeline with tooltips, anomaly highlighting, and legend.
- **Good cross-links**: Links to Debug and Diagnose.
- **No zoom/pan on Gantt**: Fixed chart, no way to zoom into a specific time range.
- **No link from timeline bar to Debug node detail**: Clicking a bar shows basic info below the chart but does not link to the full Debug detail for that node.

### 10. LineagePage (`/runs/:runId/lineage`) -- `LineagePage.tsx`
- **Good ELK-based graph layout**: Automatic layout with artifact type coloring.
- **Good detail panel**: Click an artifact to see full content.
- **No search/filter**: Cannot filter artifacts by type or producer.
- **No link to producing node's debug detail**: "Produced by" field (line 282) is plain text, not a link.

### 11. DiffPage (`/diff`) -- `DiffPage.tsx`
- **Good diff visualization**: Inline diff with red/green highlighting.
- **No pre-selection**: If user navigated from a specific run, they must still manually select both runs from dropdowns.
- **Same-run comparison allowed**: Nothing prevents selecting the same run for both A and B.
- **No empty state**: Before comparison, shows nothing below the selectors. Could show instructions.

### 12. BisectPage (`/bisect`) -- `BisectPage.tsx`
- **Good similarity visualization**: Progress bar with color coding.
- **Good divergence details**: Shows good/bad outputs side-by-side with diff.
- **No explanation of what "bisect" means**: No help text explaining the concept to new users.
- **Threshold slider**: Good UX, but no explanation of what the threshold value means.

### 13. CostDashboard (`/costs`) -- `CostDashboard.tsx`
- **Good chart design**: Area chart for trends, bar charts for model/node breakdown.
- **Good period selector**: 24h, 7d, 30d, all.
- **Budget Used KPI** (line 40): Calculation is questionable -- divides total_cost by `avg_per_run * run_count`, which equals total_cost / total_cost = 100%. This seems like a bug or placeholder.
- **Loading state**: Just "Loading cost dashboard..." text. Should use skeleton loading like other pages.

### 14. BudgetPage (`/costs/budget`) -- `BudgetPage.tsx`
- **Config is display-only** (line 55-58): The info box explicitly says "values above are for reference only" -- this means the input fields are non-functional UI decoration. Very confusing.
- **Budget column in table** (line 87): Uses the local `maxCost` state value for all runs, not actual per-workflow budget config. Misleading data.
- **No ability to set budgets**: Despite having input fields, nothing is saved. Users must edit YAML manually.

### 15. ExportPage (`/export`) -- `ExportPage.tsx`
- **Good selection UX**: Toggle between specific runs and "last N" mode.
- **Good format options**: CSV/JSON toggle, include artifacts checkbox.
- **No preview**: Cannot preview what will be exported before downloading.
- **No webhook configuration**: The export page only handles file download, not the webhook feature mentioned in the feature plan.

### 16. DoctorPage (`/system/doctor`) -- `DoctorPage.tsx`
- **Good health check grid**: Clear pass/fail/warning visualization.
- **Good refresh button**: Manual refresh with loading indicator.
- **Good empty state**: Shows icon and message when no checks returned.
- **No auto-refresh**: Unlike Gateway page, Doctor does not mention auto-refresh.

### 17. PluginsPage (`/system/plugins`) -- `PluginsPage.tsx`
- **Good empty state**: Shows icon, message, and suggestion.
- **Read-only**: No ability to enable/disable plugins or install new ones.
- **No detail view**: Cannot see plugin configuration or capabilities beyond the table row.

### 18. GatewayPage (`/system/gateway`) -- `GatewayPage.tsx`
- **Good offline instructions**: Shows `binex gateway` command when offline.
- **Good online empty state**: Explains how to register agents.
- **Good auto-refresh note**: Mentions 10-second refresh cycle.
- **No ability to register/unregister agents**: Fully read-only.

## Navigation & Information Architecture

### Current Structure Assessment
The sidebar organizes 18 pages into 6 groups:
- **Workflows** (Browse, Editor, Scaffold) -- workflow authoring
- **Runs** (Dashboard, Compare, Bisect) -- run management and comparison
- **Analysis** (Debug, Diagnose, Trace, Lineage) -- run-scoped analysis, hidden until run selected
- **Costs & Budget** (Cost Dashboard, Budget) -- financial tracking
- **Export** (Export Runs) -- data export
- **System** (Doctor, Plugins, Gateway) -- infrastructure

**Issues:**
1. The Analysis group being hidden until a run is selected means users cannot discover these pages during onboarding. They appear suddenly when the URL changes.
2. The "Runs" group label is confusing because the Dashboard is nested under it but serves as the app's home page.
3. "Compare" and "Bisect" are in the "Runs" group but they are analysis tools that compare runs -- they could belong in "Analysis".
4. The "Export" group has only one item, which wastes vertical space.
5. No visual indicator in the sidebar showing which pages have data vs which are empty.

### Suggested Improvements
1. Rename the "Runs" group to "Overview" or remove the group label for Dashboard since it is the home page.
2. Move "Compare" and "Bisect" into the "Analysis" group (they are analysis tools).
3. Merge "Export" into "Runs" or into a top-level action.
4. Show the Analysis group always, but with a "select a run" prompt on each page (currently done for Debug, Diagnose, Trace, Lineage -- but the sidebar hides them).
5. Add a small badge/count to nav items (e.g., "Dashboard (5)" showing run count, "Plugins (3)" showing plugin count).

## Missing UX Patterns

- [ ] **Empty states with CTAs** -- Dashboard empty state is bare; Editor empty state just says "Select a workflow file to edit"
- [ ] **Breadcrumbs / context trail** -- Present on Analysis pages but inconsistent; missing on Workflows, Scaffold, Costs, Export, System pages
- [ ] **Keyboard shortcuts** -- No Cmd+K command palette, no Cmd+S save, no Cmd+Enter run, no keyboard navigation hints
- [ ] **Toast notifications for actions** -- Save, run start, export success use inconsistent patterns (alert, inline text, or nothing)
- [ ] **Command palette (Cmd+K)** -- No global search or command palette; critical for a developer tool
- [ ] **Contextual help / tooltips** -- No help text explaining features; Bisect threshold, Budget config, DSL syntax all lack explanatory tooltips
- [ ] **Loading skeletons** -- Used on some pages (WorkflowBrowse, DebugPage, DoctorPage) but not others (Dashboard, CostDashboard)
- [ ] **Pagination / virtual scrolling** -- No pagination on Dashboard runs table or any list views
- [ ] **Confirmation dialogs** -- No confirmation before destructive actions (e.g., cancel run)
- [ ] **Undo support** -- No undo for actions like cancelling a run
- [ ] **Responsive design** -- Sidebar collapse exists, but no mobile consideration (desktop-first is fine, but minimum tablet support would help)
- [ ] **Dark/light theme toggle** -- Hardcoded dark theme only
- [ ] **Auto-refresh on data pages** -- Dashboard and RunDetail do not auto-refresh; stale data between tab switches
- [ ] **URL state persistence** -- Filters on Dashboard (status, search) are lost on navigation; Editor mode (visual/yaml) is lost on navigation
- [ ] **Copy-to-clipboard** -- Run IDs, error messages, artifact contents have no copy buttons
- [ ] **Relative timestamps** -- All dates shown as absolute (`toLocaleString`); "2 min ago" would be more readable

## Priority Matrix

| Issue | Impact | Effort | Priority |
|-------|--------|--------|----------|
| Dashboard empty state with CTA | High | Low | P1 |
| Fix WorkflowBrowse->Editor navigation (query param bug) | High | Low | P1 |
| Add "Re-run" and "Edit Workflow" to RunDetail | High | Low | P1 |
| Add "Debug" quick-action to Dashboard failed runs | High | Low | P1 |
| Add "Edit Workflow" to Debug page | High | Low | P1 |
| NewRunModal empty workflow list guidance | Medium | Low | P1 |
| Toast notification system (replace alert()) | Medium | Medium | P2 |
| Show Analysis sidebar always (with run selector) | Medium | Medium | P2 |
| Copy-to-clipboard on error messages and run IDs | Medium | Low | P2 |
| RunLive completion: user-controlled redirect | Medium | Low | P2 |
| Loading skeleton consistency | Low | Low | P2 |
| Breadcrumb shared component | Low | Low | P2 |
| RunDetail: populate graph edges (currently hardcoded []) | High | Medium | P2 |
| BudgetPage: remove non-functional config inputs or make them functional | Medium | Medium | P2 |
| CostDashboard: fix Budget Used KPI calculation | Medium | Low | P2 |
| Keyboard shortcuts (Cmd+S save, Cmd+Enter run) | Medium | Medium | P3 |
| Command palette (Cmd+K) | Medium | High | P3 |
| Dashboard pagination | Medium | Medium | P3 |
| URL state persistence for filters | Low | Medium | P3 |
| Relative timestamps | Low | Low | P3 |
| Onboarding tour for first-time users | Low | High | P3 |
| WorkflowBrowse: remove duplicate "Validate" button | Low | Low | P3 |

## Recommended Phase 3 Tasks

Based on this audit, the following concrete tasks are recommended:

### Batch 1: Critical Flow Fixes (P1, ~2-3 days)
1. **Fix WorkflowBrowse -> Editor file param**: Read `?file=` query parameter in `WorkflowEditor.tsx` and select the corresponding workflow. File: `ui/src/pages/WorkflowEditor.tsx`.
2. **Dashboard empty state hero**: Create a `WelcomeHero` component shown when `runs.length === 0`. Include Binex logo, description, and "Create Workflow" CTA. File: `ui/src/pages/Dashboard.tsx`.
3. **RunDetail action buttons**: Add "Re-run", "Edit Workflow", and "Debug" buttons to RunDetail header. File: `ui/src/pages/RunDetail.tsx`.
4. **Dashboard quick-debug**: Add a "Debug" icon button in the runs table for failed runs. File: `ui/src/pages/Dashboard.tsx`.
5. **Debug page "Edit & Fix" button**: Add navigation to Editor with workflow path. File: `ui/src/pages/DebugPage.tsx`.
6. **NewRunModal guidance**: Show help text and link to Scaffold when workflow list is empty. File: `ui/src/pages/Dashboard.tsx`.

### Batch 2: Consistency & Polish (P2, ~3-4 days)
7. **Toast notification system**: Implement a toast provider component. Replace `alert()` in Editor. Use for save/run/export confirmations.
8. **RunDetail graph edges**: Wire up actual dependency edges from workflow spec into the DAG visualization. File: `ui/src/pages/RunDetail.tsx` line 40.
9. **Analysis section always visible**: Remove `requiresRunId` from Analysis nav group. Add a run selector dropdown to Debug/Diagnose/Trace/Lineage pages. File: `ui/src/components/Sidebar.tsx`.
10. **Copy-to-clipboard buttons**: Add to run IDs, error messages, and artifact content panels. Create a reusable `CopyButton` component.
11. **Loading skeleton consistency**: Apply skeleton loading pattern to Dashboard and CostDashboard (already used in WorkflowBrowse, DebugPage, DoctorPage).
12. **BudgetPage cleanup**: Either make the budget config inputs functional (via API) or remove them and show a read-only display with a note to edit YAML.
13. **CostDashboard Budget Used fix**: Fix the KPI calculation at line 40 to use actual budget configuration, not a self-referencing formula.

### Batch 3: Developer Experience (P3, ~2-3 days)
14. **Keyboard shortcuts**: Implement Cmd+S (save) and Cmd+Enter (run) in WorkflowEditor. Show shortcut hints on buttons.
15. **Breadcrumb component**: Create a shared `Breadcrumb` component and apply to all pages.
16. **Relative timestamps**: Use a `timeago` utility for the Dashboard runs table and RunDetail.
17. **URL state persistence**: Persist Dashboard filters (status, search) in URL query params.
18. **Remove duplicate "Validate" button**: In WorkflowBrowse, either differentiate Validate from Edit or remove it.
