<a id="readme-top"></a>

<div align="center">
  <h1>
    <br>
    Binex
    <br>
  </h1>

  <p align="center">
    <strong>Open-source visual orchestrator for AI agent workflows</strong>
    <br>
    Build, run, debug, and replay multi-agent pipelines — 100% locally.
  </p>

  <p>
    <a href="https://pypi.org/project/binex/"><img src="https://img.shields.io/pypi/v/binex?style=flat-square&color=orange" alt="PyPI"></a>
    <a href="https://pypi.org/project/binex/"><img src="https://img.shields.io/pypi/pyversions/binex?style=flat-square" alt="Python"></a>
    <a href="https://github.com/Alexli18/binex/blob/master/LICENSE"><img src="https://img.shields.io/github/license/Alexli18/binex?style=flat-square" alt="License"></a>
    <a href="https://github.com/Alexli18/binex/actions"><img src="https://img.shields.io/github/actions/workflow/status/Alexli18/binex/ci.yml?style=flat-square&label=CI" alt="CI"></a>
    <a href="https://github.com/Alexli18/binex/actions/workflows/e2e.yml"><img src="https://img.shields.io/github/actions/workflow/status/Alexli18/binex/e2e.yml?style=flat-square&label=E2E" alt="E2E"></a>
    <a href="https://github.com/Alexli18/binex/actions/workflows/coverage.yml"><img src="https://img.shields.io/github/actions/workflow/status/Alexli18/binex/coverage.yml?style=flat-square&label=coverage%E2%89%A580%25" alt="Coverage gate"></a>
    <a href="https://alexli18.github.io/binex/"><img src="https://img.shields.io/badge/docs-online-blue?style=flat-square" alt="Docs"></a>
    <a href="https://github.com/Alexli18/binex/stargazers"><img src="https://img.shields.io/github/stars/Alexli18/binex?style=flat-square" alt="Stars"></a>
  </p>

  <p>
    <a href="#demo">Demo</a> &middot;
    <a href="#installation">Install</a> &middot;
    <a href="#web-ui">Web UI</a> &middot;
    <a href="#features">Features</a> &middot;
    <a href="https://alexli18.github.io/binex/">Docs</a> &middot;
    <a href="https://github.com/Alexli18/binex/issues">Issues</a>
  </p>
</div>

<br>

---

## Demo

### 1. Start in seconds

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/assets/demo-start.gif" alt="Quick Start" width="800">
  <br><sub>Install, run <code>binex ui</code>, and you're building workflows</sub>
</div>

### 2. Build & run custom workflows

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/assets/demo-custom.gif" alt="Custom Workflow" width="800">
  <br><sub>Drag & drop nodes, configure models, run with human input</sub>
</div>

### 3. Explore & debug results

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/assets/demo-explore.gif" alt="Explore Results" width="800">
  <br><sub>Debug, trace, diff, lineage — full post-mortem inspection</sub>
</div>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## What is Binex?

Binex is an **open-source, fully local** runtime for AI agent workflows. No cloud. No telemetry. No vendor lock-in.

```
pip install binex
binex ui
```

That's it. Browser opens. You're building AI workflows.

### Why Binex?

- **100% local** — your data never leaves your machine
- **100% open source** — MIT licensed, audit every line
- **Zero telemetry** — no tracking, no analytics, no surprises
- **Full debuggability** — every input, output, prompt, and cost is visible
- **Any model** — OpenAI, Anthropic, Google, Ollama, OpenRouter, DeepSeek, and 40+ more via LiteLLM

### How it compares

LangGraph, CrewAI, and AutoGen are frameworks for **building** agents. Binex is a
**debuggable runtime** — it competes on everything *after* "run": trace, cost,
diff, bisect, replay, and regression gates, all local.

| Capability | Binex | LangGraph | CrewAI | AutoGen |
|---|:---:|:---:|:---:|:---:|
| Built-in trace / replay / diff / bisect | ✅ | ⚠️ hosted (LangSmith) | ❌ | ❌ |
| Per-node / per-call cost tracking | ✅ | ⚠️ | ⚠️ | ⚠️ |
| Regression safety net (eval + golden-run diff) | ✅ | ❌ | ❌ | ❌ |
| Visual editor **and** CLI | ✅ | ⚠️ Studio | ❌ | ⚠️ Studio |
| YAML workflows | ✅ | ❌ | ⚠️ | ❌ |
| Debug an existing run **without migrating** | ✅ observer | ❌ | ❌ | ❌ |
| Local-first, no cloud | ✅ | ✅ | ✅ | ✅ |

They also compose — point Binex's `observe()` at an existing CrewAI/LangGraph
run to get its debugging without migrating. Full breakdown, including where each
tool shines, in [docs/comparison.md](docs/comparison.md).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Installation

> **Requires Python 3.11+**

```bash
pip install binex
```

With extras:

```bash
pip install binex[langchain]    # LangChain Runnables
pip install binex[crewai]       # CrewAI Crews
pip install binex[autogen]      # AutoGen Teams
pip install binex[telemetry]    # OpenTelemetry tracing
pip install binex[rich]         # Rich colored CLI output
```

### Docker

Prefer a container? Run the CLI **and** Web UI without touching your Python
environment:

```bash
# From the repo root — builds the frontend + installs Binex, serves the Web UI.
docker compose -f docker/docker-compose.webui.yml up --build
# → open http://localhost:8420
```

Runs, artifacts, and workspaces persist in the `binex-data` volume. Pass API keys
via the environment (or a `.env` file), e.g. `OPENAI_API_KEY=… docker compose …`.
For a fully-local setup, add the bundled Ollama sidecar with `--profile local`.
Run one-off CLI commands against the same image:

```bash
docker build -f docker/Dockerfile.webui -t binex .
docker run --rm -v binex-data:/data binex binex run workflow.yaml
```

> The separate `docker/docker-compose.yml` is a different deployment — the A2A
> agent-server mesh (planner/researcher/… + Ollama + LiteLLM), not the Web UI.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Web UI

Launch the visual workflow editor:

```bash
binex ui
```

### Visual Drag & Drop Editor

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/screenshots/new-editor.png" alt="Workflow Editor" width="800">
  <br><sub>Collapsible node sections, tool picker with 10 built-in tools, MCP config, Visual ↔ YAML sync</sub>
</div>

<br>

6 node types: **LLM Agent**, **Local Script**, **Human Input**, **Human Approve**, **Human Output**, **A2A Agent**

- 20+ preset models including 8 free OpenRouter models
- Built-in prompt library (Planner, Researcher, Analyzer, Writer, Reviewer, Summarizer)
- **Tool Picker** — 10 built-in tools, MCP server integration, custom Python tools
- **Collapsible sections** — Model, Prompt, Tools, Advanced per LLM node
- **Workflow Settings** panel — configure MCP servers (stdio/HTTP) and cron schedules
- Switch between Visual and YAML modes — changes sync both ways (including tools & MCP)
- Real-time cost estimation as you build
- Custom model input — use any litellm-compatible model

### Dashboard

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/screenshots/new-dashboard.png" alt="Runs Dashboard" width="800">
  <br><sub>All runs at a glance — status, cost, duration</sub>
</div>

### Debugging & Analysis

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/screenshots/new-debug.png" alt="Debug View" width="380">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/screenshots/new-trace.png" alt="Trace Timeline" width="380">
  <br><sub>Left: Node-by-node debug inspection. Right: Gantt timeline with anomaly detection.</sub>
</div>

### Run Comparison

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/screenshots/new-diff.png" alt="Diff View" width="800">
  <br><sub>Side-by-side diff with filtering: changed, failed, cost delta</sub>
</div>

### 19 Pages — Full CLI Parity

| Category | Pages |
|----------|-------|
| **Workflows** | Browse, Visual Editor (with tool picker & MCP config), Scaffold Wizard |
| **Runs** | Dashboard, RunLive (SSE), RunDetail |
| **Analysis** | Debug (input/output artifacts), Trace (Gantt timeline), Diagnose (root-cause), Lineage (artifact graph) |
| **Comparison** | Diff (side-by-side with filter bar, compare with previous run), Bisect (NodeMap, DAG visualization, divergence metrics) |
| **Costs** | Cost Dashboard (charts), Budget Management |
| **System** | Doctor (health), Plugins, Gateway, Export, Scheduler (cron) |

### Navigation

Sidebar organized into 4 groups: **Build** (Editor, Scaffold), **Runs** (Dashboard), **Analyze** (Compare, Bisect), **System** (Gateway, Plugins, Doctor). Run-specific pages (Debug, Trace, Diagnose, Lineage, Costs) open from run context.

### Replay

Debug any node → click Replay → swap the model or prompt → re-run just that node. No re-running the entire pipeline.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Quickstart

### CLI

```bash
# Zero-config demo
binex hello
```

> **Tip:** Runs a 2-node demo workflow (producer → consumer), no API keys needed.

```bash
# Run a workflow
binex run examples/simple.yaml
```

> **Tip:** Uses your configured LLM provider. Set `OPENAI_API_KEY` or use `ollama` for fully local runs.

```bash
# Inspect the run
binex debug latest
binex trace latest
```

> **Tip:** `debug` shows per-node inputs/outputs. `trace` shows the execution timeline as a Gantt chart.

### Web UI

```bash
binex ui
```

> **Tip:** Opens the browser automatically. Use `--port 9000` to change the port, `--no-browser` to skip auto-open.

### Create a Workflow

```yaml
name: research-pipeline
nodes:
  input:
    agent: "human://input"
    outputs: [output]

  planner:
    agent: "llm://gemini/gemini-2.5-flash"
    system_prompt: "Break this topic into research questions"
    tools:
      - "builtin://web_search"
      - "builtin://calculator"
    depends_on: [input]
    outputs: [output]

  researcher:
    agent: "llm://openrouter/google/gemma-3-27b-it:free"
    system_prompt: "Investigate and report findings"
    tools:
      - "builtin://fetch_url"
    depends_on: [planner]
    outputs: [output]

  output:
    agent: "human://output"
    depends_on: [researcher]
    outputs: [output]
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Features

### Agent Adapters

| Prefix | Description |
|--------|-------------|
| `local://` | In-process Python callable |
| `llm://` | LLM via LiteLLM (40+ providers) |
| `a2a://` | Remote agent via A2A protocol |
| `human://input` | Free-text input from user |
| `human://approve` | Approval gate with conditional branching |
| `human://output` | Display results to user |
| `builtin://` | 10 built-in tools (calculator, web_search, shell_command, etc.) |
| `mcp://` | MCP server tools (stdio or HTTP transport) |
| `python://` | Custom Python function as tool |
| `langchain://` | LangChain Runnable (plugin) |
| `crewai://` | CrewAI Crew (plugin) |
| `autogen://` | AutoGen Team (plugin) |

### CLI Commands

| Command | Description |
|---------|-------------|
| `binex run` | Execute a workflow |
| `binex ui` | Launch Web UI |
| `binex debug` | Post-mortem inspection |
| `binex trace` | Execution timeline |
| `binex replay` | Re-run with agent swaps |
| `binex diff` | Compare two runs |
| `binex diagnose` | Root-cause failure analysis |
| `binex bisect` | Find first divergence between two runs |
| `binex cost show` | Cost breakdown per node |
| `binex explore` | Interactive TUI dashboard |
| `binex scaffold` | Generate workflow from DSL |
| `binex export` | Export to CSV/JSON |
| `binex doctor` | System health check |
| `binex hello` | Zero-config demo |
| `binex list` | List available workflows |
| `binex start` | Create a new project interactively |
| `binex init` | Deprecated alias for `binex start` |
| `binex validate` | Validate workflow YAML |
| `binex cancel` | Cancel a running workflow |
| `binex artifacts` | Inspect artifacts |
| `binex dev` | Local development environment |
| `binex gateway` | A2A Gateway management |
| `binex plugins` | Manage adapter plugins |
| `binex workflow` | Workflow versioning & inspection |
| `binex scheduler start` | Start cron-based workflow scheduler |
| `binex scheduler list` | List scheduled workflows |
| `binex scheduler add/remove` | Register/unregister workflow files |
| `binex eval run` | Run an eval suite against blessed baselines |
| `binex eval bless` | Approve current outputs as the new baseline |
| `binex eval golden` | Run a workflow and gate on assertions / a golden run |
| `binex import otel` | Import an OTLP/JSON trace as a Binex run |
| `binex collect` | Live OTLP/JSON collector endpoint |
| `binex mcp serve` | Expose Binex as an MCP server |

### Eval — Regression Testing for Agent Pipelines

Write a YAML test suite, bless a baseline, then catch regressions in CI:

```bash
binex eval run examples/eval/research-eval.yaml      # run an eval suite
binex eval bless examples/eval/research-eval.yaml    # approve outputs as the baseline
binex eval golden workflow.yaml --baseline run_abc   # gate one workflow on a golden run
```

A suite pairs inputs with assertions (contains, regex, JSON path, LLM judge). In CI, add
`binex eval run suite.yaml --format github --strict-baseline`. You can also import
production traces from any agent framework as runs: `binex import otel trace.json`.

### Use Binex from Your Coding Agent

```bash
claude mcp add binex -- binex mcp serve
```

Exposes runs, evals, and artifacts as MCP tools (`binex_debug`, `binex_eval_run`,
`binex_diff`) for Claude Code, Cursor, or any MCP-compatible agent.

### Pattern Nodes

9 built-in agentic patterns that expand into sub-DAG pipelines at runtime:

| Pattern | Description |
|---------|-------------|
| `critic` | draft → critique → refine (self-improvement loop) |
| `debate` | pro → con → judge (adversarial reasoning) |
| `best_of_n` | N parallel candidates → selector |
| `reflexion` | act → evaluate → reflect (iterative self-reflection) |
| `scatter` | mapper → N parallel workers → reducer (fan-out/fan-in) |
| `fsm` | finite state machine with configurable states and terminal |
| `constitutional` | draft → critique-per-principle → revise |
| `chain_of_verification` | draft → verify claims → synthesize |
| `plan_execute` | planner → N executors → aggregator |

```yaml
nodes:
  review:
    pattern: critic
    model: gpt-4o
    config:
      rounds: 2
    steps:
      critique:
        model: gpt-4o          # override per step
```

### LLM Providers

**OpenAI** &middot; **Anthropic** &middot; **Google Gemini** &middot; **Ollama** &middot; **OpenRouter** &middot; **Groq** &middot; **Mistral** &middot; **DeepSeek** &middot; **Together AI**

### Built With

[![Python][Python-badge]][Python-url]
[![React][React-badge]][React-url]
[![FastAPI][FastAPI-badge]][FastAPI-url]
[![TypeScript][TypeScript-badge]][TypeScript-url]
[![Tailwind][Tailwind-badge]][Tailwind-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Examples

29 example workflows in `examples/`. Highlights:

| Example | What it demonstrates |
|---------|---------------------|
| `simple.yaml` | Minimal two-node pipeline |
| `diamond.yaml` | Diamond dependency pattern |
| `fan-out-fan-in.yaml` | Parallel execution with aggregation |
| `human-in-the-loop.yaml` | Approval gates and conditional branching |
| `human-feedback.yaml` | Human feedback loop |
| `conditional-routing.yaml` | Conditional node execution |
| `multi-provider-demo.yaml` | Multiple LLM providers in one workflow |
| `ollama-research.yaml` | Full research pipeline with Ollama + OpenRouter |
| `budget-hard-limit.yaml` | Budget enforcement with hard stop |
| `budget-per-node.yaml` | Per-node budget allocation |
| `a2a-multi-agent.yaml` | A2A protocol multi-agent workflow |
| `langchain-summarizer.yaml` | LangChain Runnable in a pipeline |
| `crewai-research-crew.yaml` | CrewAI Crew as a workflow node |
| `autogen-coding-team.yaml` | AutoGen Team for code generation |
| `mixed-framework-pipeline.yaml` | LangChain + CrewAI + AutoGen in one pipeline |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Architecture

```
src/binex/
├── adapters/        # Agent backends (local, LLM, A2A, human, frameworks)
├── agents/          # Agent definitions and configuration
├── cli/             # Click CLI commands
├── gateway/         # A2A Gateway server and routing
├── graph/           # DAG construction + topological scheduling
├── models/          # Pydantic v2 domain models
├── plugins/         # Plugin registry for custom adapters
├── prompts/         # 112 built-in prompt templates
├── registry/        # Provider and adapter registry
├── runtime/         # Orchestrator, dispatcher, replay engine
├── patterns/        # PatternExpander + 9 pattern templates
├── scheduler/       # Cron-based workflow scheduling
├── stores/          # SQLite execution + filesystem artifacts
├── tools/           # @tool decorator, 10 built-in tools, MCP client
├── trace/           # Debug, lineage, timeline, diffing
├── ui/              # FastAPI backend + React frontend
│   ├── api/         # 32 REST endpoints
│   └── static/      # Pre-built React app
└── workflow_spec/   # YAML loader + validator
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Documentation

Full docs at **[alexli18.github.io/binex](https://alexli18.github.io/binex/)**

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Contributing

Contributions are welcome! If you find this useful:

- **Star the repo** — it takes 1 second and helps more than you know
- **Open issues** — tell me what's broken or what you need
- **Submit PRs** — let's build this together

I'm a solo developer building this in the open. Every star, issue, and PR makes a real difference.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Configuration

Binex can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BINEX_STORE_PATH` | `.binex` | Directory for SQLite database and artifacts |
| `BINEX_DEFAULT_DEADLINE_MS` | `120000` | Default node timeout in milliseconds |
| `BINEX_DEFAULT_MAX_RETRIES` | `1` | Default retry count for failed nodes |
| `BINEX_DEFAULT_BACKOFF` | `exponential` | Retry backoff strategy (`fixed` or `exponential`) |
| `BINEX_REGISTRY_URL` | `http://localhost:8000` | Default A2A agent registry URL |

All data is stored in `.binex/` (gitignored by default):
- `.binex/binex.db` — SQLite database (runs, execution records, cost records)
- `.binex/artifacts/` — JSON artifact files

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

<div align="center">
  <sub>Built by a solo dev who believes AI agents shouldn't be black boxes.</sub>
  <br>
  <sub>No cloud. No telemetry. No surprises. Just debuggable AI workflows.</sub>
</div>

<!-- MARKDOWN LINKS -->
[Python-badge]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://python.org
[React-badge]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[FastAPI-badge]: https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white
[FastAPI-url]: https://fastapi.tiangolo.com/
[TypeScript-badge]: https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white
[TypeScript-url]: https://www.typescriptlang.org/
[Tailwind-badge]: https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white
[Tailwind-url]: https://tailwindcss.com/
