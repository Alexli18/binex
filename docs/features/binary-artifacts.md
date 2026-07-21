# Binary artifacts

Binex passes typed artifacts node-to-node. Historically those were JSON-only, so
a node producing **media** — an image generator, TTS, a PDF renderer — had no
native way to emit its result into the DAG, lineage, and debug views. Binary
artifacts fix that.

> Files agents create *inside a project* are the [workspace](workspace.md)'s job.
> This is about artifacts as node **outputs** flowing along the DAG.

## Model: envelope + content-addressed payload

An artifact is a JSON envelope plus, for binaries, a payload:

- **JSON artifacts** are unchanged (backward compatible).
- A **binary artifact**'s `content` is the envelope:

  ```json
  {"kind": "binary", "mime": "image/png", "size": 12345,
   "sha256": "<hex>", "path": "/abs/.../blobs/<sha256>"}
  ```

  The bytes live at `.binex/artifacts/blobs/<sha256>`.

Content addressing buys two things for free:

- **Deduplication** — an asset flowing through five nodes is stored once.
- **A cache key** — node caching (#68) already hashes artifact content, so the
  sha256 in the envelope is picked up automatically.

## Producing a binary artifact

From a `python://` / `local://` handler:

```python
from binex.artifacts import make_binary_artifact

async def render(task, inputs):
    png_bytes = my_renderer(...)
    return [make_binary_artifact(task.run_id, task.node_id, png_bytes, "image/png")]
```

`make_binary_artifact` stores the blob (deduping by content) and returns a normal
`Artifact` whose `content` is the envelope — it flows through the DAG, lineage,
and debug views like any other.

## Feeding binaries into LLM nodes

Binaries are routed into the model **by mime type**:

| Input | Vision model | Non-vision model |
|---|---|---|
| `image/*` | sent as an image (LiteLLM multimodal) | textual descriptor + file passthrough |
| `audio/*`, `video/*` | descriptor (until providers catch up) | descriptor |

When an image reaches a model that lacks vision, Binex logs a warning
(*"node X receives an image but model Y lacks vision — passing as descriptor"*)
and the payload still travels the DAG intact, so a downstream vision node — or a
file tool — can consume it.

## Housekeeping

Blobs are content-addressed and can accumulate. Garbage-collect the ones no run
references:

```bash
binex clean blobs            # delete unreferenced blobs
binex clean blobs --dry-run  # report how much would be freed
```

## v1 boundaries

- Size limit: 100MB (configurable via `make_binary_artifact(max_bytes=...)`).
- No transcoding; no image diffing (semantic diff reports "hashes differ").
- **Deferred:** a blob-serving UI (image previews, lineage thumbnails, audio
  player, PDF view) and a native `media://` adapter (e.g.
  `media://openai/dall-e-3`). With this plus `python://`, you can already wire
  any generator yourself — the native node is convenience, not unblocking.
