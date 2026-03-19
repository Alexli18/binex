# CAO Adapter

Integrate [CLI Agent Orchestrator (CAO)](https://github.com/awslabs/cli-agent-orchestrator) by AWS Labs as a first-class Binex adapter. CAO manages multi-agent systems through terminal sessions (tmux). Binex wraps CAO execution with full observability: trace, debug, run diff, replay, and cost/time tracking.

**v1 scope**: Handoff pattern only (synchronous execution). Assign and Send Message patterns are deferred.

## Quick Start

### Prerequisites

1. Install and start the CAO server:
   ```bash
   pip install cli-agent-orchestrator
   cao-server start  # starts on http://localhost:9889
   ```

2. Install at least one agent profile in your agent store:
   ```bash
   # profiles are .md files in ~/.aws/cli-agent-orchestrator/agent-store/
   ls ~/.aws/cli-agent-orchestrator/agent-store/
   ```

### Minimal Workflow

```yaml
name: cao-demo
nodes:
  review:
    agent: "cao://code_supervisor"
    outputs: [result]
```

Run it:

```bash
binex run cao-demo.yaml
```

## YAML Configuration

### Minimal (all defaults)

```yaml
nodes:
  my_node:
    agent: "cao://profile_name"
    outputs: [result]
```

### Full Configuration

```yaml
nodes:
  my_node:
    agent: "cao://profile_name"
    cao:
      mode: handoff               # handoff (default) | assign (v2) | send_message (v3)
      provider: claude_code       # optional — CLI provider hint
      output_format: json         # auto (default) | json | text
      output_field: "$.result"    # JSONPath — only valid with output_format: json
      timeout_minutes: 60         # integer >= 1, default 60
    outputs: [result]
    depends_on: [previous_node]
```

### Multi-Node Workflow with CAO

```yaml
name: research-pipeline
nodes:
  gather:
    agent: "cao://research_agent"
    cao:
      output_format: json
      output_field: "$.findings"
      timeout_minutes: 30
    outputs: [findings]

  review:
    agent: "cao://code_supervisor"
    depends_on: [gather]
    outputs: [review_result]
```

## Configuration Reference

### `CaoConfig` Fields

CaoConfig is a nested block under `cao:` on a node (similar to `LoopSpec` on `loop:`):

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | `handoff` / `assign` / `send_message` | `handoff` | CAO orchestration pattern. v1 supports `handoff` only; `assign` and `send_message` raise a `ValueError` at load time. |
| `provider` | string or null | `null` | CLI provider hint passed to the CAO server. When omitted, defaults to `claude_code` at runtime. See [Providers](#providers) below. |
| `output_format` | `auto` / `json` / `text` | `auto` | How to parse agent stdout. `auto` tries JSON first, falls back to text. `json` requires valid JSON (fails otherwise). `text` returns raw stdout. |
| `output_field` | string or null | `null` | JSONPath expression (must start with `$.`) to extract a specific field from JSON output. Only valid when `output_format` is `json`. |
| `timeout_minutes` | integer | `60` | Maximum execution time in minutes before `CAOTimeoutError`. Must be >= 1. |
| `max_human_prompts` | integer | `3` | Maximum number of human-in-the-loop prompts per node execution. Prevents infinite prompt loops when agent repeatedly asks for input. |

### Validation Rules

- `output_field` requires `output_format: json` — raises `ValueError` at load time
- `output_field` must start with `$.` — raises `ValueError` at load time
- `timeout_minutes` must be >= 1 — raises `ValueError` at load time
- `cao_mode: assign` or `send_message` — raises `ValueError` ("not supported in v1")

## Providers

CAO supports 3 CLI providers:

| Provider | Value | Description |
|---|---|---|
| Claude Code | `claude_code` | Anthropic's CLI agent |
| Kiro CLI | `kiro_cli` | AWS Kiro CLI |
| Q CLI | `q_cli` | Amazon Q Developer CLI |

When `provider` is omitted, the CAO server uses whatever provider is configured in the agent profile.

## Output Formats

### `auto` (default)

The adapter attempts to parse stdout as JSON. If successful, the artifact type is `json` and the content is the parsed dict. If parsing fails, the content is stored as a raw text string.

### `json` (strict)

Requires valid JSON output. If parsing fails, raises `CAOOutputParseError`. When combined with `output_field`, uses JSONPath to extract a specific value.

### `text` (raw)

Returns the raw stdout string without any parsing attempt.

## Artifacts

Each CAO execution produces two artifacts:

| Artifact | Type | Description |
|---|---|---|
| `{node_id}_cao_raw` | `cao_raw_output` | Complete raw terminal stdout (for debugging) |
| `{node_id}_cao_output` | `cao_output` or `json` | Parsed output passed to downstream nodes |

Only `cao_output` is forwarded to dependent nodes. Both are visible in the debug view.

## Error Types

| Error | Cause | Debug View Shows |
|---|---|---|
| `CAOServerUnavailableError` | CAO server not reachable | Server URL + instructions to start it |
| `CAOProfileNotFoundError` | Agent profile `.md` not found in agent store | Profile name + install command |
| `CAOTimeoutError` | Execution exceeded `timeout_minutes` | Elapsed time, timeout threshold, raw output captured so far |
| `CAOAgentError` | CAO terminal reported `error` status | Raw terminal output |
| `CAOOutputParseError` | Failed to parse output as JSON (when `output_format: json`) | Raw output + parse error message |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BINEX_CAO_SERVER_URL` | `http://localhost:9889` | Base URL of the CAO REST server |
| `BINEX_CAO_AGENT_STORE` | `~/.aws/cli-agent-orchestrator/agent-store` | Directory containing agent profile `.md` files |

## Session Naming

Each workflow run gets a single CAO session named `binex-{run_id}`. The CAO server prefixes this with `cao-`, so the actual tmux session name is `cao-binex-{run_id}`.

- One session per workflow run
- Multiple terminals within that session (one per CAO node)
- Session name is deterministic from `run_id` for crash recovery

## Shared Sessions

When a workflow has multiple CAO nodes, they share a single session:

- The first CAO node to execute creates the session via `POST /sessions`
- Subsequent CAO nodes in the same run add terminals to the existing session
- Coordination is handled by `CAOAdapter._run_sessions: ClassVar[dict]` — a class-level dict mapping `run_id` to `session_name`

```yaml
nodes:
  gather:
    agent: "cao://research_agent"    # creates session binex-{run_id}
    outputs: [findings]

  review:
    agent: "cao://code_supervisor"   # reuses same session
    depends_on: [gather]
    outputs: [review_result]
```

## Human-in-the-Loop

When a CAO agent reaches `waiting_user_answer` status, Binex prompts the user for input:

- **CLI**: falls back to `click.prompt()` for interactive input
- **Web UI**: emits a `cao:waiting_input` SSE event, which opens `CaoInputModal` in the browser
- **Limit**: `max_human_prompts` (default 3) per node execution — prevents infinite prompt loops
- **API**: `POST /api/v1/cao/terminals/{id}/input` forwards the user's response to the CAO terminal

After receiving input, the adapter resumes polling until the agent completes or asks again (up to the limit).

## Cleanup Lifecycle

Terminal and session cleanup follows a predictable pattern:

- **Happy path**: `POST /terminals/{id}/exit` — gracefully exits the terminal
- **Error path**: `POST /terminals/{id}/exit` + `DELETE /terminals/{id}` — exit then force-delete
- **Workflow end**: `close()` exits any remaining terminals, then `DELETE /sessions/cao-{name}` removes the session entirely and cleans `_run_sessions`

## Session Registry

Binex tracks active CAO terminal sessions in a `cao_sessions` SQLite table. This enables:

- **Crash recovery**: If Binex exits unexpectedly, orphaned sessions are detected on next startup and shown as a dashboard banner with "Clean up" action.
- **Graceful shutdown**: On Ctrl+C, all active CAO terminals are terminated automatically.

## Cost Tracking

CAO providers are subscription-based — per-token cost is not available. Cost views show `$0.000 (subscription-based)` with elapsed time as the primary resource indicator.

## Known Limitations

- **Output capped at 200 lines**: CAO uses tmux with `TMUX_HISTORY_LINES=200`. Very long agent outputs may be truncated in `cao_raw_output`.
- **Handoff only (v1)**: `assign` and `send_message` patterns are not implemented.
- **No authentication**: CAO server access is unauthenticated in v1.
- **No nested CAO**: A CAO node cannot invoke another CAO node.
- **Local server only**: Binex does not start or manage the `cao-server` process.
