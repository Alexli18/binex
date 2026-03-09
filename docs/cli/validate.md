# binex validate

## Synopsis

```
binex validate [OPTIONS] WORKFLOW_FILE
```

## Description

Validate a workflow YAML file without executing it. Performs three phases of checks:

1. **YAML parsing** — file loads as valid YAML and conforms to the workflow schema.
2. **DAG structure** — node dependencies form a valid directed acyclic graph (no cycles, no missing dependency refs, at least one entry node).
3. **Semantic checks** — interpolation references point to existing nodes and outputs, `when` conditions use valid syntax and reference nodes in `depends_on`, and all agent URIs use a recognized prefix (`local://`, `llm://`, `a2a://`, `human://`).

Exits `0` if valid, `2` if errors are found.

## Options

| Option | Type | Description |
|---|---|---|
| `WORKFLOW_FILE` | `Path` (must exist) | Workflow YAML file to validate |
| `--json-output` / `--json` | flag | Output as JSON |

## Examples

```bash
# Validate a workflow file
binex validate examples/simple.yaml

# JSON output for scripting
binex validate examples/simple.yaml --json
```

## Output: Success

```
Workflow 'research-pipeline' is valid.
  Nodes:  5
  Edges:  6
  Agents: llm://gpt-4o, llm://ollama/llama3.2
```

**JSON output on success:**

```json
{
  "valid": true,
  "node_count": 5,
  "edge_count": 6,
  "agents": [
    "llm://gpt-4o",
    "llm://ollama/llama3.2"
  ]
}
```

## Output: Validation Errors

Each error is printed to stderr with an `Error:` prefix. The command exits with code `2` on any error.

### Cycle Detection

When nodes form a circular dependency:

```
Error: Dependency cycle detected involving nodes: consumer, processor, producer
```

### Missing Dependency Reference

When `depends_on` names a node that does not exist:

```
Error: Node 'summarizer': depends_on references unknown node 'nonexistent_node'
```

### Unknown Interpolation Reference

When an input references a node that does not exist:

```
Error: Node 'writer', input 'data': interpolation references unknown node 'fetcher'
```

### Unknown Output Reference

When an input references an output that a node does not declare:

```
Error: Node 'reviewer', input 'draft': interpolation references unknown output 'summary' on node 'planner'
```

### No Entry Nodes

When every node has dependencies (no starting point):

```
Error: Workflow has no entry nodes (all nodes have dependencies)
```

### Invalid `when` Condition Syntax

The `when` field must match the pattern `${node.output} == value` or `${node.output} != value`:

```
Error: Node 'publisher': when condition has invalid syntax: 'status == approved'
```

### `when` Condition References Node Not in depends_on

The referenced node must be listed in the node's `depends_on`:

```
Error: Node 'publisher': when condition references node 'reviewer' which is not in depends_on
```

### Invalid YAML / Schema Error

When the file is not valid YAML or does not match the workflow schema:

```
Error: Workflow file is not valid YAML
```

### JSON Output on Failure

```json
{
  "valid": false,
  "errors": [
    "Dependency cycle detected involving nodes: consumer, processor, producer",
    "Node 'writer', input 'data': interpolation references unknown node 'fetcher'"
  ]
}
```

## Multiple Errors

The validator reports all errors it finds in a single pass, not just the first one. This makes it easier to fix everything at once:

```
Error: Node 'summarizer': depends_on references unknown node 'researcher3'
Error: Node 'output', input 'result': interpolation references unknown output 'summary' on node 'summarizer'
Error: Node 'publisher': when condition references node 'reviewer' which is not in depends_on
```

## Integrating Validate into CI

Use `--json` output for reliable parsing in CI pipelines:

```bash
# Simple pass/fail gate
binex validate workflow.yaml || exit 1

# Parse JSON output in CI
binex validate workflow.yaml --json | python -c "
import json, sys
result = json.load(sys.stdin)
if not result['valid']:
    for err in result['errors']:
        print(f'::error ::{err}')
    sys.exit(1)
print(f'Valid: {result[\"node_count\"]} nodes, {result[\"edge_count\"]} edges')
"
```

**GitHub Actions example:**

```yaml
- name: Validate workflows
  run: |
    for f in workflows/*.yaml; do
      echo "Validating $f..."
      binex validate "$f" || exit 1
    done
```

**Pre-commit hook:**

```bash
#!/usr/bin/env bash
# .git/hooks/pre-commit
for f in $(git diff --cached --name-only -- '*.yaml'); do
  if head -1 "$f" | grep -q "^name:"; then
    binex validate "$f" || exit 1
  fi
done
```

## Validate + Scaffold + Run Workflow

A common development cycle:

```bash
# 1. Generate a workflow
binex scaffold workflow --pattern research --no-interactive --name research.yaml

# 2. Validate it (catches structural issues before execution)
binex validate research.yaml

# 3. Run it
binex run research.yaml --var query="Analyze market trends"
```

## See Also

- [binex run](run.md) — execute a validated workflow
- [binex scaffold](scaffold.md) — generate agent and workflow templates
- [binex doctor](doctor.md) — check service health before running
