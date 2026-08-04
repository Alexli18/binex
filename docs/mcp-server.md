# MCP Server

Binex ships a built-in **Model Context Protocol (MCP) server** that exposes 10 tools over stdio. Once registered in your AI client, Claude (or any MCP-capable host) can list workflows, trigger runs, inspect failures, replay nodes, and run eval suites — all without leaving the chat.

## Overview

The server is started by `binex mcp serve` and communicates over stdin/stdout using the MCP JSON-RPC framing. It reuses the same SQLite store and artifact filesystem as the CLI and web UI, so every run the server creates is immediately visible in `binex ui`.

All tool responses are JSON-serialisable dicts. Artifact content is **truncated at 4 000 characters** with a pointer to `get_artifact` for the full text (see [Notes](#notes)).

## Quick Start

### Claude Code

```bash
claude mcp add binex -- binex mcp serve
```

This registers `binex` as an MCP server for the current project. Claude Code will start `binex mcp serve` automatically when needed.

### Cursor

Add the following to your Cursor `settings.json` (or `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "binex": {
      "command": "binex",
      "args": ["mcp", "serve"]
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the equivalent path on your platform:

```json
{
  "mcpServers": {
    "binex": {
      "command": "binex",
      "args": ["mcp", "serve"]
    }
  }
}
```

Restart Claude Desktop after editing. The `binex` toolset will appear in the tool picker.

## Tool Catalog

| Tool | Description |
|------|-------------|
| `list_workflows` | List available workflow YAML files in the current directory (same discovery logic as `binex list`) |
| `run_workflow` | Run a workflow non-interactively to completion with optional scripted inputs for `human://` nodes |
| `get_run_status` | Get status and summary of a run — node counts, cost, timestamps |
| `list_runs` | List the most recent runs (default: last 10) |
| `debug_node` | Inspect a specific node's inputs, outputs, prompt, latency, cost, and error (if any) |
| `diagnose_run` | Full diagnostic report for a run — failed nodes, root causes, recommendations |
| `diff_runs` | Compare two runs side-by-side — per-node status, artifact similarity, cost delta |
| `replay_node` | Re-run a single node with optional model and prompt overrides; returns the new run ID and node output |
| `eval_run` | Run an eval suite (`.yaml`) against blessed baselines; returns per-case verdicts |
| `get_artifact` | Fetch the **full, untruncated** content of any artifact by ID |

### Tool Details

#### `list_workflows`

```
Parameters:
  base_dir (optional)  Directory to scan (default: current working directory)
```

Returns `{"workflows": [{"path", "name", "description?"}]}`.

#### `run_workflow`

```
Parameters:
  path            Path to the workflow YAML file (relative or absolute)
  inputs          Optional dict of node_id → string inputs for human:// nodes
```

Returns `{"run_id", "status", "completed_nodes", "failed_nodes", "total_cost"}`.

#### `get_run_status`

```
Parameters:
  run_id          The run ID to look up
```

Returns the full run summary dict including `started_at`, `completed_at`, `source`, and node counts.

#### `list_runs`

```
Parameters:
  limit (optional)  Number of runs to return (default: 10)
```

#### `debug_node`

```
Parameters:
  run_id          Run to inspect
  node_id         Node within that run
```

Returns inputs, outputs (truncated), prompt (truncated), latency, cost, agent ID, and error string.

#### `diagnose_run`

```
Parameters:
  run_id          Run to diagnose
```

Wraps the same engine as `binex diagnose`. Output is truncated per-field at 4 000 characters.

#### `diff_runs`

```
Parameters:
  run_id_a        First (baseline) run
  run_id_b        Second (comparison) run
```

Returns a `DiffReport`-shaped dict with per-node comparison entries.

#### `replay_node`

```
Parameters:
  run_id          Original run
  node_id         Node to replay
  model           Optional LLM model override (e.g. "openai/gpt-4o-mini")
  prompt          Optional system_prompt override for this node
```

Returns `{"new_run_id", "status", "node_output"}`.

!!! note
    Replay is disabled for runs imported from external traces (`source="otel-import"`). The tool returns `{"error": "...", "code": "unsupported"}` in that case.

#### `eval_run`

```
Parameters:
  suite_path      Path to the eval suite YAML file
```

Returns the full `EvalResult` dict including per-case verdicts, assert results, and threshold comparisons.

#### `get_artifact`

```
Parameters:
  artifact_id     The artifact ID to fetch (visible in debug_node output)
```

Returns `{"id", "run_id", "type", "content", "lineage"}`. Content is **not truncated** — use this tool when other tools show a truncation notice.

## Notes

- **Response truncation**: all tools except `get_artifact` truncate artifact content at 4 000 characters. Truncated values include a suffix of the form `... [truncated N chars — use get_artifact('<id>') for full content]`.
- **Error shape**: on failure, tools return `{"error": "<human message>", "code": "<error_code>"}` where `code` is one of: `not_found`, `invalid_input`, `unsupported`, `execution_error`.
- **Store isolation**: the server reads and writes the same `.binex/` directory as the CLI. Run the server from your project root so it finds the correct stores.
- **Logging**: all server-side logs go to stderr and do not interfere with the JSON-RPC framing on stdout.
