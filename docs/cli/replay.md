# binex replay

## Synopsis

```
binex replay RUN_ID --from STEP --workflow FILE [OPTIONS]
```

## Description

Replay a previous run starting from a specific step. Artifacts produced **before** `--from` are reused from the original run; nodes from that step onward are re-executed. This lets you:

- Re-run a failed step after fixing configuration
- Swap agents to test different LLM providers or models
- A/B test prompts without re-running expensive upstream nodes

The replayed run is stored as a new run with its own `run_id`, linked to the original via `forked_from` metadata.

Supported agent prefixes: `local://`, `llm://`, `a2a://`, `human://input`, `human://approve`.

Exits `0` on success, `1` on failure.

## Options

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | Original run ID to fork from |
| `--from` | `string` (required) | Step/node ID to re-execute from. All nodes from this step onward are replayed. |
| `--workflow` | `Path` (required, must exist) | Workflow YAML file |
| `--agent` | `node=agent` (repeatable) | Swap the agent for a specific node. Can be specified multiple times. |
| `--json-output` / `--json` | flag | Output as JSON |

## Basic Example

```bash
# Replay from the summarize step using the same agents
binex replay run_a1b2c3d4 \
  --from summarize \
  --workflow workflows/report.yaml
```

**Output:**

```
Replay Run ID: run_e5f6a7b8-9c0d-4e1f-a2b3-c4d5e6f7a8b9
Forked from: run_a1b2c3d4 at step 'summarize'
Workflow: report-pipeline
Status: completed
Nodes: 4/4 completed
```

## Agent Swaps

The `--agent` option lets you replace the agent for one or more nodes. The format is `node_id=agent_uri`. You can specify it multiple times:

```bash
# Swap one node to use a different model
binex replay run_a1b2c3d4 \
  --from summarize \
  --workflow workflows/report.yaml \
  --agent summarize=llm://anthropic/claude-sonnet-4-20250514

# Swap multiple nodes
binex replay run_a1b2c3d4 \
  --from transform \
  --workflow workflows/report.yaml \
  --agent transform=llm://openai/gpt-4o \
  --agent summarize=llm://anthropic/claude-sonnet-4-20250514
```

### Supported Agent Prefixes

| Prefix | Description | Example |
|---|---|---|
| `local://` | Local Python handler | `local://echo` |
| `llm://` | LLM via litellm | `llm://openai/gpt-4o`, `llm://anthropic/claude-sonnet-4-20250514`, `llm://ollama/llama3` |
| `a2a://` | Remote A2A agent | `a2a://http://localhost:8001` |
| `human://input` | Human text input | `human://input` |
| `human://approve` | Human approval gate | `human://approve` |

### Common Agent Swap Scenarios

**OpenAI to Anthropic:**

```bash
binex replay run_a1b2c3d4 \
  --from generate \
  --workflow workflows/pipeline.yaml \
  --agent generate=llm://anthropic/claude-sonnet-4-20250514
```

**Cloud to local model (for debugging):**

```bash
binex replay run_a1b2c3d4 \
  --from generate \
  --workflow workflows/pipeline.yaml \
  --agent generate=llm://ollama/llama3
```

**LLM to local handler (for mocking):**

```bash
binex replay run_a1b2c3d4 \
  --from generate \
  --workflow workflows/pipeline.yaml \
  --agent generate=local://mock
```

## JSON Output

```bash
$ binex replay run_a1b2c3d4 \
    --from summarize \
    --workflow workflows/report.yaml \
    --json
```

```json
{
  "run_id": "run_e5f6a7b8-9c0d-4e1f-a2b3-c4d5e6f7a8b9",
  "workflow_name": "report-pipeline",
  "status": "completed",
  "total_nodes": 4,
  "completed_nodes": 4,
  "failed_nodes": 0,
  "forked_from": "run_a1b2c3d4",
  "forked_at_step": "summarize",
  "started_at": "2026-03-09T14:32:10.123456",
  "finished_at": "2026-03-09T14:32:18.654321"
}
```

## Error Handling

**Invalid run ID:**

```
$ binex replay run_nonexistent --from summarize --workflow workflows/report.yaml
Error: Run 'run_nonexistent' not found
```

**Invalid `--agent` format (missing `=`):**

```
$ binex replay run_a1b2c3d4 --from summarize --workflow workflows/report.yaml \
    --agent "summarize llm://openai/gpt-4o"
Error: Invalid agent swap format: summarize llm://openai/gpt-4o (expected node=agent)
```

**Replay fails at a step:**

```
Replay Run ID: run_f1e2d3c4-5a6b-7c8d-9e0f-a1b2c3d4e5f6
Forked from: run_a1b2c3d4 at step 'summarize'
Workflow: report-pipeline
Status: failed
Nodes: 3/4 completed
Failed: 1
```

The exit code is `1` when the replay fails. Use `binex debug <replay_run_id>` to investigate.

## Use Cases

### A/B Testing Different Models

Compare how GPT-4o and Claude Sonnet perform on the same task, reusing upstream results:

```bash
# Original run used GPT-4o
ORIGINAL=run_a1b2c3d4

# Replay with Claude Sonnet
binex replay $ORIGINAL \
  --from summarize \
  --workflow workflows/report.yaml \
  --agent summarize=llm://anthropic/claude-sonnet-4-20250514
# Replay Run ID: run_e5f6a7b8

# Replay with Llama 3 (local)
binex replay $ORIGINAL \
  --from summarize \
  --workflow workflows/report.yaml \
  --agent summarize=llm://ollama/llama3
# Replay Run ID: run_c9d8e7f6

# Compare all three
binex diff $ORIGINAL run_e5f6a7b8       # GPT-4o vs Claude Sonnet
binex diff $ORIGINAL run_c9d8e7f6       # GPT-4o vs Llama 3
binex diff run_e5f6a7b8 run_c9d8e7f6    # Claude Sonnet vs Llama 3
```

### Replay Then Diff (Full Workflow)

The most common pattern: replay a run with changes, then diff to see what was affected.

```bash
# Step 1: Replay with a fix
binex replay run_a1b2c3d4 \
  --from transform \
  --workflow workflows/pipeline.yaml \
  --agent transform=llm://openai/gpt-4o

# Step 2: Diff the original and the replay
binex diff run_a1b2c3d4 run_e5f6a7b8

# Step 3: Inspect a specific node's artifacts
binex artifacts show art_transform
```

### Debugging a Failed Step

When a run fails mid-pipeline, replay from the failed step to iterate quickly:

```bash
# Run failed at 'validate' step
binex debug run_a1b2c3d4 --node validate --errors
# Shows: Error: schema validation failed — missing 'title' field

# Fix the upstream prompt and replay from 'generate'
binex replay run_a1b2c3d4 \
  --from generate \
  --workflow workflows/pipeline.yaml

# Check if validation passes now
binex debug run_e5f6a7b8 --node validate
```

## Tips

- The `--from` step and all its downstream dependents are re-executed. Upstream nodes keep their original artifacts.
- Per-node `config` (temperature, max_tokens, api_base, api_key) from the workflow YAML is forwarded to the swapped agent. If you need different config, edit the workflow file before replaying.
- The replayed run gets a fresh `run_id` and full execution records, so you can use `binex debug`, `binex artifacts`, and `binex trace` on it.
- Agent swap format is strict: use `=` with no spaces around it (e.g., `--agent summarize=llm://openai/gpt-4o`).

## See Also

- [binex run](run.md) -- execute a fresh workflow
- [binex diff](diff.md) -- compare original and replayed runs
- [binex debug](debug.md) -- post-mortem inspection of a run
- [binex trace](trace.md) -- inspect the replayed run
- [binex artifacts](artifacts.md) -- inspect individual artifacts
