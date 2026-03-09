# binex artifacts

## Synopsis

```
binex artifacts list RUN_ID [OPTIONS]
binex artifacts show ARTIFACT_ID [OPTIONS]
binex artifacts lineage ARTIFACT_ID [OPTIONS]
```

## Description

Manage and inspect artifacts produced by workflow runs.

- **list** -- show all artifacts for a given run.
- **show** -- display a single artifact's metadata and content.
- **lineage** -- render the full provenance chain as a tree view, tracing each artifact back through `derived_from` references.

## Options

### artifacts list

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | Run to list artifacts for |
| `--json-output` / `--json` | flag | Output as JSON |

### artifacts show

| Option | Type | Description |
|---|---|---|
| `ARTIFACT_ID` | `string` | Artifact to display |
| `--json-output` / `--json` | flag | Output as JSON |

### artifacts lineage

| Option | Type | Description |
|---|---|---|
| `ARTIFACT_ID` | `string` | Artifact to trace |
| `--json-output` / `--json` | flag | Output as JSON |

## Example

```bash
# List all artifacts from a run
binex artifacts list abc123

# Show a specific artifact
binex artifacts show art_producer

# Trace provenance
binex artifacts lineage art_consumer --json
```

## Output

`artifacts show` output:

```
ID: art_producer
Type: result
Run: abc123
Status: ready
Produced by: producer
Derived from: art_init
Content: {"msg": "hello world"}
```

`artifacts lineage` renders a tree:

```
art_consumer (result)
  art_producer (result)
    art_init (input)
```

## See Also

- [binex trace](trace.md) -- inspect execution steps
- [binex run](run.md) -- produce artifacts by running a workflow
