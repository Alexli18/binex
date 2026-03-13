# binex gateway

## Synopsis

```
binex gateway [--config PATH] [--host TEXT] [--port INT]
binex gateway status [--gateway URL] [--json]
binex gateway agents [--gateway URL] [--json]
```

## Description

`binex gateway` manages the A2A Gateway -- a standalone FastAPI server that routes requests to registered remote agents. It:

1. Loads gateway configuration from YAML (resolving `${ENV_VAR}` references)
2. Registers agents from the config and starts background health checking
3. Serves a REST API for routing, health, and agent listing

When invoked without a subcommand, `binex gateway` starts the server. Use `status` and `agents` subcommands to query a running gateway.

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Config error (no config found) or connection error |

## Options

### gateway (start server)

| Option | Type | Description |
|---|---|---|
| `--config` | `Path` | Path to `gateway.yaml` config file. If omitted, searches `.binex/gateway.yaml` then `./gateway.yaml`. |
| `--host` | `string` | Override bind host (default from config: `0.0.0.0`). |
| `--port` | `int` | Override bind port (default from config: `8420`). |

### status

| Option | Type | Description |
|---|---|---|
| `--gateway` | `URL` | Gateway URL to query (default: `http://localhost:8420`). |
| `--json` | flag | Output as JSON. |

### agents

| Option | Type | Description |
|---|---|---|
| `--gateway` | `URL` | Gateway URL to query (default: `http://localhost:8420`). |
| `--json` | flag | Output as JSON. |

## Starting the Gateway

```bash
$ binex gateway --config gateway.yaml

A2A Gateway starting on 0.0.0.0:8420
  Auth: api_key (2 keys configured)
  Agents: 3 registered
  Health check: every 30s
```

The server runs in the foreground via uvicorn. Press `Ctrl+C` to stop.

### Config Search Order

When `--config` is not provided, binex searches for configuration in this order:

1. `.binex/gateway.yaml` (project-local)
2. `./gateway.yaml` (current directory)

If no config file is found, the command exits with an error:

```bash
$ binex gateway

Error: No gateway config found. Provide --config or create gateway.yaml.
```

### Example Configuration

```yaml
host: "0.0.0.0"
port: 8420

auth:
  type: api_key
  keys:
    - name: dev
      key: "${GATEWAY_DEV_KEY}"
    - name: ci
      key: "${GATEWAY_CI_KEY}"

agents:
  - name: summarizer
    endpoint: "http://localhost:9001"
    capabilities: [summarize, translate]
    priority: 10
  - name: researcher
    endpoint: "http://localhost:9002"
    capabilities: [search, extract]
    priority: 5
  - name: formatter
    endpoint: "http://localhost:9003"
    capabilities: [format]
    priority: 0

fallback:
  retry_count: 2
  retry_backoff: exponential
  retry_base_delay_ms: 500
  failover: true

health:
  interval_s: 30
  timeout_ms: 5000
```

Environment variables referenced as `${VAR}` are resolved at load time. If a referenced variable is not set, the command exits with an error.

## Gateway Status

```bash
$ binex gateway status

Gateway: http://localhost:8420
Status: healthy
Agents: 3 total (3 alive, 0 degraded, 0 down)
```

### JSON Output

```bash
$ binex gateway status --json
```

```json
{
  "gateway": "http://localhost:8420",
  "status": "healthy",
  "agents_total": 3,
  "agents_alive": 3,
  "agents_degraded": 0,
  "agents_down": 0
}
```

### Connection Error

```bash
$ binex gateway status --gateway http://localhost:9999

Error: Cannot connect to gateway at http://localhost:9999
```

## Listing Agents

```bash
$ binex gateway agents

  summarizer [alive]
    capabilities: summarize, translate
    priority: 10  latency: 42ms
  researcher [alive]
    capabilities: search, extract
    priority: 5  latency: 67ms
  formatter [degraded]
    capabilities: format
    priority: 0  latency: 320ms
```

When no agents are registered, a plain message is shown:

```
No agents registered.
```

### JSON Output

```bash
$ binex gateway agents --json
```

```json
{
  "agents": [
    {
      "name": "summarizer",
      "endpoint": "http://localhost:9001",
      "capabilities": ["summarize", "translate"],
      "priority": 10,
      "health": "alive",
      "last_latency_ms": 42
    },
    {
      "name": "researcher",
      "endpoint": "http://localhost:9002",
      "capabilities": ["search", "extract"],
      "priority": 5,
      "health": "alive",
      "last_latency_ms": 67
    },
    {
      "name": "formatter",
      "endpoint": "http://localhost:9003",
      "capabilities": ["format"],
      "priority": 0,
      "health": "degraded",
      "last_latency_ms": 320
    }
  ]
}
```

### Connection Error

```bash
$ binex gateway agents --gateway http://localhost:9999

Error: Cannot connect to gateway at http://localhost:9999
```

## Health Statuses

The gateway classifies agent and overall health as follows:

| Agent Status | Meaning |
|---|---|
| `alive` | Agent responded to health check successfully |
| `degraded` | Agent responded but with elevated latency or errors |
| `down` | Agent failed to respond to health check |

| Overall Status | Condition |
|---|---|
| `healthy` | All agents alive |
| `degraded` | At least one agent is degraded or down (but not all down) |
| `unhealthy` | All agents are down |

## Tips

- Use `binex gateway status --json` in CI scripts to check gateway readiness before running workflows.
- The gateway is stateless -- agent registry is loaded from `gateway.yaml` at startup and health status is kept in-memory. Restart the server to pick up config changes.
- Use `${ENV_VAR}` syntax in `gateway.yaml` for secrets (API keys, endpoints). Never commit secrets to version control.
- The default port is `8420`. Override with `--port` or set `port` in `gateway.yaml`.
- Auth is optional. When configured, the `/agents` and `/agents/refresh` endpoints require a valid API key in the request headers.

## See Also

- [binex run](run.md) -- execute workflows (use `a2a://` agents routed through the gateway)
- [Architecture > Adapters](../architecture/adapters.md) -- how `A2AAgentAdapter` connects to gateway agents
