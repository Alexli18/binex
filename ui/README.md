# Binex Web UI

React frontend for the Binex workflow orchestrator. Provides a visual drag-and-drop editor, real-time run monitoring, and full CLI parity in the browser.

## Tech Stack

- **React 18** + TypeScript
- **Vite** — build & dev server
- **Tailwind CSS** + **shadcn/ui** — styling & components
- **React Flow** + **ELK.js** — DAG visualization & auto-layout
- **Monaco Editor** — YAML editing with syntax highlighting
- **@tanstack/react-query** — data fetching & caching
- **js-yaml** — YAML parsing in browser
- **Recharts** — cost & timeline charts
- **Lucide React** — icons

## Pages (19)

| Category | Pages |
|----------|-------|
| **Workflows** | WorkflowBrowse, WorkflowEditor, Scaffold |
| **Runs** | Dashboard, RunLive (SSE), RunDetail |
| **Analysis** | DebugPage, TracePage, DiagnosePage, LineagePage |
| **Comparison** | DiffPage (filter bar, compare with previous), BisectPage (NodeMap, DAG viz, divergence metrics) |
| **Costs** | CostDashboard, BudgetPage |
| **System** | DoctorPage, PluginsPage, GatewayPage, ExportPage, SchedulerPage |

## Sidebar Navigation

4 collapsible groups: **Build** (Editor, Scaffold), **Runs** (Dashboard), **Analyze** (Compare, Bisect), **System** (Gateway, Plugins, Doctor). Run-specific pages open from run context menus.

## Development

```bash
# Install dependencies
npm install

# Dev server (hot reload, proxied to FastAPI backend)
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Lint
npm run lint
```

The dev server expects the FastAPI backend at `http://localhost:8000` (started via `binex ui --dev`).

## Production Build

```bash
# From repo root — builds frontend and copies to Python package
./scripts/build-ui.sh
```

The built assets are placed in `src/binex/ui/static/` and served by FastAPI in production mode.

## Project Structure

```
ui/
├── src/
│   ├── pages/           # 18 page components
│   ├── components/
│   │   ├── common/      # Shared UI (NewRunModal, ArtifactDiff, etc.)
│   │   ├── dag/         # React Flow DAG components (CustomNode, BisectNode)
│   │   ├── debug/       # Debug detail panels
│   │   ├── editor/      # Visual workflow editor (incl. LoopContainerNode, LoopConfigModal, ExitConditionBuilder)
│   │   ├── layout/      # PageShell, Breadcrumb, layout primitives
│   │   ├── trace/       # Gantt timeline components
│   │   └── ui/          # shadcn/ui primitives
│   ├── hooks/           # Custom hooks (usePreviousRun, etc.)
│   ├── lib/             # Utilities
│   └── App.tsx          # Router & layout
├── public/
├── index.html
└── vite.config.ts
```
