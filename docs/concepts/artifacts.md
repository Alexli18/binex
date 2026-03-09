# Artifacts

## What is an Artifact?

```python
class Artifact(BaseModel):
    id: str
    run_id: str
    type: str
    content: Any = None
    status: Literal["complete", "partial"] = "complete"
    lineage: Lineage
    created_at: datetime
```

An artifact is any piece of data produced or consumed by a node during a workflow run. Artifacts carry their content, a type label, and a [lineage](lineage.md) record that tracks provenance.

## How It Works

When a node finishes execution, the runtime wraps each declared output into an `Artifact` and persists it to the artifact store. Downstream nodes reference these artifacts using `${node.output_name}` syntax in their `inputs` block. The runtime resolves these references and passes the corresponding artifacts to the next agent.

Artifacts are stored as JSON files under `.binex/artifacts/` on disk via `FilesystemArtifactStore`. Each artifact gets a unique `id` scoped to its `run_id`.

The `status` field supports streaming use cases: an artifact can be `"partial"` while being produced incrementally, then marked `"complete"` when finalized.

## Example

A persisted artifact as JSON:

```json
{
  "id": "producer-result-a1b2c3",
  "run_id": "run-001",
  "type": "text",
  "content": "Hello, Binex",
  "status": "complete",
  "lineage": {
    "produced_by": "producer",
    "derived_from": []
  },
  "created_at": "2026-03-08T10:00:00Z"
}
```

## Related Concepts

- [Lineage](lineage.md) -- every artifact embeds a lineage record
- [Execution](execution.md) -- execution records reference input and output artifacts
- [Workflows](workflows.md) -- artifacts flow between nodes in a workflow
