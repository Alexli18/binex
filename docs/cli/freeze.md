# binex freeze

## Synopsis

```
binex freeze WORKFLOW [-o binex.lock] [--check]
```

## Description

Writes a **lockfile** for a pipeline — a `package-lock.json` for a workflow. For
every node it records the agent, resolved model, and content hashes of the
prompt, parameters, and tool set, plus a combined node hash. `binex run --frozen`
and `binex freeze --check` then report what drifted since the lock was written.

Because Binex owns both the spec and the run, it can answer "why did yesterday's
run behave differently" structurally — something observability-only tools can't.

## Options

| Option | Type | Description |
|---|---|---|
| `WORKFLOW` | `Path` | Workflow YAML to lock or check |
| `-o` / `--output` | `str` | Lockfile path (default: `binex.lock`) |
| `--check` | flag | Report drift against the lockfile instead of writing it |

## Writing a lock

```bash
$ binex freeze workflow.yaml
Wrote binex.lock (3 nodes).
Note: 1 node(s) use unpinnable model aliases (writer) — the provider can change
them underneath the lock. Use a dated snapshot to pin.
```

## Honesty of the lock

`gpt-4o` is a **pointer** — the provider swaps weights underneath it, so a lock
can't truly freeze it. The lock marks such aliases `pinned: false`; a dated
snapshot (`gpt-4o-2024-11-20`) or a digest (`ollama/llama3@sha256:...`) is
`pinned: true`. A lockfile that pretended more determinism than exists would be
worse than none.

> **v1 limitation:** the lock flags pinnability from the model string; it does
> not resolve an alias to its current dated snapshot or query an Ollama digest
> (those need provider APIs). Pin explicitly with a dated model where it matters.

## Checking for drift

```bash
$ binex freeze workflow.yaml --check
Drift detected vs binex.lock:
  - node 'researcher': prompt changed
  - node 'writer': model changed
```

`binex run WORKFLOW --frozen [--lockfile binex.lock]` runs the same check before
executing and **fails** on any drift — half the answer to "why did yesterday's
run behave differently", delivered before you debug anything.

## See also

- [`binex diff`](diff.md) — compare two runs
- [`binex run`](run.md) — `--frozen` / `--lockfile`
