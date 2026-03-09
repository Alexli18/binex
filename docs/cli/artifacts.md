# binex artifacts

## Synopsis

```
binex artifacts list RUN_ID [OPTIONS]
binex artifacts show ARTIFACT_ID [OPTIONS]
binex artifacts lineage ARTIFACT_ID [OPTIONS]
```

## Description

Manage and inspect artifacts produced by workflow runs.

- **list** -- show all artifacts for a given run, including their type and status.
- **show** -- display a single artifact's full metadata and content. When `rich` is installed, content is rendered as a Markdown panel.
- **lineage** -- render the full provenance chain as a tree view, tracing each artifact back through `derived_from` references recursively.

Artifacts are stored as JSON files in `.binex/artifacts/` and are keyed by artifact ID. Each artifact has:

- **id** -- unique identifier (typically `art_<node_id>`)
- **run_id** -- the run that produced it
- **type** -- artifact type (e.g., `result`, `input`, `decision`)
- **status** -- artifact status (e.g., `ready`)
- **content** -- the actual payload (string or JSON object)
- **lineage** -- provenance metadata (`produced_by` node and `derived_from` artifact IDs)

## Options

### artifacts list

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | Run to list artifacts for |
| `--json-output` / `--json` | flag | Output as JSON array |

### artifacts show

| Option | Type | Description |
|---|---|---|
| `ARTIFACT_ID` | `string` | Artifact to display |
| `--json-output` / `--json` | flag | Output full artifact model as JSON |

### artifacts lineage

| Option | Type | Description |
|---|---|---|
| `ARTIFACT_ID` | `string` | Artifact to trace provenance for |
| `--json-output` / `--json` | flag | Output lineage tree as JSON |

## Listing Artifacts

```bash
$ binex artifacts list run_f7a1b2c3

  art_fetch_data            type=result              status=ready
  art_transform             type=result              status=ready
  art_summarize             type=result              status=ready
  art_format_output         type=result              status=ready
```

When no artifacts exist for the run:

```
$ binex artifacts list run_nonexistent
No artifacts found for run 'run_nonexistent'.
```

### List as JSON

```bash
$ binex artifacts list run_f7a1b2c3 --json
```

```json
[
  {
    "id": "art_fetch_data",
    "run_id": "run_f7a1b2c3",
    "type": "result",
    "status": "ready",
    "content": {"articles": ["article1.txt", "article2.txt"]},
    "lineage": {
      "produced_by": "fetch_data",
      "derived_from": []
    }
  },
  {
    "id": "art_transform",
    "run_id": "run_f7a1b2c3",
    "type": "result",
    "status": "ready",
    "content": {"cleaned": "Merged text from 2 articles about AI safety..."},
    "lineage": {
      "produced_by": "transform",
      "derived_from": ["art_fetch_data"]
    }
  },
  {
    "id": "art_summarize",
    "run_id": "run_f7a1b2c3",
    "type": "result",
    "status": "ready",
    "content": "AI safety is a rapidly growing field that focuses on ensuring...",
    "lineage": {
      "produced_by": "summarize",
      "derived_from": ["art_transform"]
    }
  },
  {
    "id": "art_format_output",
    "run_id": "run_f7a1b2c3",
    "type": "result",
    "status": "ready",
    "content": "# AI Safety Report\n\n## Key Findings\n...",
    "lineage": {
      "produced_by": "format_output",
      "derived_from": ["art_summarize"]
    }
  }
]
```

## Showing an Artifact

### Plain Text (without `rich`)

```bash
$ binex artifacts show art_summarize

ID: art_summarize
Type: result
Run: run_f7a1b2c3
Status: ready
Produced by: summarize
Derived from: art_transform
Content: {"text": "AI safety is a rapidly growing field..."}
```

### Rich Output (with `rich` installed)

When `rich` is installed, the content is rendered as a Markdown panel:

```
ID: art_summarize
Type: result
Run: run_f7a1b2c3
Status: ready
Produced by: summarize
Derived from: art_transform
╭──────────── Content ─────────────╮
│                                  │
│ AI safety is a rapidly growing   │
│ field that focuses on ensuring   │
│ artificial intelligence systems  │
│ behave as intended...            │
│                                  │
╰──────────────────────────────────╯
```

### Show as JSON

```bash
$ binex artifacts show art_summarize --json
```

```json
{
  "id": "art_summarize",
  "run_id": "run_f7a1b2c3",
  "type": "result",
  "status": "ready",
  "content": "AI safety is a rapidly growing field that focuses on ensuring artificial intelligence systems behave as intended...",
  "lineage": {
    "produced_by": "summarize",
    "derived_from": ["art_transform"]
  }
}
```

### Different Artifact Types

**LLM result (string content):**

```
ID: art_summarize
Type: result
Run: run_f7a1b2c3
Status: ready
Produced by: summarize
Content: "AI safety is a rapidly growing field..."
```

**Local handler result (dict content):**

```
ID: art_fetch_data
Type: result
Run: run_f7a1b2c3
Status: ready
Produced by: fetch_data
Content: {"articles": ["article1.txt", "article2.txt"], "count": 2}
```

**Human approval decision:**

```
ID: art_review
Type: decision
Run: run_f7a1b2c3
Status: ready
Produced by: review
Content: "approved"
```

### Error: Artifact Not Found

```
$ binex artifacts show art_nonexistent
Error: Artifact 'art_nonexistent' not found.
```

## Lineage Tree

The `lineage` subcommand traces an artifact's full provenance chain, recursively following `derived_from` references to build a tree.

### Tree View

```bash
$ binex artifacts lineage art_format_output

art_format_output (type=result, produced_by=format_output)
└── art_summarize (type=result, produced_by=summarize)
    └── art_transform (type=result, produced_by=transform)
        └── art_fetch_data (type=result, produced_by=fetch_data)
```

**How to read this:** `art_format_output` was produced by the `format_output` node. Its input was `art_summarize`, which was produced by `summarize`, whose input was `art_transform`, and so on back to `art_fetch_data` at the root.

### Diamond Dependencies

When multiple nodes feed into the same downstream node, you may see shared ancestors appear in multiple branches:

```bash
$ binex artifacts lineage art_merge_output

art_merge_output (type=result, produced_by=merge)
└── art_branch_a (type=result, produced_by=branch_a)
    └── art_source (type=result, produced_by=source)
└── art_branch_b (type=result, produced_by=branch_b)
    └── art_source (type=result, produced_by=source)
```

The lineage engine uses cycle detection (`_ancestors` frozenset) to prevent infinite recursion on circular references, while still allowing the same artifact to appear in independent branches.

### Lineage as JSON

```bash
$ binex artifacts lineage art_format_output --json
```

```json
{
  "artifact_id": "art_format_output",
  "type": "result",
  "produced_by": "format_output",
  "parents": [
    {
      "artifact_id": "art_summarize",
      "type": "result",
      "produced_by": "summarize",
      "parents": [
        {
          "artifact_id": "art_transform",
          "type": "result",
          "produced_by": "transform",
          "parents": [
            {
              "artifact_id": "art_fetch_data",
              "type": "result",
              "produced_by": "fetch_data",
              "parents": []
            }
          ]
        }
      ]
    }
  ]
}
```

The JSON structure is recursive: each node has an `artifact_id`, `type`, `produced_by`, and `parents` array. Leaf nodes (no upstream dependencies) have `"parents": []`.

### Error: Artifact Not Found

```
$ binex artifacts lineage art_nonexistent
Error: Artifact 'art_nonexistent' not found.
```

## Use Cases

### Inspecting a Failed Run

After a run fails, list artifacts to see which nodes produced output and which did not:

```bash
# List what was produced
binex artifacts list run_d8e9f0a1

  art_fetch_data            type=result              status=ready
  art_transform             type=result              status=ready
```

Only 2 of 4 artifacts exist, meaning `summarize` and `format_output` never ran. Use `binex debug` to see errors, then `binex artifacts show` to inspect the last successful artifact:

```bash
binex artifacts show art_transform
```

### Comparing Artifacts Between Runs

After replaying a run with different agents, compare the outputs:

```bash
# Show the original summarize output
binex artifacts show art_summarize --json | jq '.content'

# Show the replay's summarize output (artifact IDs are the same pattern)
binex artifacts list run_e5f6a7b8
binex artifacts show art_summarize --json | jq '.content'
```

### Tracing Data Flow

Use `lineage` to understand how a final artifact was built:

```bash
binex artifacts lineage art_final_report
```

This helps answer: "What data went into this output?" and "Which nodes contributed to this result?"

## Tips

- Artifact IDs follow the pattern `art_<node_id>` by default, making them predictable.
- Use `--json` with `jq` for scripting: `binex artifacts list run_id --json | jq '.[].id'`
- The `content` field can be a string (LLM output) or a JSON object (local handler output). The `show` command handles both.
- Lineage trees are built on-demand by scanning the filesystem artifact store. There is no in-memory index, so the first call may be slightly slower on large runs.
- The `derived_from` field connects artifacts into a DAG. Each artifact knows its parent artifacts, not its parent nodes.

## See Also

- [binex run](run.md) -- produce artifacts by running a workflow
- [binex debug](debug.md) -- inspect execution records and errors
- [binex trace](trace.md) -- inspect execution steps
- [binex diff](diff.md) -- compare artifacts across runs
