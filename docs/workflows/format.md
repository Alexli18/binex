# Workflow YAML Format

Complete schema reference for Binex workflow files.

## Root — `WorkflowSpec`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | `int` | no | Schema version (default: `1`, must be >= 1). See [Versioning](#versioning) below. |
| `name` | `str` | yes | Workflow name |
| `description` | `str` | no | Workflow description (default: `""`) |
| `nodes` | `dict[str, NodeSpec]` | yes | Map of node\_id to node definition |
| `defaults` | `DefaultsSpec` | no | Default settings applied to all nodes |
| `budget` | `BudgetConfig` | no | Budget constraints for the run (see below) |
| `webhook` | `WebhookConfig` | no | Webhook notification target (see below) |
| `schedule` | `str` | no | Cron expression (5-field) for scheduled execution |
| `concurrency` | `int` or `dict[str, int]` | no | Cap on concurrent node execution (see below) |
| `mcp_servers` | `dict[str, McpServerConfig]` | no | MCP server configurations (see below) |

## Node — `NodeSpec`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | no | Auto-set from the dict key |
| `agent` | `str` | yes | Agent URI — `local://`, `llm://`, `a2a://`, `human://`, `langchain://`, `crewai://`, `autogen://`, or custom plugin prefix |
| `system_prompt` | `str` | no | System prompt sent to the agent (supports `file://` prefix) |
| `inputs` | `dict[str, Any]` | no | Input key-value pairs; supports variable interpolation |
| `outputs` | `list[str]` | yes | Artifact names this node produces |
| `depends_on` | `list[str]` | no | Node IDs that must complete before this node runs |
| `config` | `dict[str, Any]` | no | Per-node config forwarded to the adapter (see below) |
| `retry_policy` | `RetryPolicy` | no | Override the default retry settings |
| `deadline_ms` | `int` | no | Hard total-duration timeout for this node |
| `heartbeat_timeout_ms` | `int` | no | Silence timeout for long nodes that report progress (see below) |
| `when` | `str` | no | Conditional execution expression (see below) |
| `cost` | `NodeCostHint` | no | Optional cost estimate for planning (see below) |
| `budget` | `float` or `NodeBudget` | no | Per-node budget limit (shorthand: `budget: 0.50`, full: `budget: { max_cost: 0.50 }`) |
| `tools` | `list[str]` | no | Tool URIs available to this node (see [Tools](#tools) below) |
| `output_schema` | `dict` | no | JSON Schema for validating node output. Failed validation triggers auto-retry |
| `fallbacks` | `list[str]` | no | Fallback models tried when the primary fails on an infrastructure error (see below) |
| `cache` | `bool` | no | Reuse this node's cached result when its inputs are unchanged (see below) |
| `routing` | `dict` | no | Per-node Gateway routing overrides (see below) |

### `config` keys (LLM adapter)

| Key | Example | Effect |
|-----|---------|--------|
| `api_base` | `"http://localhost:11434"` | LiteLLM API base URL |
| `api_key` | `"sk-..."` | Provider API key |
| `temperature` | `0.7` | Sampling temperature |
| `max_tokens` | `4096` | Max tokens in completion |

All `config` values are forwarded to `litellm.acompletion()` when not `None`.

### External System Prompt — `file://`

The `system_prompt` field supports loading content from an external file using the `file://` prefix.
Relative paths are resolved relative to the workflow YAML file's directory. Absolute paths are used as-is.

```yaml
nodes:
  researcher:
    agent: "llm://openai/gpt-4"
    system_prompt: "file://prompts/researcher.md"
    outputs: [findings]
```

If the referenced file does not exist, workflow loading fails with a clear error message.

### Conditional Execution — `when`

The `when` field enables conditional node execution based on upstream artifact values.
A node with a `when` condition is **skipped** (not failed) if the condition evaluates to false.
Skipped nodes count as resolved for downstream dependency purposes.

**Operators:**

| Operator | Example | Meaning |
|----------|---------|---------|
| `==` | `${review.decision} == approved` | Run only if artifact content equals `"approved"` |
| `!=` | `${review.decision} != rejected` | Run only if artifact content does not equal `"rejected"` |

**Example — approval gate with branching:**

```yaml
publish:
  agent: "local://echo"
  inputs:
    final: "${revise.content}"
  outputs: [result]
  depends_on: [human_review]
  when: "${human_review.decision} == approved"

discard:
  agent: "local://echo"
  inputs: {}
  outputs: [notice]
  depends_on: [human_review]
  when: "${human_review.decision} == rejected"
```

The `when` field is commonly used with `human://approve` nodes but works with any artifact value.

## Defaults — `DefaultsSpec`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `deadline_ms` | `int` | `120000` | Default deadline in milliseconds |
| `retry_policy` | `RetryPolicy` | see below | Default retry policy for all nodes |

## Retry — `RetryPolicy`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_retries` | `int` | `1` | Maximum retry attempts |
| `backoff` | `"fixed"` or `"exponential"` | `"exponential"` | Backoff strategy between retries |

## Budget — `BudgetConfig`

Budget constraints limit the total cost of a workflow run. The orchestrator checks accumulated cost after each batch of nodes.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_cost` | `float` | — | Maximum allowed cost in the specified currency (must be > 0) |
| `currency` | `str` | `"USD"` | Currency code |
| `policy` | `"stop"` or `"warn"` | `"warn"` | What to do when budget is exceeded |

### Budget Policies

| Policy | Behavior |
|--------|----------|
| `stop` | Skip all remaining nodes, set run status to `"over_budget"` |
| `warn` | Log a warning to stderr, continue execution |

**Example:**

```yaml
name: budgeted-pipeline
budget:
  max_cost: 5.0
  policy: stop

nodes:
  planner:
    agent: "llm://gpt-4o"
    outputs: [plan]
  researcher:
    agent: "llm://claude-sonnet-4-20250514"
    outputs: [findings]
    depends_on: [planner]
  summarizer:
    agent: "llm://gpt-4o"
    outputs: [summary]
    depends_on: [researcher]
```

If the accumulated cost exceeds $5.00 after the researcher node, the summarizer is skipped and the run status is `"over_budget"`.

See the [Budget & Cost Tracking Guide](../cli/budget-guide.md) for more examples and patterns.

With `--json`, the run output includes budget information:

```json
{
  "status": "over_budget",
  "total_cost": 5.23,
  "budget": 5.0,
  "remaining_budget": -0.23
}
```

## Long-Running Nodes & Progress

An LLM node streams tokens, so it's visibly alive. A `local://` node running
Whisper on a two-hour track is silent for thirty minutes — and the default
`deadline_ms` (120 s) kills it. A node that **reports progress** is alive, so the
timeout can apply to *silence* rather than total duration.

- **`heartbeat_timeout_ms`** — the node fails only if it produces no progress for
  this long. `deadline_ms` still applies as an optional hard total-duration cap.
- A `local://` / `python://` handler opts in by accepting a `report_progress`
  parameter and calling `report_progress(fraction, message)` — e.g.
  `report_progress(0.4, "transcribing 48/120 min")`. Handlers that don't accept
  it are unchanged.
- Subprocess / `a2a://` agents report via the binex-trace SDK: `trace.progress(fraction, message)`.
- Progress surfaces as a `node:progress` runtime event (per-node progress in the
  Web UI) and is captured as a trace event.

```python
# local handler
async def transcribe(task, inputs, report_progress):
    for i, chunk in enumerate(chunks):
        ...
        report_progress(i / len(chunks), f"transcribing {i}/{len(chunks)}")
    return [artifact]
```

```yaml
nodes:
  transcribe:
    agent: "local://whisper"
    outputs: [text]
    heartbeat_timeout_ms: 120000   # fail only after 2 min of silence
    deadline_ms: 7200000           # but never run longer than 2 h
```

## Model Fallback Chains

A 40-minute run shouldn't die because of a single `429` or a provider outage.
`fallbacks` lists models to try, in order, when the primary fails:

```yaml
nodes:
  writer:
    agent: "llm://gpt-4o"
    outputs: [draft]
    fallbacks: ["anthropic/claude-sonnet-4-5", "ollama/llama3.1"]
```

Order: retry the current model per its backoff policy → move to the next model →
its own retries. Fallback fires **only** on infrastructure/availability errors —
rate limit (`429`), `5xx`, timeout, model-not-found, and auth (`401`, with a loud
warning, since the next provider uses a different key). It never fires on a model
that answered but poorly — that's [auto-repair](#auto-repair)'s job.

**Reproducibility** (silent model swaps would break diff/bisect/eval):

- Each execution records both `requested_model` and `actual_model`.
- A `node:cache_hit`-style fallback event is emitted (`gpt-4o → claude: rate_limited`)
  and stored on the artifact's `metadata.fallbacks`.
- `binex run --no-fallback` disables the chain entirely, so a model benchmark
  can't be silently contaminated. Also available via `BINEX_NO_FALLBACK=1`.
- `binex validate` warns if a fallback has a smaller context window than the
  primary, or lacks function-calling while the node declares tools.

Streaming: if a stream dies mid-emission, the node restarts from scratch on the
fallback model (no partial splicing).

## Node Caching

Editing the prompt of node 7 shouldn't force re-running (and re-paying for)
nodes 1–6. With caching on, Binex reuses a node's stored result whenever nothing
that affects its output has changed — like `make` for pipelines.

The cache key is a content hash of the node's agent, resolved prompt, model
parameters, tool set, and the content of its **input artifacts**. Change any of
them and the node re-executes; leave them alone and it's served from cache at
`$0`, in a distinct trace event pointing back to the source run.

Caching is **opt-in**, because reusing a result isn't always safe (a
temperature > 0 model is intentionally nondeterministic; a `local://` script may
have side effects). Two ways to enable it:

```yaml
nodes:
  transcribe:
    agent: "local://whisper"
    outputs: [text]
    cache: true          # always cache this node
```

```bash
binex run pipeline.yaml --cache      # iteration mode: cache every node this run
binex run pipeline.yaml --offline    # run ONLY from cache; a miss fails the node
```

`--offline` (implies `--cache`) is the VCR-style mode: record once, then iterate
on downstream logic for free and without network access. Clear the cache with
[`binex clean cache`](../cli/clean.md).

## Concurrency

By default the orchestrator would dispatch every ready node at once. A wide
fan-out (e.g. a `scatter` pattern with 50 workers) then fires 50 simultaneous
LLM calls and trips provider rate limits. `concurrency` caps how many nodes run
at the same time.

**Global cap (scalar):**

```yaml
name: wide-pipeline
concurrency: 8        # at most 8 nodes in flight at once
nodes:
  ...
```

**Per-provider caps (mapping):** the `default` key is the global cap; every
other key limits a single provider. A node holds a global slot *and* its
provider slot, so a local Ollama (one GPU) and a hosted API can coexist:

```yaml
concurrency:
  default: 8          # global cap (falls back to BINEX_MAX_CONCURRENCY, then 8)
  openai: 5           # at most 5 concurrent openai calls
  ollama: 1           # serialize the local model
```

The provider is derived from the agent URI: `llm://openai/gpt-4o` → `openai`,
`llm://ollama/llama3` → `ollama`, and non-LLM agents fall back to their scheme
(`local://` → `local`, `a2a://` → `a2a`).

**Precedence:** the workflow `concurrency` field overrides the
`BINEX_MAX_CONCURRENCY` environment variable, which overrides the default of
`8`. All limits must be `>= 1`.

## Node Cost Hint — `NodeCostHint`

Optional cost estimate for planning purposes. Does not affect execution — purely informational.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `estimate` | `float` | `0.0` | Estimated cost for this node (must be >= 0) |

```yaml
nodes:
  expensive_node:
    agent: "llm://gpt-4o"
    outputs: [result]
    cost:
      estimate: 2.50
```

## Per-Node Budget — `NodeBudget`

Individual nodes can have their own budget limits. The policy is inherited from the workflow-level `budget.policy` (default: `stop`).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_cost` | `float` | — | Maximum allowed cost for this node (must be > 0) |

**Shorthand:** `budget: 0.50` is equivalent to `budget: { max_cost: 0.50 }`.

When both workflow and node budgets are defined, the effective limit is `min(node_budget, remaining_workflow_budget)`.

**Pre-check before retry:** If a node has a budget and fails, the orchestrator checks remaining budget before each retry attempt. With `policy: stop`, the retry is skipped if budget is exhausted. With `policy: warn`, the user is prompted via `click.confirm()`.

**Post-check after execution:** After each execution, if the node's accumulated cost exceeds its budget, the policy determines behavior: `stop` discards the result and marks the node failed; `warn` keeps the result and logs a warning.

**Example:**

```yaml
name: per-node-budget
budget:
  max_cost: 10.00
  policy: stop

nodes:
  planner:
    agent: "llm://gpt-4o-mini"
    outputs: [plan]
    budget: 0.50           # shorthand

  researcher:
    agent: "llm://gpt-4o"
    outputs: [findings]
    depends_on: [planner]
    budget:
      max_cost: 3.00       # full form

  summarizer:
    agent: "llm://gpt-4o"
    outputs: [summary]
    depends_on: [researcher]
    budget: 2.00
```

If the planner costs $0.60 (exceeding its $0.50 limit), it is marked as failed and dependent nodes do not run.

## Output Schema Validation

Nodes can define a JSON Schema to validate their output. If the output fails validation and the node has retries remaining, Binex automatically retries the node.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `output_schema` | `dict` | `None` | Standard JSON Schema object |

**Example:**

```yaml
nodes:
  extractor:
    agent: "llm://openai/gpt-4o"
    system_prompt: "Extract structured data. Return valid JSON."
    outputs: [result]
    output_schema:
      type: object
      properties:
        title:
          type: string
        score:
          type: number
          minimum: 0
          maximum: 100
      required:
        - title
        - score
    retry_policy:
      max_retries: 2
```

If the LLM returns output that doesn't match the schema (e.g., missing `title` field or `score` out of range), the node is retried automatically. After all retries are exhausted, the node fails with a validation error.

The validator handles both JSON string output (parsed first) and dict output (validated directly).

## Auto-Repair

Blindly re-running a node on invalid output usually makes the model repeat the
same mistake — and you pay twice. When a node has an `output_schema`, Binex
applies a repair ladder, cheapest first:

1. **Deterministic repair (0 tokens, always on).** Most "invalid JSON" is just a
   markdown code fence around the payload, prose before/after it, or a trailing
   comma. Binex strips the fence, extracts the first balanced JSON value, and
   re-parses — before any model call. Applies to every agent type, and the
   cleaned JSON replaces the artifact content so downstream nodes get valid data.
2. **Native structured output.** For `llm://` nodes whose model supports it,
   Binex passes the schema into the completion call (`response_format`), so
   malformed output mostly never happens. Detected per-model; silently skipped
   when unsupported.
3. **Feedback loop (`repair.max_attempts`).** If output is still invalid, Binex
   appends the model's answer plus the validation errors to the conversation and
   re-asks up to `max_attempts` times. `local://` and `a2a://` nodes keep
   fail-fast semantics — there's no model to ask.

```yaml
nodes:
  extract:
    agent: "llm://openai/gpt-4o-mini"
    outputs: [result]
    output_schema: { type: object, required: [title] }
    fallbacks: ["openai/gpt-4o"]
    repair:
      max_attempts: 2      # feedback-loop attempts; deterministic repair is always on
      escalate: true       # on repair exhaustion, retry the ladder on the next fallback model
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `repair.max_attempts` | `int` | `0` | LLM feedback-loop attempts on schema-invalid output |
| `repair.escalate` | `bool` | `false` | On repair exhaustion, promote to the next [fallback](#model-fallback-chains) model and retry the ladder |

Every repair attempt's tokens are counted in the run cost. The produced
artifact records `metadata.repair_attempts` and which ladder step succeeded; on
exhaustion the node fails with the validation errors.

**Escalation (`repair.escalate`).** When the feedback loop is exhausted, that's
a signal the model can't handle the schema — not a transient error. With
`escalate: true` and a [fallback chain](#model-fallback-chains), Binex promotes
to the next model and restarts the repair ladder there (trace event
`escalated: schema_repair_exhausted`, distinct from a transport-error fallback).
This turns repair + fallback into an automatic cost optimizer: route everything
through a cheap model and let the strong model catch only the hard tail.
`--no-fallback` disables escalation too.

## Routing Overrides

When a Gateway is configured (either embedded via `gateway.yaml` or standalone via `--gateway`), individual nodes can override the default routing behavior using the `routing` field:

```yaml
nodes:
  critical_search:
    agent: "a2a://research"
    routing:
      prefer: lowest_latency
      timeout_ms: 10000
      retry_count: 5
      failover: true
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `prefer` | `str` | `"highest_priority"` | Selection strategy (`highest_priority`, `lowest_latency`, `round_robin`) |
| `timeout_ms` | `int` | `null` | Override request timeout for this node |
| `retry_count` | `int` | `null` | Override retry count for this node |
| `failover` | `bool` | `null` | Override failover setting for this node |

Routing overrides only apply when a Gateway is configured. Without a Gateway, the `routing` field is ignored.

## Tools

Nodes can declare tools that are made available to the LLM during execution. Three URI schemes are supported:

| Scheme | Example | Description |
|--------|---------|-------------|
| `builtin://` | `builtin://web_search` | One of 10 built-in tools |
| `mcp://` | `mcp://my-server` | All tools from a configured MCP server |
| `python://` | `python://my_module.my_func` | Custom Python function decorated with `@tool` |

### Built-in tools (10)

| Category | Tools |
|----------|-------|
| **Data** | `calculator`, `json_parse`, `random_choice`, `dice_roll` |
| **Web** | `fetch_url`, `http_request`, `web_search` |
| **Files** | `read_file`, `write_file` |
| **System** | `shell_command` |

**Example:**

```yaml
nodes:
  researcher:
    agent: "llm://openai/gpt-4o"
    system_prompt: "Research the topic using web search"
    tools:
      - "builtin://web_search"
      - "builtin://fetch_url"
      - "builtin://calculator"
    outputs: [findings]
```

## MCP Servers — `McpServerConfig`

MCP (Model Context Protocol) servers provide additional tools to LLM nodes. Configure them at the workflow level, then reference them in node `tools` lists.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | `str` | stdio only | Command to launch the MCP server |
| `args` | `list[str]` | no | Arguments for the command |
| `env` | `dict[str, str]` | no | Environment variables |
| `url` | `str` | HTTP only | URL of a running MCP server |

**Example — stdio transport:**

```yaml
mcp_servers:
  file-search:
    command: npx
    args: ["-y", "@anthropic/mcp-file-search"]
  code-tools:
    command: python
    args: ["-m", "my_mcp_server"]

nodes:
  coder:
    agent: "llm://anthropic/claude-sonnet-4-20250514"
    tools:
      - "mcp://file-search"
      - "mcp://code-tools"
      - "builtin://shell_command"
    outputs: [code]
```

**Example — HTTP transport:**

```yaml
mcp_servers:
  remote-api:
    url: "http://localhost:3000/mcp"
```

## Schedule — Cron Expression

The `schedule` field accepts a standard 5-field cron expression. Workflows with a `schedule` are automatically discovered and executed by `binex scheduler start`.

```yaml
name: hourly-report
schedule: "0 * * * *"
nodes:
  reporter:
    agent: "llm://openai/gpt-4o-mini"
    system_prompt: "Generate hourly status report"
    outputs: [report]
```

## Variable Interpolation

Two variable scopes are available inside `inputs` values:

| Syntax | Resolved | Description |
|--------|----------|-------------|
| `${user.<key>}` | Load time | Substituted from `--var` CLI arguments |
| `${<node_id>.<output>}` | Runtime | References an artifact produced by another node |

**Example:**

```yaml
inputs:
  query: "${user.query}"              # --var query="LLM agents"
  plan: "${planner.execution_plan}"   # artifact from the planner node
```

!!! warning
    Use `${planner.plan}` (node ID + output name), **not** `${node.planner.plan}`. The `node.` prefix is not supported.

## Minimal Valid Workflow

```yaml
name: minimal
nodes:
  only_node:
    agent: "local://echo"
    system_prompt: ping
    inputs:
      msg: "hello"
    outputs: [response]
```

No `defaults`, `description`, `depends_on`, or `config` required.

## Versioning

Workflow files support schema versioning via the `version` field. This enables future schema changes with automatic migration.

```yaml
version: 1
name: my-workflow
nodes:
  step1:
    agent: "local://echo"
    outputs: [result]
```

### Behavior

- **Missing `version` field**: Defaults to version 1 (backward compatible with all existing workflows). A warning is logged.
- **`version: 1`**: Current version — no migration needed.
- **`version > CURRENT_VERSION`**: Raises `UnsupportedVersionError` at load time. Upgrade Binex to use newer workflows.

### Migration framework

When Binex upgrades its schema version, a migration chain transforms older workflow dicts step by step (v1 → v2 → ... → current). Migrations run in-memory at load time — the original YAML file is never modified.

### Workflow snapshots

Every `binex run` stores a normalized, SHA256-deduplicated snapshot of the workflow definition in SQLite. This lets you:

- Inspect the exact workflow used in any past run via `binex debug <run-id>`
- Compare workflows between runs via `binex workflow diff <run1> <run2>`
- Reproduce runs even if the original YAML file has changed

Check the workflow version of any file:

```bash
binex workflow version examples/simple.yaml

## Webhook — `WebhookConfig`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | `str` | yes | Webhook endpoint URL |

Webhook notifications are sent on run completion, failure, or budget exceeded. Can also be set via `BINEX_WEBHOOK_URL` environment variable.

```yaml
name: notified-pipeline
webhook:
  url: "https://hooks.example.com/binex"
nodes:
  step1:
    agent: "local://echo"
    outputs: [result]
```
