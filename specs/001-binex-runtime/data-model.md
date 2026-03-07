# Data Model: Binex Runtime

**Date**: 2026-03-07
**Feature**: 001-binex-runtime

## Entities

### WorkflowSpec

Parsed representation of a YAML/JSON workflow definition.

| Field | Type | Description |
|-------|------|-------------|
| name | string | Workflow identifier |
| description | string | Human-readable description |
| nodes | map[string, NodeSpec] | Node definitions keyed by node ID |
| defaults | DefaultsSpec | Default retry_policy and deadline for all nodes |

### NodeSpec

A single node definition within a workflow.

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique node identifier within workflow |
| agent | string | Agent endpoint URL or registry reference |
| skill | string | Capability/skill identifier |
| inputs | map[string, string] | Input bindings (may reference other nodes' outputs via `${node.output}`) |
| outputs | list[string] | Named output artifact types |
| depends_on | list[string] | Node IDs this node depends on |
| retry_policy | RetryPolicy (optional) | Override for default retry policy |
| deadline_ms | integer (optional) | Override for default deadline |

### TaskNode (Runtime)

Runtime representation of a node during execution.

| Field | Type | Description |
|-------|------|-------------|
| id | string | Matches NodeSpec.id |
| run_id | string | Run this node belongs to |
| spec | NodeSpec | Original node specification |
| status | TaskStatus | Current lifecycle state |
| adapter | AgentAdapter | Resolved adapter for execution |
| input_artifact_refs | list[string] | Resolved input artifact IDs |
| output_artifact_refs | list[string] | Produced output artifact IDs |
| attempt | integer | Current retry attempt (starts at 1) |

### TaskStatus (Enum)

```
requested -> accepted -> running -> completed
                                 -> failed
                                 -> cancelled
                                 -> timed_out
```

Valid transitions:
- requested -> accepted (agent acknowledges)
- accepted -> running (execution begins)
- running -> completed (success)
- running -> failed (error)
- running -> cancelled (user/system cancellation)
- running -> timed_out (deadline exceeded)
- failed -> requested (retry)

### RetryPolicy

| Field | Type | Description |
|-------|------|-------------|
| max_retries | integer | Maximum retry attempts (default: 1) |
| backoff | string | Backoff strategy: "fixed", "exponential" (default: "exponential") |

### Artifact

A typed output produced by a task node.

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique artifact identifier (e.g., art_plan_01) |
| run_id | string | Run that produced this artifact |
| type | string | Artifact type name (e.g., "execution_plan", "search_results") |
| content | any | Artifact payload (structured data) |
| status | string | "complete" or "partial" |
| lineage | Lineage | Provenance metadata |
| created_at | datetime | Creation timestamp |

### Lineage

| Field | Type | Description |
|-------|------|-------------|
| produced_by | string | Task node ID that produced this artifact |
| derived_from | list[string] | Artifact IDs this artifact was derived from |

### ArtifactRef

Lightweight reference to an artifact (used in execution records).

| Field | Type | Description |
|-------|------|-------------|
| artifact_id | string | Reference to Artifact.id |
| type | string | Artifact type name |

### ExecutionRecord

Metadata about a single node execution.

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique record identifier |
| run_id | string | Run identifier |
| task_id | string | Node identifier within run |
| parent_task_id | string (optional) | Parent node (for sub-DAGs) |
| agent_id | string | Agent identifier (endpoint or name) |
| status | TaskStatus | Final status of this execution |
| input_artifact_refs | list[string] | Input artifact IDs |
| output_artifact_refs | list[string] | Output artifact IDs |
| prompt | string (optional) | LLM prompt used (if applicable) |
| model | string (optional) | LLM model used (if applicable) |
| tool_calls | list[object] (optional) | Tool calls made during execution |
| latency_ms | integer | Execution duration in milliseconds |
| timestamp | datetime | Execution start time |
| trace_id | string | Trace correlation ID |
| error | string (optional) | Error message if failed |

### RunSummary

Summary of a complete workflow run.

| Field | Type | Description |
|-------|------|-------------|
| run_id | string | Unique run identifier |
| workflow_name | string | Name of the executed workflow |
| status | string | Overall run status (completed/failed/cancelled) |
| started_at | datetime | Run start time |
| completed_at | datetime (optional) | Run completion time |
| total_nodes | integer | Total number of nodes |
| completed_nodes | integer | Number of completed nodes |
| failed_nodes | integer | Number of failed nodes |
| forked_from | string (optional) | Original run_id if this is a replay |
| forked_at_step | string (optional) | Step from which replay started |

### AgentInfo

Registry entry for a discovered agent.

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique agent identifier |
| endpoint | string | Agent URL |
| name | string | Human-readable name |
| capabilities | list[string] | List of capability/skill identifiers |
| health | AgentHealth | Current health status |
| latency_avg_ms | integer | Average response latency |
| last_seen | datetime | Last successful health check |
| agent_card | object | Raw A2A Agent Card data |

### AgentHealth (Enum)

```
alive -> slow -> degraded -> down
```

- alive: Responding within normal latency
- slow: Responding but above latency threshold
- degraded: Intermittent failures
- down: Consecutive failures exceed threshold

## Relationships

```
WorkflowSpec 1──* NodeSpec (nodes map)
Run 1──* TaskNode (runtime nodes)
Run 1──* ExecutionRecord (execution history)
Run 1──* Artifact (produced artifacts)
TaskNode *──1 NodeSpec (specification)
Artifact *──* Artifact (lineage: derived_from)
Artifact *──1 TaskNode (lineage: produced_by)
ExecutionRecord *──* Artifact (input/output refs)
RunSummary ──? RunSummary (forked_from for replays)
```

## Storage Mapping

### Execution Store (SQLite default)

Tables:
- `runs` -> RunSummary fields
- `execution_records` -> ExecutionRecord fields
- `artifacts_meta` -> Artifact metadata (id, run_id, type, lineage, status, created_at)

### Artifact Store (Filesystem default)

Structure:
```
.binex/artifacts/
  {run_id}/
    {artifact_id}.json    # artifact content + metadata
```
