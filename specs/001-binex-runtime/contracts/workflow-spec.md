# Workflow Spec Contract

## Format

YAML or JSON file defining a DAG of task nodes.

## Schema

```yaml
name: string                    # Required. Workflow identifier.
description: string             # Optional. Human-readable description.

nodes:                          # Required. Map of node ID -> node definition.
  <node-id>:
    agent: string               # Required. Agent endpoint URL or registry ref.
    skill: string               # Optional. Capability/skill identifier.
    inputs:                     # Optional. Input bindings.
      <key>: string             #   Static value or interpolation: "${node.output}"
    outputs: [string]           # Required. Named output artifact types.
    depends_on: [string]        # Optional. Node IDs this node depends on.
    retry_policy:               # Optional. Overrides defaults.
      max_retries: integer      #   Default: 1
      backoff: string           #   "fixed" | "exponential". Default: "exponential"
    deadline_ms: integer        # Optional. Overrides defaults.

defaults:                       # Optional. Default settings for all nodes.
  deadline_ms: integer          #   Default: 120000 (2 minutes)
  retry_policy:
    max_retries: integer
    backoff: string
```

## Variable Interpolation

Input values support `${<node-id>.<output-name>}` syntax to reference output artifacts from upstream nodes.

**Rules**:
- Referenced node must be in `depends_on` (directly or transitively)
- Referenced output must be in the source node's `outputs` list
- `${user.<key>}` references workflow-level inputs (passed via `--var`)

## Validation Rules

1. All `depends_on` references must point to existing node IDs
2. The dependency graph must be acyclic (DAG)
3. All `${node.output}` interpolations must reference valid nodes and outputs
4. At least one node must have no dependencies (entry point)
5. Node IDs must be unique within the workflow
6. Agent URLs must be syntactically valid

## Example

```yaml
name: research-pipeline
description: "Multi-agent research pipeline"

nodes:
  planner:
    agent: http://localhost:9001
    skill: planning.research
    inputs:
      query: "${user.query}"
    outputs: [execution_plan]

  researcher_1:
    agent: http://localhost:9002
    skill: research.search
    inputs:
      plan: "${planner.execution_plan}"
      source: arxiv
    outputs: [search_results]
    depends_on: [planner]

  researcher_2:
    agent: http://localhost:9003
    skill: research.search
    inputs:
      plan: "${planner.execution_plan}"
      source: google_scholar
    outputs: [search_results]
    depends_on: [planner]

  validator:
    agent: http://localhost:9004
    skill: analysis.validate
    inputs:
      results:
        - "${researcher_1.search_results}"
        - "${researcher_2.search_results}"
    outputs: [validated_results]
    depends_on: [researcher_1, researcher_2]
    retry_policy:
      max_retries: 2
      backoff: exponential

  summarizer:
    agent: http://localhost:9005
    skill: analysis.summarize
    inputs:
      validated: "${validator.validated_results}"
    outputs: [summary_report]
    depends_on: [validator]
    deadline_ms: 60000

defaults:
  deadline_ms: 120000
  retry_policy:
    max_retries: 1
```
