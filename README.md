<a id="readme-top"></a>

<div align="center">
  <h1>
    <br>
    Binex
    <br>
  </h1>

  <p align="center">
    <strong>Debuggable runtime for AI agent pipelines</strong>
    <br>
    Orchestrate multi-agent workflows. Trace every step. Replay and diff runs.
  </p>

  <p>
    <a href="https://pypi.org/project/binex/"><img src="https://img.shields.io/pypi/v/binex?style=flat-square&color=orange" alt="PyPI"></a>
    <a href="https://pypi.org/project/binex/"><img src="https://img.shields.io/pypi/pyversions/binex?style=flat-square" alt="Python"></a>
    <a href="https://github.com/Alexli18/binex/blob/master/LICENSE"><img src="https://img.shields.io/github/license/Alexli18/binex?style=flat-square" alt="License"></a>
    <a href="https://github.com/Alexli18/binex/actions"><img src="https://img.shields.io/github/actions/workflow/status/Alexli18/binex/ci.yml?style=flat-square&label=CI" alt="CI"></a>
    <a href="https://alexli18.github.io/binex/"><img src="https://img.shields.io/badge/docs-online-blue?style=flat-square" alt="Docs"></a>
  </p>

  <p>
    <a href="#installation">Installation</a> &middot;
    <a href="#quickstart">Quickstart</a> &middot;
    <a href="#demo">Demo</a> &middot;
    <a href="https://alexli18.github.io/binex/">Documentation</a> &middot;
    <a href="https://github.com/Alexli18/binex/issues">Issues</a>
  </p>
</div>

<br>

---

## What is Binex?

Binex is a debuggable runtime for AI agent workflows.

It executes DAG-based pipelines of agents (LLM, local, remote A2A, or human),
tracks artifacts between steps, and allows replaying and inspecting runs.

**Key features:**

- **DAG-based execution** &mdash; define agent pipelines as readable YAML, not tangled code
- **Artifact lineage** &mdash; every input and output tracked across the entire pipeline
- **Replayable workflows** &mdash; re-run with agent swaps, compare results
- **Full tracing** &mdash; every node call, every artifact, every millisecond recorded
- **Post-mortem debugging** &mdash; inspect any run after the fact with rich reports
- **Run diffing** &mdash; compare two executions side-by-side to spot regressions
- **Human-in-the-loop** &mdash; approval gates and free-text input with conditional branching
- **Budget & cost tracking** &mdash; per-node cost records, budget enforcement (stop/warn), CLI cost inspection
- **Framework adapters** &mdash; plug in LangChain, CrewAI, or AutoGen agents with a single URI
- **Plugin system** &mdash; extend Binex with custom adapter plugins via entry points
- **CLI-first DX** &mdash; everything accessible from the terminal

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Installation

Install from PyPI:

```bash
pip install binex
```

With framework adapters:

```bash
pip install binex[langchain]    # LangChain Runnables
pip install binex[crewai]       # CrewAI Crews
pip install binex[autogen]      # AutoGen Teams
pip install binex[langchain,crewai,autogen]  # all three
```

For rich colored output:

```bash
pip install binex[rich]
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Quickstart

Run the built-in demo (no config needed):

```bash
binex hello
```

Create a workflow file `workflow.yaml`:

```yaml
name: hello
nodes:
  greet:
    agent: "local://echo"
    inputs:
      msg: "hello world"
    outputs: [response]

  respond:
    agent: "local://echo"
    inputs:
      greeting: "${greet.response}"
    depends_on: [greet]
```

Run it:

```bash
binex run workflow.yaml
```

Inspect the run:

```bash
binex debug latest
binex trace latest
```

<details>
<summary><strong>See it in action</strong></summary>

```
$ binex hello

Running built-in hello-world workflow...

  [1/2] greeter ...
  [greeter] -> result:
Hello from Binex!

  [2/2] responder ...
  [responder] -> result:
{"greeter": "Hello from Binex!"}

Run completed (2/2 nodes)
Run ID: run_d71c9a50

Next steps:
  binex debug run_d71c9a50    — inspect the run
  binex init                  — create your own project
  binex run examples/simple.yaml — try a workflow file
```

</details>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Demo

A multi-provider research pipeline: **Ollama** runs locally for planning and summarization, **OpenRouter** calls cloud models for parallel research &mdash; all in one YAML file.

<details>
<summary><strong>Requirements to run this demo</strong></summary>

- [Ollama](https://ollama.com/) installed and running locally
- Model pulled: `ollama pull gemma3:4b`
- Free [OpenRouter](https://openrouter.ai/) API key (set `OPENROUTER_API_KEY` in `.env`)
- Binex installed: `pip install binex`

</details>

```yaml
# examples/multi-provider-demo.yaml
name: multi-provider-research

nodes:
  user_input:
    agent: "human://input"

  planner:
    agent: "llm://ollama/gemma3:4b"
    system_prompt: "Create a structured research plan with 3 subtopics..."
    inputs: { topic: "${user_input.result}" }
    depends_on: [user_input]

  researcher1:
    agent: "llm://openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    inputs: { plan: "${planner.result}" }
    depends_on: [planner]

  researcher2:
    agent: "llm://openrouter/nvidia/nemotron-3-super-120b-a12b:free"
    inputs: { plan: "${planner.result}" }
    depends_on: [planner]

  summarizer:
    agent: "llm://ollama/gemma3:4b"
    inputs: { research1: "${researcher1.result}", research2: "${researcher2.result}" }
    depends_on: [researcher1, researcher2]
```

<div align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggTFIKICAgIEFbInVzZXJfaW5wdXQ8YnIvPjxzdWI+aHVtYW46Ly9pbnB1dDwvc3ViPiJdIC0tPiBCWyJwbGFubmVyPGJyLz48c3ViPm9sbGFtYS9nZW1tYTM6NGI8L3N1Yj4iXQogICAgQiAtLT4gQ1sicmVzZWFyY2hlcjE8YnIvPjxzdWI+b3BlbnJvdXRlci9uZW1vdHJvbi0zLXN1cGVyPC9zdWI+Il0KICAgIEIgLS0+IERbInJlc2VhcmNoZXIyPGJyLz48c3ViPm9wZW5yb3V0ZXIvbmVtb3Ryb24tMy1zdXBlcjwvc3ViPiJdCiAgICBDIC0tPiBFWyJzdW1tYXJpemVyPGJyLz48c3ViPm9sbGFtYS9nZW1tYTM6NGI8L3N1Yj4iXQogICAgRCAtLT4gRQ==?type=png&bgColor=white" alt="Demo DAG" width="700">
</div>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Start Wizard

Create a full research pipeline from a template in seconds:

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/assets/demo-start.gif" alt="binex start" width="800">
</div>

Or build your own workflow node-by-node with the custom constructor:

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/assets/demo-custom.gif" alt="binex start custom" width="800">
</div>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Explore Dashboard

Interactive run inspector &mdash; trace, graph, cost, artifacts, node detail, debug &mdash; all in one place:

<div align="center">
  <img src="https://raw.githubusercontent.com/Alexli18/binex/master/assets/demo-explore.gif" alt="binex explore" width="800">
</div>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## How It Works

Define a workflow in YAML. Binex builds a DAG, schedules nodes respecting dependencies, dispatches each to the right agent adapter, and records everything.

```yaml
name: research-pipeline
description: "Fan-out research with human approval"

nodes:
  planner:
    agent: "llm://openai/gpt-4"
    system_prompt: "Break this topic into 3 research questions"
    inputs:
      topic: "${user.topic}"
    outputs: [questions]

  researcher_1:
    agent: "llm://anthropic/claude-sonnet-4-20250514"
    inputs: { question: "${planner.questions}" }
    outputs: [findings]
    depends_on: [planner]

  researcher_2:
    agent: "a2a://localhost:8001"
    inputs: { question: "${planner.questions}" }
    outputs: [findings]
    depends_on: [planner]

  reviewer:
    agent: "human://approve"
    inputs:
      draft: "${researcher_1.findings}"
    outputs: [decision]
    depends_on: [researcher_1, researcher_2]

  summarizer:
    agent: "llm://openai/gpt-4"
    inputs:
      research: "${researcher_1.findings}"
    outputs: [summary]
    depends_on: [reviewer]
    when: "${reviewer.decision} == approved"
```

<div align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIEFbcGxhbm5lcl0gLS0-IEJbcmVzZWFyY2hlcl8xXQogICAgQSAtLT4gQ1tyZXNlYXJjaGVyXzJdCiAgICBCIC0tPiBEWyJyZXZpZXdlciAoaHVtYW4gYXBwcm92YWwpIl0KICAgIEMgLS0-IEQKICAgIEQgLS0-fGFwcHJvdmVkfCBFW3N1bW1hcml6ZXJd?type=png&bgColor=white" alt="Workflow DAG" width="300">
</div>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Architecture

<div align="center">
  <img src="https://mermaid.ink/img/YmxvY2stYmV0YQogICAgY29sdW1ucyAzCiAgICBDTElbIkNMSQpydW4gwrcgZGVidWcgwrcgdHJhY2UgwrcgcmVwbGF5IMK3IGRpZmYgwrcgZGV2Il06MwogICAgUnVudGltZVsiUnVudGltZQpPcmNoZXN0cmF0b3IgKyBEaXNwYXRjaGVyIl06MwogICAgQWRhcHRlcnNbIkFkYXB0ZXJzCmxvY2FsOi8vIMK3IGxsbTovLyDCtyBhMmE6Ly8gwrcgaHVtYW46Ly8iXSBHcmFwaFsiR3JhcGgKREFHIMK3IHRvcG8tc29ydCDCtyBjeWNsZSBkZXRlY3QiXSBTcGVjWyJXb3JrZmxvdyBTcGVjCllBTUwgbG9hZGVyIMK3IHZhbGlkYXRpb24iXQogICAgU3RvcmVzWyJTdG9yZXMKU1FMaXRlIGV4ZWN1dGlvbnMgKyBGUyBhcnRpZmFjdHMiXTozCiAgICBNb2RlbHNbIk1vZGVscwpXb3JrZmxvdyDCtyBOb2RlIMK3IEFydGlmYWN0IMK3IEV4ZWN1dGlvbiJdOjM=?type=png&bgColor=white" alt="Architecture" width="600">
</div>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Features

### Agent Adapters

| Prefix | Adapter | Description |
|--------|---------|-------------|
| `local://` | LocalPythonAdapter | In-process Python callable |
| `llm://` | LLMAdapter | LLM completion via LiteLLM (40+ providers) |
| `a2a://` | A2AAgentAdapter | Remote agent via A2A protocol |
| `human://input` | HumanInputAdapter | Terminal prompt for free-text input |
| `human://approve` | HumanApprovalAdapter | Approval gate with conditional branching |
| `langchain://` | LangChainAdapter | LangChain Runnable via plugin (requires `binex[langchain]`) |
| `crewai://` | CrewAIAdapter | CrewAI Crew via plugin (requires `binex[crewai]`) |
| `autogen://` | AutoGenAdapter | AutoGen Team via plugin (requires `binex[autogen]`) |

### CLI Commands

| Command | Description |
|---------|-------------|
| `binex run <workflow.yaml>` | Execute a workflow |
| `binex debug <run-id\|latest>` | Post-mortem inspection (`--json`, `--errors`, `--node`, `--rich`) |
| `binex trace <run-id>` | Execution timeline, node details, or DAG graph |
| `binex replay <run-id>` | Re-run with optional agent swaps |
| `binex diff <run1> <run2>` | Compare two runs side-by-side |
| `binex artifacts list <run-id>` | List artifacts with lineage tracking |
| `binex validate <workflow.yaml>` | Validate YAML before execution |
| `binex scaffold workflow "A -> B"` | Generate workflow from DSL shorthand |
| `binex init` | Interactive project setup |
| `binex dev up` | Start Docker dev stack |
| `binex doctor` | Check system health |
| `binex cost show <run-id>` | Cost breakdown per node (`--json`) |
| `binex cost history <run-id>` | Chronological cost events (`--json`) |
| `binex explore` | Interactive browser for runs and artifacts |
| `binex plugins list` | Show built-in adapters and installed plugins (`--json`) |
| `binex plugins check <workflow>` | Validate all agent URIs are resolvable |
| `binex hello` | Zero-config demo |

### LLM Providers

Out-of-the-box support for 9 providers via LiteLLM:

**OpenAI** &middot; **Anthropic** &middot; **Google Gemini** &middot; **Ollama** &middot; **OpenRouter** &middot; **Groq** &middot; **Mistral** &middot; **DeepSeek** &middot; **Together AI**

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Examples

Example workflows are available in the [`examples/`](examples/) directory:

| Example | What it demonstrates |
|---------|---------------------|
| `simple.yaml` | Minimal two-node pipeline |
| `diamond.yaml` | Diamond dependency pattern |
| `fan-out-fan-in.yaml` | Parallel execution with aggregation |
| `human-in-the-loop.yaml` | Approval gates and conditional branching |
| `multi-provider-demo.yaml` | Multiple LLM providers in one workflow |
| `a2a-multi-agent.yaml` | Remote agents via A2A protocol |
| `langchain-summarizer.yaml` | LangChain Runnable in a pipeline |
| `crewai-research-crew.yaml` | CrewAI Crew as a workflow node |
| `autogen-coding-team.yaml` | AutoGen Team for code generation |
| `mixed-framework-pipeline.yaml` | LLM + LangChain + CrewAI + AutoGen combined |
| `conditional-routing.yaml` | Branch based on node output |
| `map-reduce.yaml` | MapReduce-style aggregation |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Documentation

Full documentation is available at **[alexli18.github.io/binex](https://alexli18.github.io/binex/)**:

- [Quickstart](https://alexli18.github.io/binex/quickstart/) &mdash; install and run your first workflow
- [Concepts](https://alexli18.github.io/binex/concepts/agents/) &mdash; agents, workflows, artifacts, execution model
- [CLI Reference](https://alexli18.github.io/binex/cli/run/) &mdash; every command with options and examples
- [Architecture](https://alexli18.github.io/binex/architecture/overview/) &mdash; runtime internals and design decisions
- [Workflow Format](https://alexli18.github.io/binex/workflows/format/) &mdash; complete YAML schema reference

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Project Structure

```
src/binex/
├── adapters/        # Agent backends (local, LLM, A2A, human, LangChain, CrewAI, AutoGen)
├── agents/          # Built-in agent implementations
├── cli/             # Click CLI commands
├── graph/           # DAG construction + topological scheduling
├── models/          # Pydantic v2 domain models
├── registry/        # FastAPI agent registry service
├── runtime/         # Orchestrator, dispatcher, lifecycle
├── plugins/         # Plugin registry for custom adapter discovery
├── stores/          # SQLite execution + filesystem artifact persistence
├── trace/           # Debug reports, lineage, timeline, diffing
├── workflow_spec/   # YAML loader + validator + variable resolution
└── tools.py         # Tool calling support (@tool decorator)
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) for upcoming features.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Contributing

Contributions are welcome! See [`CONTRIBUTING.md`](CONTRIBUTING.md) for development setup and guidelines.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

<div align="center">
  <sub>Built with focus on debuggability, because AI agents shouldn't be black boxes.</sub>
</div>
