# Lineage

## What is Lineage?

```python
class Lineage(BaseModel):
    produced_by: str
    derived_from: list[str] = Field(default_factory=list)
```

Lineage is the provenance record embedded in every [artifact](artifacts.md). It answers two questions: which node produced this artifact, and which upstream artifacts was it derived from.

## How It Works

When the runtime creates an output artifact for a node, it sets `produced_by` to the node's ID and populates `derived_from` with the IDs of all input artifacts that were passed to that node. This creates a tree of dependencies that can be walked from any artifact back to the original user inputs.

Lineage is recorded automatically -- agents do not need to manage it. The runtime inspects the resolved inputs for each node and captures the artifact IDs before forwarding them to the adapter.

## Example

Consider a three-node pipeline: `fetch` produces raw data, `transform` processes it, and `summarize` condenses the result.

```json
{
  "id": "fetch-result-001",
  "lineage": { "produced_by": "fetch", "derived_from": [] }
}

{
  "id": "transform-result-002",
  "lineage": { "produced_by": "transform", "derived_from": ["fetch-result-001"] }
}

{
  "id": "summarize-result-003",
  "lineage": { "produced_by": "summarize", "derived_from": ["transform-result-002"] }
}
```

Walking `derived_from` backwards from `summarize-result-003` produces the full lineage tree:

```
summarize-result-003
  └── transform-result-002
        └── fetch-result-001
```

This chain lets you trace any output back through every transformation to the original input, which is critical for debugging and auditing workflow runs.

## Related Concepts

- [Artifacts](artifacts.md) -- lineage is a field on every artifact
- [Execution](execution.md) -- execution records track the agent invocations that produce lineage
