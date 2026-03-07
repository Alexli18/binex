# Quickstart: Binex Runtime

## Prerequisites

- Python 3.11+
- Docker (for local dev environment)
- uv (recommended) or pip

## Install

```bash
pip install binex
```

## 1. Start Local Environment

```bash
binex dev
```

This starts Docker Compose with:
- Ollama (local LLM inference)
- LiteLLM proxy
- 4 reference agents (planner, researcher, validator, summarizer)
- Agent registry

## 2. Verify Setup

```bash
binex doctor
```

All components should report healthy.

## 3. Run Example Pipeline

```bash
binex run examples/research.yaml --var query="WiFi CSI sensing"
```

This executes a 5-node research pipeline:
1. Planner decomposes the query into subtasks
2. Two researchers search different sources in parallel
3. Validator deduplicates and validates results
4. Summarizer produces a structured report

## 4. Inspect the Run

```bash
# View execution timeline
binex trace <run-id>

# View DAG visualization
binex trace graph <run-id>

# Inspect a specific step
binex trace node <run-id> validator

# View artifact lineage
binex artifacts lineage <artifact-id>
```

## 5. Replay with Agent Swap

```bash
# Replay from validator step
binex replay <run-id> --from validator

# Swap validator agent and compare
binex replay <run-id> --agent validator=strict_validator

# Compare runs
binex diff <original-run-id> <replay-run-id>
```

## 6. Create Your Own Workflow

```bash
# Scaffold a new agent
binex scaffold agent --name my-agent

# Validate your workflow
binex validate my-workflow.yaml

# Run it
binex run my-workflow.yaml
```

## Project Structure

```
binex/
  src/binex/
    models/       # Domain models (zero internal deps)
    graph/        # DAG engine + scheduler
    runtime/      # Orchestrator, dispatcher, lifecycle, replay
    adapters/     # Agent backends (A2A, local, LLM)
    stores/       # Artifact + execution stores
    trace/        # Execution trace, lineage, diff
    registry/     # Agent registry service
    workflow_spec/# YAML/JSON workflow parsing
    agents/       # Reference agents
    cli/          # CLI commands
```
