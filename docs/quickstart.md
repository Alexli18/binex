# Quickstart

Install Binex and run your first workflow in under 5 minutes.

## Install

```bash
pip install -e .
```

## Create a Workflow

```yaml
# my-workflow.yaml
name: hello-pipeline
description: "A simple 2-node pipeline"

nodes:
  producer:
    agent: "local://echo"
    system_prompt: produce
    inputs:
      data: "${user.input}"
    outputs: [result]

  consumer:
    agent: "local://echo"
    system_prompt: consume
    inputs:
      data: "${producer.result}"
    outputs: [final]
    depends_on: [producer]
```

## Run

```bash
binex run my-workflow.yaml --var input="hello world"
```

## Debug

Inspect any run with a full post-mortem report:

```bash
binex debug <run-id>
```

```
=== Debug: <run-id> ===
Workflow: hello-pipeline
Status:   completed (2/2 completed)
Duration: 0.003s

-- producer [completed] ------
  Agent:  local://echo
  Output: art_producer (result)

-- consumer [completed] ------
  Agent:  local://echo
  Input:  art_producer <- producer
  Output: art_consumer (result)
```

Use `--json` for machine-readable output, `--errors` to show only failures, `--node <id>` to focus on one node, or `--rich` for colored output (`pip install binex[rich]`).

## Trace

```bash
binex trace <run-id>
```

```
Run: <run-id>
Status: completed

Timeline:
  producer  ██████████  completed  1.2s
  consumer  ██████████  completed  0.8s
```

## Next Steps

- [CLI Reference](cli/run.md) — all commands and options
- [Concepts](concepts/workflows.md) — how workflows work
- [Workflow Format](workflows/format.md) — YAML schema reference
