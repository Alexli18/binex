# A2A Gateway Design

**Date**: 2026-03-13
**Status**: Approved
**Branch**: `010-a2a-gateway`
**Version**: v0.3.0

## Overview

A2A Gateway is a proxy layer between the Binex orchestrator and remote A2A agents. It provides centralized authentication, capability-based routing, and automatic failover — enabling production-grade multi-agent deployments.

## Architecture

### Deployment Modes

**Embedded (default):** `binex run` starts the Gateway in-process. Zero config, zero friction. The orchestrator calls Gateway functions directly (no HTTP hop).

**Standalone:** `binex gateway --config gateway.yaml` runs a separate FastAPI server. The orchestrator connects via HTTP. Use this for multi-orchestrator setups or independent scaling.

**Selection logic:**
- If `gateway:` URL is specified in config → standalone (HTTP to external Gateway)
- Otherwise → embedded (in-process, no network overhead)

```
Embedded mode:
  Orchestrator ──(function call)──> Gateway logic ──(HTTP)──> Agent

Standalone mode:
  Orchestrator ──(HTTP)──> Gateway server ──(HTTP)──> Agent
```

### Module Structure

```
src/binex/gateway/
├── __init__.py           # public API: create_gateway()
├── app.py                # FastAPI app (standalone mode)
├── router.py             # capability resolver + explicit URL passthrough
├── auth.py               # pluggable auth middleware
├── fallback.py           # retry + failover logic
├── registry.py           # agent registry (capabilities, health, endpoints)
├── health.py             # background health checker
└── config.py             # GatewayConfig model (from gateway.yaml)
```

### Dependency Layer

```
models (zero deps)
  ↓
gateway.config (models)
  ↓
gateway.registry (models, gateway.config)
  ↓
gateway.auth (gateway.config)
gateway.router (gateway.registry)
gateway.fallback (gateway.registry, gateway.health)
gateway.health (gateway.registry)
  ↓
gateway.app (gateway.router, gateway.auth, gateway.fallback)
  ↓
adapters/a2a.py (gateway — optional, used when gateway is enabled)
  ↓
runtime/orchestrator.py (adapters)
  ↓
cli (runtime, gateway.app for standalone mode)
```

Key rule: `gateway` depends on `models` and `config` only. It must NOT import from `runtime`, `stores`, or `cli`. The orchestrator imports gateway, not the other way around.

## Authentication

### API Key Auth

Default auth mechanism. Simple, stateless, sufficient for most deployments.

**How it works:**
1. Client sends `X-API-Key` header with each request
2. Gateway middleware validates key against configured list
3. Invalid/missing key → `401 Unauthorized`

**Configuration (`gateway.yaml`):**

```yaml
auth:
  type: api_key
  keys:
    - name: orchestrator-1
      key: "bx-gw-key-abc123..."
    - name: orchestrator-2
      key: "bx-gw-key-def456..."
```

**Dev mode (no auth):**

```yaml
auth: null
```

### Pluggable Design

Auth is a middleware protocol:

```python
class GatewayAuth(Protocol):
    async def authenticate(self, request: Request) -> AuthResult: ...
```

Built-in implementations:
- `ApiKeyAuth` — checks `X-API-Key` header (v0.3)
- Future: `JwtAuth`, `MtlsAuth`

Selected via `auth.type` in config. Unknown type → startup error with clear message.

## Routing

### Dual Mode Resolution

The Gateway resolves agent references from workflow YAML using two modes:

**Explicit URL** — `a2a://http://localhost:9001`
- Contains `://` after the `a2a://` prefix
- Gateway proxies directly to the URL (no registry lookup)
- Auth and fallback still apply

**Capability-based** — `a2a://researcher`
- No `://` after prefix → treated as capability name
- Gateway queries registry for agents matching the capability
- Selection strategy: health (alive > degraded) → latency (lowest) → cost (cheapest)

**Parsing rule:**
```python
def resolve(agent_uri: str) -> str | list[str]:
    payload = agent_uri.removeprefix("a2a://")
    if "://" in payload:
        return payload  # explicit URL
    return registry.find_by_capability(payload)  # capability lookup
```

### Agent Registry

Agents register with capabilities, endpoints, and metadata:

```yaml
# gateway.yaml
agents:
  - name: researcher-arxiv
    endpoint: http://researcher-1.internal:9001
    capabilities: [research, search, arxiv]
    priority: 1

  - name: researcher-scholar
    endpoint: http://researcher-2.internal:9002
    capabilities: [research, search, scholar]
    priority: 2

  - name: summarizer-gpt4
    endpoint: http://summarizer.internal:9003
    capabilities: [summarize, report]
```

When workflow requests `a2a://research`:
1. Find agents where `"research"` is in capabilities → `[researcher-arxiv, researcher-scholar]`
2. Filter by health (alive only)
3. Sort by priority → latency → pick first

### Routing Hints in Workflow

Workflows can express routing preferences (optional):

```yaml
# workflow.yaml
nodes:
  researcher:
    agent: "a2a://research"
    routing:
      prefer: lowest_latency    # or: highest_priority, lowest_cost
      timeout_ms: 5000          # override default gateway timeout
```

If no `routing:` block, Gateway uses defaults from `gateway.yaml`.

## Fallback

### Retry + Failover Strategy

When an agent call fails:

```
1. Retry same agent (up to retry_count times, with exponential backoff)
   ├── Success → return result
   └── All retries exhausted → step 2

2. Failover to next agent with same capability
   ├── Success → return result
   └── No more candidates → step 3

3. Fail the node (return error to orchestrator)
```

**Configuration (`gateway.yaml`):**

```yaml
fallback:
  retry_count: 2
  retry_backoff: exponential     # fixed | exponential
  retry_base_delay_ms: 500
  failover: true                 # try alternative agents on failure
```

**Per-workflow override:**

```yaml
# workflow.yaml
nodes:
  critical_node:
    agent: "a2a://research"
    routing:
      retry_count: 3             # override gateway default
      failover: false            # don't failover for this node
```

### Health Checking

Background health checker polls registered agents:

```
Every 30s (configurable):
  For each registered agent:
    GET /health → update status

Status transitions:
  alive → degraded (response > 5s)
  alive → down (no response / error)
  degraded → alive (response < 5s)
  down → alive (successful response)
```

Health status affects routing: `alive` agents are preferred over `degraded`. `down` agents are excluded from routing.

## Configuration

### `gateway.yaml` Schema

```yaml
# .binex/gateway.yaml
host: "0.0.0.0"                 # standalone mode bind address
port: 8420                       # standalone mode port

auth:
  type: api_key                  # api_key | null
  keys:
    - name: main
      key: "${BINEX_GATEWAY_KEY}"  # env var interpolation

agents:
  - name: researcher-1
    endpoint: http://localhost:9001
    capabilities: [research, search]
    priority: 1
  - name: summarizer-1
    endpoint: http://localhost:9002
    capabilities: [summarize]

fallback:
  retry_count: 2
  retry_backoff: exponential
  retry_base_delay_ms: 500
  failover: true

health:
  interval_s: 30
  timeout_ms: 5000
```

### Config File Search Order

1. `--gateway` CLI flag (explicit path)
2. `.binex/gateway.yaml` (project-local)
3. `./gateway.yaml` (current directory)
4. No config found → pass-through mode (no auth, no routing, no fallback — direct proxy only)

### Workflow-Level Gateway Reference

```yaml
# workflow.yaml — optional, for standalone mode
gateway: http://gateway.internal:8420
```

If omitted, embedded mode is used.

## CLI

### New Commands

```bash
# Start standalone gateway
binex gateway [--config gateway.yaml] [--host 0.0.0.0] [--port 8420]

# Check gateway status
binex gateway status [--gateway http://...]

# List registered agents and their health
binex gateway agents [--gateway http://...]
```

### Updated Commands

```bash
# binex run — now supports gateway
binex run workflow.yaml                           # embedded gateway (auto)
binex run workflow.yaml --gateway http://gw:8420  # external gateway

# binex doctor — gateway health check added
binex doctor  # includes gateway connectivity test
```

## Data Flow

### Embedded Mode

```
binex run workflow.yaml
  │
  ├── Load workflow.yaml
  ├── Load gateway.yaml (if exists)
  ├── Start embedded Gateway (in-process)
  │     ├── Load agent registry
  │     ├── Start health checker (background)
  │     └── Initialize auth middleware
  │
  ├── Orchestrator starts DAG execution
  │     ├── Node needs a2a:// agent
  │     ├── A2AAdapter calls Gateway.route(agent_uri)
  │     │     ├── Resolve: explicit URL or capability lookup
  │     │     ├── Auth: inject X-API-Key for target agent (if configured)
  │     │     ├── Execute: POST /execute to resolved endpoint
  │     │     ├── On failure: retry → failover
  │     │     └── Return: ExecutionResult or error
  │     └── Orchestrator continues DAG
  │
  └── Shutdown: stop health checker, close connections
```

### Standalone Mode

```
Terminal 1: binex gateway --config gateway.yaml
  └── FastAPI server on :8420

Terminal 2: binex run workflow.yaml --gateway http://localhost:8420
  │
  ├── Orchestrator starts DAG execution
  │     ├── Node needs a2a:// agent
  │     ├── A2AAdapter sends HTTP to Gateway
  │     │     POST http://localhost:8420/route
  │     │     Headers: X-API-Key: bx-gw-key-...
  │     │     Body: {agent_uri, task_id, artifacts, ...}
  │     │
  │     ├── Gateway:
  │     │     ├── Authenticate request
  │     │     ├── Resolve agent
  │     │     ├── Forward to target agent
  │     │     ├── Handle retry/failover
  │     │     └── Return result
  │     │
  │     └── Orchestrator receives result, continues DAG
```

## API Endpoints (Standalone Mode)

```
POST /route              — route and forward a task to an agent
GET  /health             — gateway health check
GET  /agents             — list registered agents with health status
GET  /agents/{name}      — single agent details
POST /agents/refresh     — trigger health re-check for all agents
```

### POST /route

```json
// Request
{
  "agent_uri": "a2a://researcher",
  "task_id": "task_abc123",
  "skill": "research.search",
  "trace_id": "trace_xyz",
  "artifacts": [...],
  "routing": {                    // optional overrides
    "prefer": "lowest_latency",
    "timeout_ms": 5000,
    "retry_count": 3
  }
}

// Response (success)
{
  "artifacts": [...],
  "cost": 0.023,
  "routed_to": "researcher-arxiv",
  "endpoint": "http://researcher-1.internal:9001",
  "attempts": 1
}

// Response (all agents failed)
{
  "error": "All agents for capability 'research' are unavailable",
  "attempts": [
    {"agent": "researcher-arxiv", "error": "Connection timeout", "retries": 2},
    {"agent": "researcher-scholar", "error": "Connection refused", "retries": 2}
  ]
}
```

## Models

```python
# gateway/config.py
class GatewayConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8420
    auth: AuthConfig | None = None
    agents: list[AgentEntry] = []
    fallback: FallbackConfig = FallbackConfig()
    health: HealthConfig = HealthConfig()

class AuthConfig(BaseModel):
    type: Literal["api_key"] = "api_key"
    keys: list[ApiKeyEntry] = []

class ApiKeyEntry(BaseModel):
    name: str
    key: str

class AgentEntry(BaseModel):
    name: str
    endpoint: str
    capabilities: list[str] = []
    priority: int = 0

class FallbackConfig(BaseModel):
    retry_count: int = 2
    retry_backoff: Literal["fixed", "exponential"] = "exponential"
    retry_base_delay_ms: int = 500
    failover: bool = True

class HealthConfig(BaseModel):
    interval_s: int = 30
    timeout_ms: int = 5000
```

## Testing Strategy

- Unit tests: router resolution, auth middleware, fallback logic, config loading
- Integration tests: embedded gateway + orchestrator, health checker
- Mock agents: simple FastAPI apps returning canned responses
- Patch `_get_stores()` pattern for CLI tests (consistent with existing)
- Target: full coverage of all routing paths, auth scenarios, and fallback chains

## Security Notes

- API keys in `gateway.yaml` support `${ENV_VAR}` interpolation — never hardcode secrets
- Gateway does NOT validate target agent IPs (no SSRF protection) — consistent with existing A2AAdapter
- Auth middleware runs before routing — unauthenticated requests never reach agents
- `yaml.safe_load()` for all config parsing (consistent with project convention)

## Out of Scope (v0.3)

- JWT / mTLS auth (pluggable design allows future addition)
- Agent auto-discovery (agents must be manually registered in gateway.yaml)
- Rate limiting per client/agent
- Request/response transformation
- WebSocket support for streaming
- Multi-gateway federation
