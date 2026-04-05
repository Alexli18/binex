# Workflow Cookbook

Browse all bundled example workflows by use case. Each entry includes a short description and the command to run it.

---

## Getting Started

The simplest workflows to learn Binex basics — no API keys required for the local/Ollama variants.

| Workflow | File | Description |
|----------|------|-------------|
| Hello World | [`hello-world.yaml`](https://github.com/Alexli18/binex/blob/master/examples/hello-world.yaml) | Minimal single-node workflow; same as `binex hello` |
| Simple Pipeline | [`simple.yaml`](https://github.com/Alexli18/binex/blob/master/examples/simple.yaml) | 2-node linear pipeline (producer → consumer) |
| Ollama Hello | [`ollama-hello.yaml`](https://github.com/Alexli18/binex/blob/master/examples/ollama-hello.yaml) | Minimal 2-node LLM workflow using a local Ollama model — no API keys needed |
| File Prompt | [`file-prompt.yaml`](https://github.com/Alexli18/binex/blob/master/examples/file-prompt.yaml) | Load `system_prompt` from external files via `file://` prefix |

```bash
binex run examples/hello-world.yaml
binex run examples/simple.yaml --var input="hello world"
binex run examples/ollama-hello.yaml --var input="hi"
```

---

## Research & Analysis

Multi-agent research pipelines for gathering, synthesising, and summarising information.

| Workflow | File | Description |
|----------|------|-------------|
| Research | [`research.yaml`](https://github.com/Alexli18/binex/blob/master/examples/research.yaml) | Multi-agent fan-out-fan-in research pipeline |
| Ollama Research | [`ollama-research.yaml`](https://github.com/Alexli18/binex/blob/master/examples/ollama-research.yaml) | Research + translate pipeline mixing Ollama and OpenRouter |
| Gemini Research | [`gemini-research.yaml`](https://github.com/Alexli18/binex/blob/master/examples/gemini-research.yaml) | Research pipeline powered by Gemini 2.5 Flash |
| Research with MCP | [`research-with-mcp.yaml`](https://github.com/Alexli18/binex/blob/master/examples/research-with-mcp.yaml) | Research agent with filesystem access via MCP server |
| Scheduled Report | [`scheduled-report.yaml`](https://github.com/Alexli18/binex/blob/master/examples/scheduled-report.yaml) | Cron-triggered research report using the `schedule` field |

```bash
binex run examples/research.yaml --var topic="quantum computing"
binex run examples/gemini-research.yaml --var topic="rust programming"
```

---

## Human-in-the-Loop

Workflows that pause execution and wait for a human to review, approve, or provide feedback before continuing.

| Workflow | File | Description |
|----------|------|-------------|
| Human-in-the-Loop | [`human-in-the-loop.yaml`](https://github.com/Alexli18/binex/blob/master/examples/human-in-the-loop.yaml) | Pizza order workflow with human approval gate |
| Human Feedback | [`human-feedback.yaml`](https://github.com/Alexli18/binex/blob/master/examples/human-feedback.yaml) | Generate → human review → revise → output loop |
| Draft → Review → Approve | [`draft-review-approve.yaml`](https://github.com/Alexli18/binex/blob/master/examples/draft-review-approve.yaml) | Content chain with human approval at the final stage |

```bash
binex run examples/human-in-the-loop.yaml
binex run examples/human-feedback.yaml --var topic="blog post about AI"
```

---

## Cost & Budget

Workflows demonstrating Binex's cost-tracking and budget enforcement features.

| Workflow | File | Description |
|----------|------|-------------|
| Budget Hard Limit | [`budget-hard-limit.yaml`](https://github.com/Alexli18/binex/blob/master/examples/budget-hard-limit.yaml) | Stop execution when accumulated cost exceeds `max_cost` |
| Budget Per-Node | [`budget-per-node.yaml`](https://github.com/Alexli18/binex/blob/master/examples/budget-per-node.yaml) | Each node has its own budget cap with configurable policy |
| Budget Warn/Monitor | [`budget-warn-monitor.yaml`](https://github.com/Alexli18/binex/blob/master/examples/budget-warn-monitor.yaml) | Log a warning when cost exceeds threshold but keep running |

```bash
binex run examples/budget-hard-limit.yaml --var input="summarise this doc"
binex cost show <run-id>
```

---

## Multi-Provider

Workflows that mix multiple LLM providers in a single pipeline, routed via litellm.

| Workflow | File | Description |
|----------|------|-------------|
| Multi-Provider Demo | [`multi-provider-demo.yaml`](https://github.com/Alexli18/binex/blob/master/examples/multi-provider-demo.yaml) | Ollama plans & summarises, Gemini researches |
| Multi-Provider Research | [`multi-provider-research.yaml`](https://github.com/Alexli18/binex/blob/master/examples/multi-provider-research.yaml) | Research pipeline mixing Ollama, Gemini, and OpenRouter per node |

```bash
binex run examples/multi-provider-demo.yaml --var topic="climate change"
```

---

## Framework Integration

Workflows that use third-party agent frameworks (LangChain, CrewAI, AutoGen) as Binex nodes via built-in adapters.

| Workflow | File | Description |
|----------|------|-------------|
| LangChain Summarizer | [`langchain-summarizer.yaml`](https://github.com/Alexli18/binex/blob/master/examples/langchain-summarizer.yaml) | LangChain Runnable called as a Binex node via `langchain://` adapter |
| CrewAI Research Crew | [`crewai-research-crew.yaml`](https://github.com/Alexli18/binex/blob/master/examples/crewai-research-crew.yaml) | CrewAI Crew object kicked off as a workflow node |
| AutoGen Coding Team | [`autogen-coding-team.yaml`](https://github.com/Alexli18/binex/blob/master/examples/autogen-coding-team.yaml) | AutoGen Team/AgentChat run as a Binex node |
| Mixed Framework Pipeline | [`mixed-framework-pipeline.yaml`](https://github.com/Alexli18/binex/blob/master/examples/mixed-framework-pipeline.yaml) | LLM, LangChain, CrewAI, and AutoGen nodes in a single workflow |
| A2A Multi-Agent | [`a2a-multi-agent.yaml`](https://github.com/Alexli18/binex/blob/master/examples/a2a-multi-agent.yaml) | Remote A2A (Agent-to-Agent) protocol agents as workflow nodes |

```bash
binex run examples/mixed-framework-pipeline.yaml --var input="analyse this dataset"
```

---

## CLI Agent (CAO) Workflows

Workflows using the CAO adapter to call CLI-native agents (Claude Code, Kiro, Q CLI) that can read/write the filesystem, run commands, and interact with local tools.

| Workflow | File | Description |
|----------|------|-------------|
| CAO Hello | [`cao-hello.yaml`](https://github.com/Alexli18/binex/blob/master/examples/cao-hello.yaml) | Single CAO node that scans and summarises your project structure |
| CAO Pipeline | [`cao-pipeline.yaml`](https://github.com/Alexli18/binex/blob/master/examples/cao-pipeline.yaml) | First agent writes Python, second agent runs and tests it |
| CAO Code Review | [`cao-code-review.yaml`](https://github.com/Alexli18/binex/blob/master/examples/cao-code-review.yaml) | Write → review → human approval → fix pipeline |
| CAO Multi-Provider | [`cao-multi-provider.yaml`](https://github.com/Alexli18/binex/blob/master/examples/cao-multi-provider.yaml) | Claude Code, Kiro, and Q CLI working together in one workflow |
| CAO Parallel Workers | [`cao-parallel-workers.yaml`](https://github.com/Alexli18/binex/blob/master/examples/cao-parallel-workers.yaml) | Supervisor fans out to three parallel CAO workers, LLM reduces results |
| CAO Repo Health | [`cao-repo-health.yaml`](https://github.com/Alexli18/binex/blob/master/examples/cao-repo-health.yaml) | Four CLI agents scan a repo in parallel; LLM produces a prioritised report |

```bash
binex run examples/cao-hello.yaml
binex run examples/cao-repo-health.yaml
```

---

## Patterns

Reusable DAG topology examples illustrating common architectural patterns.

| Workflow | File | Description |
|----------|------|-------------|
| Diamond | [`diamond.yaml`](https://github.com/Alexli18/binex/blob/master/examples/diamond.yaml) | A splits into B and C (parallel), which merge at D |
| Fan-Out | [`fan-out.yaml`](https://github.com/Alexli18/binex/blob/master/examples/fan-out.yaml) | One node feeds multiple parallel downstream nodes |
| Fan-In | [`fan-in.yaml`](https://github.com/Alexli18/binex/blob/master/examples/fan-in.yaml) | Multiple independent sources merge into a single aggregator |
| Fan-Out / Fan-In | [`fan-out-fan-in.yaml`](https://github.com/Alexli18/binex/blob/master/examples/fan-out-fan-in.yaml) | Combined scatter-gather pattern |
| Map-Reduce | [`map-reduce.yaml`](https://github.com/Alexli18/binex/blob/master/examples/map-reduce.yaml) | Splitter fans work to parallel workers; reducer merges results |
| Conditional Routing | [`conditional-routing.yaml`](https://github.com/Alexli18/binex/blob/master/examples/conditional-routing.yaml) | Route to different handlers based on `when` conditions |
| Chain with Review | [`chain-with-review.yaml`](https://github.com/Alexli18/binex/blob/master/examples/chain-with-review.yaml) | Draft → review → revise → finalise linear chain |
| Multi-Stage | [`multi-stage.yaml`](https://github.com/Alexli18/binex/blob/master/examples/multi-stage.yaml) | Three sequential stages each containing a parallel pair of nodes |

```bash
binex run examples/diamond.yaml --var input="process this"
binex run examples/fan-out-fan-in.yaml --var topic="distributed systems"
```

---

## Reliability & Security

Workflows demonstrating error handling, retries, and secure credential management.

| Workflow | File | Description |
|----------|------|-------------|
| Error Handling | [`error-handling.yaml`](https://github.com/Alexli18/binex/blob/master/examples/error-handling.yaml) | Configure `retry_policy` and `deadline_ms` per node |
| Secure Pipeline | [`secure-pipeline.yaml`](https://github.com/Alexli18/binex/blob/master/examples/secure-pipeline.yaml) | Use environment variables for sensitive data (API keys, secrets) |

```bash
binex run examples/error-handling.yaml --var input="test"
```

---

## Just for Fun

| Workflow | File | Description |
|----------|------|-------------|
| D&D Master | [`dnd-master.yaml`](https://github.com/Alexli18/binex/blob/master/examples/dnd-master.yaml) | D&D Dungeon Master with dice rolling and random encounters |

```bash
binex run examples/dnd-master.yaml
```

---

## Quick Reference

| Category | Workflows |
|----------|-----------|
| Getting Started | `hello-world`, `simple`, `ollama-hello`, `file-prompt` |
| Research & Analysis | `research`, `ollama-research`, `gemini-research`, `research-with-mcp`, `scheduled-report` |
| Human-in-the-Loop | `human-in-the-loop`, `human-feedback`, `draft-review-approve` |
| Cost & Budget | `budget-hard-limit`, `budget-per-node`, `budget-warn-monitor` |
| Multi-Provider | `multi-provider-demo`, `multi-provider-research` |
| Framework Integration | `langchain-summarizer`, `crewai-research-crew`, `autogen-coding-team`, `mixed-framework-pipeline`, `a2a-multi-agent` |
| CLI Agent (CAO) | `cao-hello`, `cao-pipeline`, `cao-code-review`, `cao-multi-provider`, `cao-parallel-workers`, `cao-repo-health` |
| Patterns | `diamond`, `fan-out`, `fan-in`, `fan-out-fan-in`, `map-reduce`, `conditional-routing`, `chain-with-review`, `multi-stage` |
| Reliability & Security | `error-handling`, `secure-pipeline` |
| Just for Fun | `dnd-master` |
