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

## Pages (18)

| Category | Pages |
|----------|-------|
| **Workflows** | WorkflowBrowse, WorkflowEditor, Scaffold |
| **Runs** | Dashboard, RunLive (SSE), RunDetail |
| **Analysis** | DebugPage, TracePage, DiagnosePage, LineagePage |
| **Comparison** | DiffPage, BisectPage |
| **Costs** | CostDashboard, BudgetPage |
| **System** | DoctorPage, PluginsPage, GatewayPage, ExportPage |

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
│   │   ├── common/      # Shared UI (NewRunModal, etc.)
│   │   ├── dag/         # React Flow DAG components
│   │   ├── debug/       # Debug detail panels
│   │   ├── editor/      # Visual workflow editor
│   │   ├── layout/      # PageShell, Breadcrumb, layout primitives
│   │   ├── trace/       # Gantt timeline components
│   │   └── ui/          # shadcn/ui primitives
│   ├── lib/             # Utilities
│   └── App.tsx          # Router & layout
├── public/
├── index.html
└── vite.config.ts
```
