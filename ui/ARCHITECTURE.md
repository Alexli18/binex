# Binex Web UI Architecture

## Overview

The Binex Web UI is a single-page application for managing, debugging, and monitoring DAG-based agent workflows. It consists of a **React 18 + TypeScript frontend** (Vite, Tailwind CSS, shadcn/ui) served by a **FastAPI backend** that wraps the existing Binex Python runtime stores.

The frontend communicates with the backend via a REST API (`/api/v1/*`) and Server-Sent Events (SSE) for real-time run monitoring. In production the FastAPI server serves the pre-built React app as static files with SPA fallback routing.

## Component Tree

```
App
├── Sidebar (collapsible navigation, 6 groups)
│   ├── Workflows: Browse, Editor, Scaffold
│   ├── Runs: Dashboard, Compare (Diff), Bisect
│   ├── Analysis (requires runId): Debug, Diagnose, Trace, Lineage
│   ├── Costs & Budget: Cost Dashboard, Budget
│   ├── Export: Export Runs
│   └── System: Doctor, Plugins, Gateway
│
└── <Routes>
    ├── Dashboard ("/")
    │   └── NewRunModal
    ├── RunDetail ("/runs/:runId")
    │   ├── WorkflowGraph (dag/CustomNode)
    │   └── HumanPromptModal
    ├── RunLive ("/runs/:runId/live")
    │   ├── WorkflowGraph
    │   └── HumanPromptModal
    ├── WorkflowEditor ("/editor")
    │   ├── EditorToolbar
    │   ├── EditorCanvas (visual mode, React Flow)
    │   │   ├── EditableNode
    │   │   ├── NodePalette
    │   │   └── ModelSelect
    │   ├── EditorYaml (YAML mode, Monaco Editor)
    │   │   └── WorkflowGraph (live preview)
    │   └── EditorSidebar
    │       ├── CostEstimatePanel
    │       └── SaveAsModal
    ├── WorkflowBrowse ("/workflows")
    ├── Scaffold ("/scaffold")
    ├── DebugPage ("/runs/:runId/debug")
    │   ├── DebugNodeList
    │   ├── DebugNodeDetail
    │   │   ├── DebugArtifactViewer
    │   │   └── DebugErrorPanel
    │   └── ReplayModal
    ├── DiagnosePage ("/runs/:runId/diagnose")
    ├── TracePage ("/runs/:runId/trace")
    │   ├── TraceControls
    │   ├── TraceGantt
    │   └── TraceTable
    ├── LineagePage ("/runs/:runId/lineage")
    │   └── WorkflowGraph (lineage visualization)
    ├── DiffPage ("/diff")
    ├── BisectPage ("/bisect")
    ├── CostDashboard ("/costs")
    ├── BudgetPage ("/costs/budget")
    ├── ExportPage ("/export")
    ├── DoctorPage ("/system/doctor")
    ├── PluginsPage ("/system/plugins")
    └── GatewayPage ("/system/gateway")
```

### Shared Components

```
components/
├── common/
│   ├── StatusBadge        — status chip with colored dot (uses design tokens)
│   ├── ErrorBoundary      — React error boundary with retry
│   └── HelpTooltip        — inline ? icon with tooltip
├── layout/
│   ├── PageHeader         — consistent page title + breadcrumb
│   ├── PageShell          — standard page wrapper with padding
│   ├── EmptyState         — illustration + message for empty data
│   ├── LoadingState       — skeleton/spinner placeholder
│   └── ErrorState         — error message with retry action
└── ui/                    — shadcn/ui primitives
    ├── alert, badge, button, card, dialog, dropdown-menu,
    │   input, select, separator, skeleton, sonner, tabs, tooltip
    └── (all use Radix UI primitives + cn() for class merging)
```

## Data Flow

```
┌─────────────┐     React Query      ┌───────────┐     fetch()      ┌─────────────────┐
│  Components │ ◄──────────────────── │   Hooks   │ ──────────────► │   lib/api.ts     │
│  (pages)    │   queryKey cache      │ useRuns() │   /api/v1/*     │   ApiError class │
└─────────────┘                       │ useDebug()│                 └────────┬────────┘
                                      │ useTrace()│                          │
                                      │ useSSE()  │                          ▼
                                      └───────────┘                 ┌─────────────────┐
                                                                    │  FastAPI Server  │
                                                                    │  server.py       │
                                                                    │  /api/v1/ prefix │
                                                                    └────────┬────────┘
                                                                             │
                                                              ┌──────────────┼──────────────┐
                                                              ▼              ▼              ▼
                                                    ┌──────────────┐ ┌────────────┐ ┌────────────┐
                                                    │ SqliteExec   │ │ Filesystem │ │ EventBus   │
                                                    │ Store        │ │ Artifact   │ │ (in-memory │
                                                    │ (.binex/db)  │ │ Store      │ │ pub/sub)   │
                                                    └──────────────┘ └────────────┘ └────────────┘
```

Each API module uses a `_get_stores()` helper that returns `(SqliteExecutionStore, FilesystemArtifactStore)` pointing to `.binex/`. The stores are read-only for analysis endpoints; runs and workflows have write access.

## State Management

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| Server cache | `@tanstack/react-query` | All API data (runs, debug, trace, costs, workflows). Auto-refetch intervals for live data (runs: 5s, single run: 3s, gateway: 10s). |
| URL params | `react-router-dom` | Run ID (`:runId`), workflow file (`?file=`), page routing. Analysis pages derive context from URL. |
| Local component state | `useState` | UI toggles (filters, modals, selected items, editor mode). |
| SSE events | `useSSE` hook | Real-time run events. `EventSource` with exponential backoff reconnect. Events deduplicated by ID. Terminal events (`run:completed`, `run:cancelled`) stop reconnection. |
| Persistent UI prefs | `localStorage` | "What's New" dismissed state. |

## Design System

### Design Tokens (`lib/design-tokens.ts`)

Single source of truth for the dark theme palette:

- **Status colors**: `completed` (emerald), `running` (blue), `failed` (red), `cancelled` (slate), `pending` (slate), `skipped` (slate), `over_budget` (amber), `interrupted` (orange). Each has `bg`, `text`, `border`, `dot` variants.
- **Node type colors**: `llm` (violet), `local` (cyan), `a2a` (indigo), `human` (amber). Each has `bg`, `text`, `border`, `icon` variants.
- **Semantic colors**: `primary`, `success`, `danger`, `warning`, `info`, `muted` with `DEFAULT`, `hover`, `bg`, `bgSubtle`, `border`.
- **Surface tokens**: `base` (slate-950), `raised` (slate-900), `overlay`, `hover`, `border`, `divider`.
- **Typography**: `heading`, `body`, `muted`, `code`.

### shadcn/ui Components

Pre-configured Radix UI primitives in `components/ui/`: Alert, Badge, Button, Card, Dialog, DropdownMenu, Input, Select, Separator, Skeleton, Sonner (toast), Tabs, Tooltip.

### Tailwind Config

Custom theme extensions: `rounded-badge`, `animate-pulse-status`, `text-body-sm`. Dark theme with slate color base. PurgeCSS-safe via design token values.

### `cn()` Utility (`lib/utils.ts`)

```ts
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
```

Used everywhere for conditional + merged Tailwind classes.

## API Endpoints

All endpoints are prefixed with `/api/v1/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server health (uptime, version, store status, frontend built) |
| GET | `/config` | Server config (mode, version) |
| **Runs** | | |
| GET | `/runs` | List all runs (RunSummary[]) |
| GET | `/runs/{run_id}` | Single run details |
| POST | `/runs` | Create and start a new run |
| POST | `/runs/{run_id}/cancel` | Cancel a running workflow |
| GET | `/runs/{run_id}/records` | Execution records for a run |
| POST | `/runs/replay` | Replay a node with modified params |
| **Events (SSE)** | | |
| GET | `/runs/{run_id}/events` | SSE stream of run events |
| **Analysis** | | |
| GET | `/runs/{run_id}/debug` | Debug data (nodes, artifacts, errors) |
| GET | `/runs/{run_id}/diagnose` | Root cause analysis + recommendations |
| GET | `/runs/{run_id}/trace` | Timeline + anomaly detection |
| GET | `/runs/{run_id}/lineage` | Artifact lineage graph |
| **Artifacts** | | |
| GET | `/runs/{run_id}/artifacts` | All artifacts for a run |
| **Costs** | | |
| GET | `/runs/{run_id}/costs` | Cost breakdown for a run |
| GET | `/costs/dashboard` | Aggregated cost dashboard (period filter) |
| POST | `/costs/estimate` | Estimate cost for a workflow YAML |
| **Workflows** | | |
| GET | `/workflows` | List workflow YAML files |
| GET | `/workflows/{path}` | Read workflow file content |
| PUT | `/workflows/{path}` | Save/update workflow file |
| **Scaffold** | | |
| GET | `/scaffold/patterns` | List DSL patterns |
| POST | `/scaffold` | Generate workflow YAML from DSL/template |
| **Comparison** | | |
| POST | `/diff` | Compare two runs node-by-node |
| POST | `/bisect` | Find divergence point between good/bad runs |
| **Export** | | |
| POST | `/export` | Export runs as CSV/JSON (blob download) |
| **Prompts** | | |
| GET | `/prompts/templates` | List prompt templates |
| GET | `/prompts/templates/{name}` | Get template content |
| **System** | | |
| GET | `/system/doctor` | Health checks |
| GET | `/system/plugins` | List plugins |
| GET | `/system/gateway` | A2A gateway status + agents |

## SSE Event Flow

```
Browser                          Server (EventBus)
  │                                   │
  │  GET /api/v1/runs/{id}/events     │
  │ ─────────────────────────────────►│
  │                                   │
  │  ◄── event: node:started          │  (node begins execution)
  │  ◄── event: node:completed        │  (node finished, may include cost)
  │  ◄── event: node:failed           │  (node error)
  │  ◄── event: human:prompt_needed   │  (human-in-the-loop prompt)
  │  ◄── event: human:output          │  (human response received)
  │  ◄── event: run:completed         │  (terminal — close connection)
  │  ◄── event: run:cancelled         │  (terminal — close connection)
  │                                   │
```

### Connection Lifecycle

1. `useSSE(runId)` creates an `EventSource` to `/api/v1/runs/{runId}/events`
2. On `onopen`: state → `connected`, reset reconnect counter
3. On `onerror`: close connection, exponential backoff reconnect (1s → 2s → 4s → ... → 30s max)
4. Terminal events (`run:completed`, `run:cancelled`): close and stop reconnecting
5. Event deduplication via `lastEventId` tracking in a `Set`
6. On `runId` change: full reset (clear events, reset state, reconnect)

### EventBus (Backend)

Module-level singleton in `ui/api/events.py`. In-memory pub/sub — subscribers register per run ID. When a node completes, the orchestrator publishes events that are forwarded as SSE.

## File Structure

```
ui/                                 # Frontend (React + Vite)
├── index.html                      # Vite entry point
├── package.json                    # Dependencies
├── vite.config.ts                  # Vite config (proxy → FastAPI in dev)
├── tailwind.config.ts              # Tailwind theme
├── tsconfig.json                   # TypeScript config
├── vitest.config.ts                # Test config
└── src/
    ├── App.tsx                     # Router + layout (Sidebar + Routes)
    ├── main.tsx                    # React entry (QueryClientProvider, BrowserRouter, TooltipProvider)
    ├── index.css                   # Tailwind base + custom styles
    ├── pages/                      # Route-level components (18 pages)
    │   ├── Dashboard.tsx           # Run list + filters + NewRunModal
    │   ├── RunDetail.tsx           # Single run overview + DAG
    │   ├── RunLive.tsx             # Live run monitoring with SSE
    │   ├── WorkflowEditor.tsx      # YAML/visual editor orchestrator
    │   ├── WorkflowBrowse.tsx      # Workflow file browser
    │   ├── Scaffold.tsx            # DSL → YAML generator
    │   ├── DebugPage.tsx           # Node-level debug inspector
    │   ├── DiagnosePage.tsx        # Root cause analysis
    │   ├── TracePage.tsx           # Gantt timeline + anomalies
    │   ├── LineagePage.tsx         # Artifact lineage graph
    │   ├── DiffPage.tsx            # Run comparison
    │   ├── BisectPage.tsx          # Divergence finder
    │   ├── CostDashboard.tsx       # Cost analytics + charts
    │   ├── BudgetPage.tsx          # Budget configuration
    │   ├── ExportPage.tsx          # Run export (CSV/JSON)
    │   ├── DoctorPage.tsx          # System health checks
    │   ├── PluginsPage.tsx         # Plugin registry
    │   └── GatewayPage.tsx         # A2A gateway status
    ├── hooks/                      # React Query data hooks
    │   ├── useRuns.ts              # useRuns, useRun, useRecords, useCancelRun, useCreateRun
    │   ├── useAnalysis.ts          # useDebug, useTrace, useDiagnose, useLineage
    │   ├── useArtifacts.ts         # useArtifacts, useCosts
    │   ├── useWorkflows.ts         # useWorkflows, useWorkflow, useSaveWorkflow
    │   ├── useCostDashboard.ts     # useCostDashboard, useCostEstimate
    │   ├── useComparison.ts        # useDiff, useBisect
    │   ├── useUtilities.ts         # usePatterns, useScaffold, useExport, useDoctor, usePlugins, useGateway
    │   ├── usePromptTemplates.ts   # usePromptTemplates, usePromptTemplateContent
    │   └── useSSE.ts               # SSE connection with reconnect logic
    ├── lib/                        # Utilities
    │   ├── api.ts                  # HTTP client (get/post/put + ApiError)
    │   ├── types.ts                # Shared TypeScript types
    │   ├── design-tokens.ts        # Color/typography/surface tokens
    │   ├── utils.ts                # cn() class merge utility
    │   ├── yaml-to-graph.ts        # YAML → DAG nodes/edges + ELK layout
    │   └── graph-to-yaml.ts        # React Flow nodes → YAML serialization
    └── components/                 # Reusable components
        ├── Sidebar.tsx             # Main navigation (6 groups, collapsible)
        ├── CostEstimatePanel.tsx   # Workflow cost estimator
        ├── HumanPromptModal.tsx    # Human-in-the-loop UI
        ├── ReplayModal.tsx         # Node replay with param editing
        ├── SaveAsModal.tsx         # Save workflow as new file
        ├── common/                 # Shared domain components
        ├── layout/                 # Page structure components
        ├── ui/                     # shadcn/ui primitives
        ├── dag/                    # DAG visualization (React Flow)
        ├── editor/                 # Workflow editor sub-components
        ├── debug/                  # Debug page sub-components
        └── trace/                  # Trace page sub-components

src/binex/ui/                       # Backend (FastAPI)
├── __init__.py
├── server.py                       # App factory (create_app), CORS, static serving, health
├── static/                         # Pre-built React app (gitignored)
└── api/                            # API endpoint modules
    ├── __init__.py
    ├── errors.py                   # APIError exception class
    ├── events.py                   # EventBus singleton + SSE endpoint
    ├── runs.py                     # Run CRUD + replay
    ├── workflows.py                # Workflow file management
    ├── artifacts.py                # Artifact retrieval
    ├── debug.py                    # Debug endpoint
    ├── diagnose.py                 # Diagnose endpoint
    ├── trace.py                    # Trace endpoint
    ├── lineage.py                  # Lineage endpoint
    ├── costs.py                    # Per-run cost endpoint
    ├── cost_dashboard.py           # Aggregated cost analytics
    ├── estimate.py                 # Cost estimation
    ├── diff.py                     # Run comparison
    ├── bisect.py                   # Divergence analysis
    ├── export.py                   # Export to CSV/JSON
    ├── scaffold.py                 # DSL scaffold endpoint
    ├── prompt_templates.py         # Prompt template CRUD
    ├── prompts.py                  # Prompt management
    └── system.py                   # Doctor, plugins, gateway
```

## Key Patterns

### `_get_stores()` Helper
Every backend API module calls `_get_stores()` to get `(SqliteExecutionStore, FilesystemArtifactStore)`. These point to `.binex/binex.db` and `.binex/artifacts/`. SQLite stores have lazy init and **must** be closed after use (`await store.close()`). In tests, patch this helper to inject in-memory stores.

### ErrorBoundary
Class component wrapping page sections. Catches React render errors, shows an Alert with error details and a "Retry" button. Accepts optional custom `fallback` ReactNode.

### Skeleton Loading
Pages show `<Skeleton>` components (from shadcn/ui) during data loading. Sub-components export their own skeleton variants (e.g., `DebugNodeListSkeleton`, `DebugNodeDetailSkeleton`).

### React Query Patterns
- `queryKey` arrays for cache identity: `['runs']`, `['debug', runId, errorsOnly]`
- `enabled: !!runId` to prevent queries without required params
- `refetchInterval` for polling live data
- `useMutation` + `queryClient.invalidateQueries()` for write operations
- Toast notifications via `sonner` on success/error

### Design Token Usage
Components use `getStatusColors(status)` and `getNodeTypeColors(type)` from `design-tokens.ts` for consistent styling. The `StatusBadge` component demonstrates the pattern: token objects with `bg`, `text`, `border`, `dot` classes.

### Workflow Editor Modes
Two editing modes with bidirectional sync:
- **YAML mode**: Monaco editor with live DAG preview (debounced YAML → graph parsing)
- **Visual mode**: React Flow canvas with drag-and-drop nodes (graph → YAML serialization)

### SPA Routing
In production, `server.py` serves `index.html` for all non-`/api/*` GET requests, enabling client-side routing via React Router.
