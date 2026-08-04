<a id="readme-top"></a>

<div align="center">
  <h1>
    <br>
    Binex
    <br>
  </h1>

  <p align="center">
    <strong>Debugger + regression-testing toolkit for AI agent pipelines (local-first)</strong>
    <br>
    Replay, diff, bisect, and eval multi-agent workflows — 100% on your machine.
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
    <a href="#installation">Install</a> &middot;
    <a href="#debugging">Debug & Replay</a> &middot;
    <a href="#eval">Eval</a> &middot;
    <a href="#web-ui">Web UI</a> &middot;
    <a href="#orchestration">Orchestration</a> &middot;
    <a href="https://alexli18.github.io/binex/">Docs</a>
  </p>
</div>

<br>

---

## Installation

> **Requires Python 3.11+**

```bash
pip install binex
binex hello          # zero-config smoke test
```

Optional extras: `binex[telemetry]` (OTel), `binex[langchain]`, `binex[crewai]`, `binex[autogen]`, `binex[rich]`.

All data is stored locally in `.binex/` — SQLite database + JSON artifact files. No cloud, no telemetry.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

<a id="debugging"></a>

## Debugging & Replay

Every run stores the full execution trace: inputs, outputs, prompts, costs, timing. Inspect it without re-running anything.

```bash
binex run examples/simple.yaml          # run a workflow
binex debug latest                      # per-node inputs/outputs
binex trace latest                      # Gantt timeline with anomaly detection
binex replay latest --node planner      # re-run one node with a different model/prompt
```

Compare two runs to find regressions:

```bash
binex diff run-abc123 run-def456        # side-by-side artifact diff + cost delta
binex bisect run-abc123 run-def456      # find the first node where outputs diverged
binex diagnose latest                   # root-cause failure analysis
```

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/assets/demo-explore.gif" alt="Explore Results" width="800">
  <br><sub>Debug, trace, diff, lineage — full post-mortem inspection</sub>
</div>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

<a id="eval"></a>

## Eval — Regression Testing for Agent Pipelines

Write a YAML test suite, bless a baseline, then catch regressions in CI.

```bash
# Run an eval suite
binex eval run examples/eval/research-eval.yaml

# Approve current outputs as the new baseline
binex eval bless examples/eval/research-eval.yaml

# Re-run and compare against the baseline
binex eval run examples/eval/research-eval.yaml

# List all stored baselines
binex eval baselines
```

An eval suite pairs inputs with assertions (contains, JSON path, LLM judge, cost threshold). Use in CI:

```yaml
# .github/workflows/eval.yml
- run: binex eval run examples/eval/research-eval.yaml --format github --strict-baseline
```

Import OTel spans from any agent framework to create test cases from production traces:

```bash
binex import otel trace.json
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Web UI

```bash
binex ui        # opens browser automatically; --port 9000 to change
```

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/screenshots/new-dashboard.png" alt="Runs Dashboard" width="800">
  <br><sub>All runs at a glance — status, cost, duration</sub>
</div>

<br>

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/screenshots/new-debug.png" alt="Debug View" width="380">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/screenshots/new-diff.png" alt="Diff View" width="380">
  <br><sub>Left: per-node debug inspection. Right: side-by-side diff with changed / failed / cost delta filters.</sub>
</div>

Full parity with CLI: dashboard, visual editor, debug, trace, diff, bisect, lineage, cost charts, eval results, scheduler, gateway, plugins, export, doctor.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Use Binex from your coding agent

Expose Binex as an MCP server so Claude Code, Cursor, or any MCP-compatible agent can query runs, trigger evals, and inspect artifacts directly:

```bash
claude mcp add binex -- binex mcp serve
```

Once added, your agent can call tools like `binex_debug`, `binex_eval_run`, and `binex_diff` without leaving its context.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

<a id="orchestration"></a>

## Orchestration

Binex also runs the workflows it debugs. Define pipelines in YAML, or use the visual editor.

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/assets/demo-custom.gif" alt="Custom Workflow" width="800">
  <br><sub>Drag & drop nodes, configure models, run with human input</sub>
</div>

<br>

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/screenshots/new-editor.png" alt="Workflow Editor" width="800">
  <br><sub>Visual editor — drag & drop nodes, tool picker, MCP config, Visual ↔ YAML sync</sub>
</div>

### Adapters

`local://` · `llm://` · `a2a://` · `human://input|approve|output` · `cao://` (CLI agents) · `langchain://` · `crewai://` · `autogen://`

Full adapter reference → [docs](https://alexli18.github.io/binex/)

### Providers

OpenAI · Anthropic · Google Gemini · Ollama · OpenRouter · Groq · Mistral · DeepSeek · Together AI (and 40+ more via LiteLLM)

Selected examples: `simple.yaml`, `fan-out-fan-in.yaml`, `human-in-the-loop.yaml`, `budget-hard-limit.yaml`, `a2a-multi-agent.yaml`, `mixed-framework-pipeline.yaml`, `eval/research-eval.yaml`. Full list + CLI reference → [docs](https://alexli18.github.io/binex/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Architecture

```
src/binex/
├── adapters/        # local, LLM, A2A, human, CAO, framework adapters
├── cli/             # Click CLI commands
├── eval/            # eval engine: loader, runner, assertions, baselines
├── importers/       # OTel span importer
├── mcp_server/      # MCP server (binex mcp serve)
├── models/          # Pydantic v2 domain models
├── runtime/         # orchestrator, dispatcher, replay engine
├── scheduler/       # cron-based workflow scheduling
├── stores/          # SQLite execution + filesystem artifacts
├── tools/           # @tool decorator, 10 built-in tools, MCP client
├── trace/           # debug, lineage, timeline, diffing
├── ui/              # FastAPI backend + React frontend (19 pages)
└── workflow_spec/   # YAML loader + validator
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Contributing

Contributions are welcome. Star the repo, open issues, submit PRs. Fork → branch → PR.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

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
