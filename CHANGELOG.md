# Changelog

## Unreleased

### Security

- **SSRF protection for `fetch_url` / `http_request` (#59)** — the HTTP tools now resolve a URL's host and reject private, loopback, link-local, reserved, multicast, and unspecified addresses (RFC 1918, `127.0.0.0/8`, `169.254.0.0/16` cloud metadata, `::1`, `fc00::/7`, `0.0.0.0`) before connecting. Redirects are followed manually and every hop is re-validated, so a public URL can't `302` into the metadata service; only `http`/`https` schemes are allowed. Opt out for local use with `BINEX_ALLOW_PRIVATE_URLS=1`. Matters on servers running `binex gateway` / `binex scheduler`.
- **`shell_command` executable allowlist (#58)** — the built-in shell tool no longer runs arbitrary binaries chosen by the model. It now permits only a conservative default allowlist (`ls`, `cat`, `grep`, `wc`, …); `rm`, `curl`, `python -c ...`, etc. are blocked unless explicitly allowed via `BINEX_SHELL_ALLOW="python3,..."` or `BINEX_SHELL_ALLOW_ALL=1`. An absolute path can't bypass the check (it matches on the basename). A prompt-injected or confused agent can no longer run destructive or exfiltrating commands by default.

### Features

- **Model fallback chains** — a node can list `fallbacks: [model2, model3]`; when the primary model fails on an infrastructure error (rate limit `429`, `5xx`, timeout, model-not-found, or auth `401` with a loud warning), Binex moves to the next model instead of failing the whole run. It never falls back on a model that answered but poorly (that's auto-repair). For reproducibility — silent model swaps would corrupt diff/bisect/eval — each execution records `requested_model` and `actual_model`, the swap is stored on `artifact.metadata.fallbacks`, and `binex run --no-fallback` (or `BINEX_NO_FALLBACK=1`) disables the chain for clean benchmarks. `binex validate` warns when a fallback has a smaller context window than the primary or lacks function-calling while the node declares tools. (#66)
- **Node caching** — reuse a node's result when nothing that affects its output has changed, so editing a downstream prompt no longer forces re-running (and re-paying for) unchanged upstream nodes. The cache key is a content hash of the agent, resolved prompt, model parameters, tools, and input-artifact content; a hit is served at `$0` with a distinct `node:cache_hit` trace event pointing to the source run. Opt-in via per-node `cache: true` or run-level `binex run --cache`; `binex run --offline` runs only from cache (a miss fails the node — VCR-style iteration). New `binex clean cache [--older-than DAYS] [--dry-run]` clears the cache. (#68)
- **Auto-repair for structured output** — instead of failing (or blindly re-running) a node whose output doesn't match its `output_schema`, Binex now repairs it via a cheapest-first ladder: (1) **deterministic repair**, always on and zero-token — strips markdown fences, extracts the first balanced JSON value, drops trailing commas, and replaces the artifact content with clean JSON for downstream nodes (works for every agent type); (2) **native structured output** — `llm://` nodes whose model supports it get the schema passed into the completion call (`response_format`), detected per-model; (3) **feedback loop** — `repair: { max_attempts: N }` re-asks the model in-context with the validation errors, up to N times (`local://`/`a2a://` stay fail-fast). Repair tokens are counted in run cost; the artifact records `metadata.repair_attempts` and which step succeeded. (#65)

- **Event-driven scheduler** — the orchestrator now dispatches each node as soon as its dependencies complete, waking on the first completion (`asyncio.wait(FIRST_COMPLETED)`) instead of awaiting a whole batch. A slow node no longer blocks nodes whose dependencies already finished, and the busy-wait polling loop is gone. Combined with the concurrency cap, wide DAGs are both faster and safe. (#56)
- **Concurrency cap** — the orchestrator no longer dispatches unlimited nodes at once. A `concurrency` workflow field caps in-flight node execution, as a global scalar (`concurrency: 8`) or a per-provider mapping (`concurrency: {default: 8, openai: 5, ollama: 1}`). Providers are derived from the agent URI; a node holds a global slot plus its provider slot (acquired global-first, so no deadlock). Configurable via the `BINEX_MAX_CONCURRENCY` env var (default `8`); the workflow field takes precedence. Prevents wide fan-out (e.g. `scatter` with N=50) from tripping provider rate limits. (#55)
- **`binex resume <run-id>`** — continue a failed or interrupted run from where it stopped. Completed nodes are cached (artifacts reused, budget not re-spent); failed, timed-out, pending, and orphaned-running nodes are re-executed. The resumed run is a new immutable child linked via `resumed_from`. Partitioning is by node status (not a topological prefix), so parallel-branch failures resume correctly. Per-node drift detection re-runs only nodes whose definition changed; a topology change is refused unless `--force`. `cancelled`/`stopped` runs resume with a warning; `running` runs are refused without `--force` to avoid double execution. `--from <node>` forces re-execution from a node and its descendants. Budget is cumulative across the resume chain. (#54)
- **`binex cost simulate`** — estimate what a run would cost on a different model from its stored token counts and litellm pricing, with **zero LLM calls**. `--node NODE --model M` swaps one node; `--all-nodes M` re-prices the whole pipeline. Results are shown as a range, not a point: the swapped node gets a ±10% tokenizer band, nodes downstream of the swap get a wider band (a different model may change output length, cascading into downstream inputs), and unpriced models keep the original cost and are flagged. `--json` for machine-readable output. (#70)
### Bug Fixes

- **SQLite WAL mode** — the store now opens the database with `PRAGMA journal_mode=WAL` (plus `busy_timeout=5000` and `synchronous=NORMAL`). The Web UI can read run data while the orchestrator is actively writing execution/cost records, instead of hitting `database is locked` during live runs. (#57)

## v0.7.5

Amber redesign, pattern step editor, and repository polish.

### Features

- **Amber UI redesign** — full palette audit across editor, dashboard, and landing page. Amber primary token, sharp corners, JetBrains Mono typography, dark #0b0b0c base.
- **Pattern Step Editor** — per-step model, prompt, and `max_retries` overrides in the visual editor. Collapsible step rows with model inheritance display.
- **Per-step retry policy** — `max_retries` in YAML `steps:` block applies `RetryPolicy` with exponential backoff to individual pattern sub-nodes at runtime.
- **Built-in prompts** — 20 prompt templates for all 9 pattern types (`.md` files in prompt library + "Default" button in step editor).
- **Docs theme** — MkDocs documentation restyled to match landing page: amber accent, dark background, JetBrains Mono, no light mode.

### Bug Fixes

- **Dropdown clipping** — fixed `CollapsibleSection` `overflow-hidden` blocking ModelSelect dropdown in node editor.
- **Landing page links** — replaced all placeholder `href="#"` with real GitHub/docs URLs.
- **E2E navigation test** — updated sidebar collapse/active-link assertions for inline-style sidebar (no Tailwind classes).

### Chore

- Removed internal dev files from repo root: `SCAN_RESULTS.md`, `improvement_log.md`, `program.md`, `program_propose.md`, VHS tape scripts.

## v0.7.0

Pattern Nodes release — macro-node patterns that expand into full sub-DAG pipelines.

### Features

- **Pattern Nodes** — 9 built-in patterns: `critic`, `debate`, `best_of_n`, `reflexion`, `scatter`, `fsm`, `constitutional`, `chain_of_verification`, `plan_execute`. Each expands into a wired sub-DAG at runtime.
- **PatternExpander** — `expand_patterns()` resolves pattern nodes in a `WorkflowSpec` before execution. Handles nested pattern chains, back-edges (loops), and external `depends_on` wiring.
- **YAML integration** — patterns declared inline via `pattern:` field on any node; `config.steps` for per-step model/prompt overrides.
- **UI: Node Palette** — 9 pattern types in the DAG editor palette with icons and descriptions.
- **UI: Pattern Group** — collapsed sub-DAG view in the graph editor with expandable detail.
- **UI: Pattern Config** — per-step model, prompt, and config overrides in the sidebar.
- **Workflow cookbook** — example YAML workflows for all 9 patterns in `docs/`.

### Bug Fixes

- **Pattern expander** — fixed critical bug where cross-pattern `depends_on` was not rewired for expanded nodes (chained patterns produced stale pattern IDs).
- **`has_rich()`** — added `sys.stdout.isatty()` check to prevent Rich hanging in non-TTY environments (CI, CliRunner).
- **CI stability** — added `pytest-timeout` (30s per test) to prevent hanging tests from blocking CI indefinitely.

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
