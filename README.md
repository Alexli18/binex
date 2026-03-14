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

Full workflow: drag & drop nodes, configure models and prompts, run with human input, see results, debug, trace, and lineage — all in the browser.

https://github.com/user-attachments/assets/YOUR_VIDEO_ID

> Upload `docs/demo/binex_EN.mp4` to GitHub and replace the link above.

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Installation

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Web UI

Launch the visual workflow editor:

```bash
binex ui
```

### Visual Drag & Drop Editor

Build workflows visually — drag nodes from the palette, connect them, configure models and prompts inline.

6 node types: **LLM Agent**, **Local Script**, **Human Input**, **Human Approve**, **Human Output**, **A2A Agent**

- 20+ preset models including 8 free OpenRouter models
- Built-in prompt library (Planner, Researcher, Analyzer, Writer, Reviewer, Summarizer)
- Switch between Visual and YAML modes — changes sync both ways
- Real-time cost estimation as you build
- Custom model input — use any litellm-compatible model

### 18 Pages — Full CLI Parity

| Category | Pages |
|----------|-------|
| **Workflows** | Browse, Visual Editor, Scaffold Wizard |
| **Runs** | Dashboard, RunLive (SSE), RunDetail |
| **Analysis** | Debug (input/output artifacts), Trace (Gantt timeline), Diagnose (root-cause), Lineage (artifact graph) |
| **Comparison** | Diff (side-by-side), Bisect (find divergence) |
| **Costs** | Cost Dashboard (charts), Budget Management |
| **System** | Doctor (health), Plugins, Gateway, Export |

### Replay

Debug any node → click Replay → swap the model or prompt → re-run just that node. No re-running the entire pipeline.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Quickstart

### CLI

```bash
# Zero-config demo
binex hello

# Run a workflow
binex run examples/simple.yaml

# Inspect the run
binex debug latest
binex trace latest
```

### Web UI

```bash
binex ui
```

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
    depends_on: [input]
    outputs: [output]

  researcher:
    agent: "llm://openrouter/google/gemma-3-27b-it:free"
    system_prompt: "Investigate and report findings"
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
| `binex cost show` | Cost breakdown per node |
| `binex explore` | Interactive TUI dashboard |
| `binex scaffold` | Generate workflow from DSL |
| `binex export` | Export to CSV/JSON |
| `binex doctor` | System health check |
| `binex hello` | Zero-config demo |

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

| Example | What it demonstrates |
|---------|---------------------|
| `simple.yaml` | Minimal two-node pipeline |
| `diamond.yaml` | Diamond dependency pattern |
| `fan-out-fan-in.yaml` | Parallel execution with aggregation |
| `human-in-the-loop.yaml` | Approval gates and conditional branching |
| `multi-provider-demo.yaml` | Multiple LLM providers in one workflow |
| `ollama-research.yaml` | Full research pipeline with Ollama + OpenRouter |
| `langchain-summarizer.yaml` | LangChain Runnable in a pipeline |
| `crewai-research-crew.yaml` | CrewAI Crew as a workflow node |
| `autogen-coding-team.yaml` | AutoGen Team for code generation |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Architecture

```
src/binex/
├── adapters/        # Agent backends (local, LLM, A2A, human, frameworks)
├── cli/             # Click CLI commands
├── graph/           # DAG construction + topological scheduling
├── models/          # Pydantic v2 domain models
├── plugins/         # Plugin registry for custom adapters
├── prompts/         # 121 built-in prompt templates
├── runtime/         # Orchestrator, dispatcher, replay engine
├── stores/          # SQLite execution + filesystem artifacts
├── trace/           # Debug, lineage, timeline, diffing
├── ui/              # FastAPI backend + React frontend
│   ├── api/         # 20 REST endpoints
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
