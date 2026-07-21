# Workspace

Binex passes small JSON artifacts node-to-node. But many real workflows are
agents collaborating on an **accumulating body of files** — a codebase, a
document set, a dataset. A coder writes `src/`, an asset agent fills `assets/`,
a tester runs the build. A **workspace** models exactly that: a shared directory
the run's nodes read and write.

```yaml
name: build-a-site
workspace:
  source: empty            # empty | copy | git
nodes:
  scaffold:
    agent: "llm://gpt-4o"
    outputs: [note]
    workspace: write        # write nodes serialize
  style:
    agent: "llm://gpt-4o"
    outputs: [note]
    workspace: write
    depends_on: [scaffold]
  review:
    agent: "llm://gpt-4o"
    outputs: [report]
    workspace: read         # read nodes parallelize
    depends_on: [style]
```

## The workspace is a git repository

Physically the workspace lives at `.binex/workspaces/<run_id>/` and **is a git
repo**. After each *write* node completes, Binex makes an automatic commit
tagged `node: <id>`. That single decision buys four things at once:

- **"Files changed by node X"** — a `git diff` between commits.
- **File-level lineage** — `git log` says who last touched a file.
- **Rollback** — for free.
- **Restore points** — replaying node 5 needs the file state as of node 4; that's
  a checkout. Without snapshots, replay is fundamentally broken for file-based
  workflows (nodes mutate files, state is lost). With them, replay and resume
  transfer to the file world almost for free.

## Declaring a workspace

| `source` | Meaning |
|---|---|
| `empty` | Start from an empty git repo (default) |
| `copy` | Seed from a local directory (`path:`) |
| `git` | Clone a repository (`path:` = URL, optional `ref:`) |

Shorthand: `workspace: ./some/dir` is `source: copy, path: ./some/dir`.

## Node access

Each participating node declares `workspace: read` or `workspace: write`:

- **LLM nodes** automatically get `read_file` / `write_file` / `list_files`
  tools, **jailed to the workspace root**. Absolute paths, `..` traversal, and
  symlinks that escape the root are all rejected — a prompt-injected model
  cannot read or write outside the sandbox (important with `shell_command`).
- **`local://` / `python://` handlers** receive the root via
  `task.config["_workspace_root"]` and can read/write it directly.

## Concurrency (correct, if restrictive)

Two parallel nodes writing the same workspace would race, and their per-node
commits would interleave. v1 is simple and correct: an async readers-writer lock
**serializes writers among themselves** while **readers parallelize freely**.
Per-node worktree branches with automatic merge is a deferred v2 —
agent-vs-agent merge conflicts are a can of worms we don't open yet.

## Coexistence with artifacts

Pipe-passed JSON artifacts remain the mechanism for small structured data
between nodes. Workspaces are for the shared file corpus. The two coexist by
design — use artifacts for "here's the plan", the workspace for "here's the
code".

## Housekeeping

Workspaces are heavy. Reclaim them with:

```bash
binex clean workspaces                 # delete all run workspaces
binex clean workspaces --older-than 7  # only those older than 7 days
binex clean workspaces --dry-run       # report without deleting
```

## Requirements & scope

- Requires `git` on the PATH.
- **v1 scope:** single shared tree with read/write serialization. Deferred:
  per-node worktree merge, and the debug "Files changed" tab / `binex diff`
  workspace comparison (a follow-up).
