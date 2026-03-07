# Agent Adapter Contract

## Protocol: AgentAdapter

Every agent backend must implement this protocol.

### execute

```
execute(task: TaskNode, input_artifacts: list[Artifact], trace_id: str) -> list[Artifact]
```

Dispatches a task to an agent and returns output artifacts.

| Parameter | Type | Description |
|-----------|------|-------------|
| task | TaskNode | The task to execute (includes spec, agent binding, inputs) |
| input_artifacts | list[Artifact] | Resolved input artifacts from upstream nodes |
| trace_id | string | Correlation ID for distributed tracing |
| **returns** | list[Artifact] | Output artifacts produced by the agent |

**Error behavior**: Raises adapter-specific exception on failure. The runtime catches and records in execution store.

### cancel

```
cancel(task_id: str) -> None
```

Cancels a running task. Best-effort — agents may not support cancellation.

### health

```
health() -> AgentHealth
```

Returns the current health status of the agent.

## Adapter Types

### A2AAgentAdapter

Communicates with remote A2A-compatible agents via the Google A2A SDK. Translates between Binex artifacts and A2A message/artifact format.

### LocalPythonAdapter

Executes agent logic in-process. The agent is a Python callable. No network overhead. Used for development and testing.

### LLMAdapter

Makes direct LLM calls via LiteLLM. No agent server needed. The task spec defines the prompt template and model. Useful for simple single-step LLM tasks.

## Registry Contract

### REST Endpoints

```
POST   /agents              Register an agent endpoint
GET    /agents               List all agents (filterable by capability, health)
GET    /agents/{id}          Get agent details
DELETE /agents/{id}          Deregister an agent
GET    /agents/search?capability=<cap>  Search by capability
GET    /health               Registry health check
```

### Agent Discovery (Pull-based)

The registry periodically crawls registered agent endpoints to:
1. Fetch/refresh the agent card (capabilities, metadata)
2. Check health (response time, error rate)
3. Update health status (alive/slow/degraded/down)
