# Changelog

## v0.6.5

Security, Performance & Observability release.

### Security (CRITICAL)

- **shell_command** — patched command injection: replaced `shell=True` with `shell=False` + `shlex.split()`. Shell metacharacters no longer interpreted.
- **calculator** — patched arbitrary code execution: replaced raw `eval()` with AST whitelist validation. Only math expressions and whitelisted functions permitted.

### Features

- **binex-trace SDK** — lightweight A2A agent tracing via structured JSON on stderr. API: `trace.task()`, `trace.log()`, `trace.checkpoint()`. Zero runtime dependencies.
- **Trace events storage** — trace events persisted in SQLite alongside execution records
- **`binex trace subtasks`** — new CLI command to render subtask tree from captured stderr
- **`binex trace node --node`** — show trace events in node detail view

### Performance

- **Cost dashboard** — batch SELECT + SQL aggregation replacing N+1 queries
- **CAO sessions** — batch UPDATE for session status changes

### Documentation

- **Trace SDK guide** — `docs/features/trace-sdk.md`
- **Security model** — `docs/features/security.md`

## v0.6.4

Type Safety & Performance release.

### Features

- **Mypy strict type annotations** — full typing added to all modules (cli, ui, runtime, trace, agents, tools, models, stores)
- **Query pagination** — `limit` and `offset` parameters on `list_runs()` for large dataset handling
- **Scheduler documentation** — new `docs/cli/scheduler.md` with CLI commands, YAML config, and examples
- **Tools & MCP documentation** — new `docs/features/tools-mcp.md` covering built-in tools, MCP servers, and security

### Fixes

- **SQLite column order** — replaced `SELECT *` with explicit column list to fix migration-induced column order mismatch
- **Diff page inline display** — artifact diffs now render inline under the table row instead of at the bottom of the page
- **5 real type mismatches** caught and corrected by mypy strict checking
- **71 ruff lint errors** fixed (I001 import sorting, E501 line length, F401 unused imports)
- **Exception logging** — swallowed exceptions now logged in observability module
- **Budget checks** — made non-blocking for Web UI responsiveness
- **Artifact access safety** — guard against empty artifact lists in runtime dispatcher

### Performance

- **SQLite indexes** — added on `cao_sessions.status` and `run_id` for execution/cost records
- **Cost calculation** — new `get_node_cost()` to avoid loading all cost records during budget checks
- **Replay artifacts** — batch-fetch to eliminate N+1 queries
- **BFS scheduler** — `deque.popleft()` instead of `list.pop(0)` for O(1)
- **HTTP client** — reuse `httpx.AsyncClient` in A2A adapters and health checker

## v0.6.3

Logo & Landing redesign release.

### Features

- **Logo redesign** — "Binary Flow" mark from binary tree DAG paths, purple→cyan gradient, new favicon
- **Landing page redesign** — "Electric Minimalism with Cinematic Motion" — asymmetrical hero, staggered features grid, Syne + Inter fonts, entrance animations
- **Blog plugin** — mkdocs-blog integration with first post

### Fixes

- Human workflows — pre-create run record to prevent live page 404
- Blog post improvements — content clarity, CTA, og:image

## v0.6.2

Web UI Tools & Scheduler release.

### Features

- **Built-in Tools** — 10 built-in tools: calculator, dice_roll, fetch_url, http_request, web_search, read_file, write_file, shell_command, json_parse, random_choice
- **MCP Server Integration** — Model Context Protocol support via stdio and HTTP/SSE transports
- **Tools in Web UI Editor** — tool picker, MCP config panel, collapsible sections for LLM nodes
- **Scheduler Cron** — `schedule` field for cron expressions; `binex scheduler start/list/add/remove` CLI commands
- **Cost Dashboard** — `/costs` page with KPI cards, trend chart, cost breakdown, budget status

### Fixes

- Cost dashboard route and diff page combobox selectors
- Select component option handling in E2E tests

## v0.6.1

PyPI compatibility release.

### Fixes

- README images converted to absolute GitHub URLs for PyPI display

## v0.6.0

Web UI Enhancement release.

### Features

- **Scaffold redesign** — template cards with categories, MiniGraph SVG preview, node count badges; 4→5 categories (new: Agentic Patterns)
- **3 new agentic patterns** — reflection, plan-execute-verify, dry-run-harness (20 scaffold templates total)
- **8 workflow prompts** — planner, analyzer, executor, task decomposer, and more for DAG-native roles (119 prompts total)
- **Prompt Library** — new Build page with search, category tabs, markdown preview, "Use in Editor" integration; custom prompt creation with built-in deletion protection
- **Model Selector v2** — provider-aware selection via `GET /api/v1/providers`, searchable Command popover, tier badges, configured vs unconfigured providers, recently used models
- **`binex list`** — discover available workflows in current directory and examples (`--json` supported)
- **`binex start` consolidation** — `binex init` now alias for `binex start`; added `--quick` flag for non-interactive setup
- **README refresh** — inline screenshots, 3-panel GIF demo, quickstart callouts
- **Landing page** — project website with feature overview

### Fixes

- Editor visual mode sync — YAML↔canvas changes now propagate correctly
- HelpPanel z-index overlap with editor sidebar resolved
- Scaffold prompt inlining — generated YAML now includes system_prompt content instead of placeholder text

### Notes

- `__version__` synced with pyproject.toml (was 0.4.0, now 0.6.0)
- New API endpoint: `GET /api/v1/providers` for model selector
- Scaffold API now includes `category`, `description`, `use_case`, `node_count` fields

## v0.4.0

Observability & Persistence release.

### Features

- **OpenTelemetry integration** — optional run-level and node-level tracing spans (`binex.run`, `binex.node.<id>`), zero overhead when disabled (no-op fallback)
- **Workflow schema versioning** — `version` field on workflows (default 1), migration framework for future schema changes
- **Workflow snapshots** — every `binex run` stores an immutable SHA256-deduplicated snapshot of the workflow definition in SQLite
- **`binex workflow version <file>`** — display the schema version of a workflow file
- **`binex workflow diff <run1> <run2>`** — compare workflow definitions used in two different runs (unified diff)
- **CSV/JSON export** — `binex export <run-id>` for run data export (`--format json`, `--last N`, `--include-artifacts`)
- **Webhook notifications** — run lifecycle events (completed, failed, budget exceeded) sent to configured webhook URLs

### Installation

```bash
pip install binex[telemetry]   # OpenTelemetry tracing (optional)
```

### Notes

- Existing workflows without a `version` field default to version 1 (backward compatible)
- `workflow_snapshots` SQLite table and `workflow_hash` column added via lazy migration
- OTEL tracing activates only when `opentelemetry` is installed AND `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_TRACES_EXPORTER` is set

## v0.3.0

Framework Adapters release.

### Features

- A2A Gateway — standalone proxy with routing, auth, fallback, health checking
- LangChain adapter — run LangChain chains as workflow nodes
- CrewAI adapter — integrate CrewAI crews via A2A protocol
- AutoGen adapter — bridge AutoGen agents into Binex pipelines
- Plugin system for custom adapters via entry points

## v0.2.0

Developer Experience release.

### Features

- `binex diagnose <run-id>` — automated root-cause analysis for failed runs
- `binex bisect <run-id>` — binary search for regression-introducing node
- Streaming output for long-running LLM nodes
- Improved `binex diff` with side-by-side artifact comparison
- Node output schema validation (`output_schema` in YAML)

## v0.1.0

First public release.

### Features

- DAG-based workflow runtime with topological scheduling
- Artifact lineage tracking across pipeline steps
- Replayable workflows with agent swap support
- Run diffing for side-by-side comparison
- CLI interface: run, debug, trace, replay, diff, artifacts, explore, scaffold, validate, doctor
- Agent adapters: LLM (via LiteLLM), local Python, A2A protocol, human-in-the-loop
- Human approval gates with conditional branching
- 9 LLM providers out of the box (OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Groq, Mistral, DeepSeek, Together)
- Rich colored output (optional)
- SQLite execution store + filesystem artifact store
- Interactive project initialization wizard
- DSL shorthand for workflow generation
- MkDocs documentation site
