# binex resume

## Synopsis

```
binex resume RUN_ID [--from NODE] [--force] [OPTIONS]
```

## Description

Continue a failed or interrupted run from the point where it stopped. Unlike
[`replay`](replay.md) — which re-executes from a step you choose — `resume`
figures out what to redo automatically: nodes that **completed** are cached
(their artifacts are reused, so the budget is not re-spent), while **failed**,
**timed-out**, never-started, and orphaned-`running` nodes are re-executed.

The resumed run is stored as a new run with its own `run_id`, linked to the
parent via `resumed_from` metadata. This keeps runs immutable so `diff`,
`bisect`, and lineage continue to work. `resumed_from` is distinct from
`forked_from` (used by `replay`): a resume is a **continuation of the same
intent**, not a new experiment.

The workflow definition is loaded from the parent run's recorded path.

Exits `0` on success, `1` on failure.

## Options

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | The run to resume |
| `--from` | `string` | Force re-execution from this node and everything downstream, overriding the status-based partition |
| `--force` | flag | Override topology-drift and `running`-status refusals |
| `--json-output` / `--json` | flag | Output as JSON |

## Basic Example

```bash
# A run failed at node 9 of 10 — continue where it stopped
binex resume run_a1b2c3d4
```

**Output:**

```
Resume Run ID: run_e5f6a7b8c9d0
Resumed from: run_a1b2c3d4
Workflow: report-pipeline
Status: completed
Nodes: 10/10 completed (8 cached, 2 re-run)
Cost (cumulative): $0.0431
```

## How nodes are partitioned

For a run with a parallel DAG, the set of completed nodes is not a simple
prefix — one branch may have finished while another failed. Resume partitions
by **actual node status**:

- **Cached** — nodes that `COMPLETED` in the parent, whose definition is
  unchanged, and whose entire upstream is also cached.
- **Re-run** — `FAILED`, `TIMED_OUT`, never-started (pending), and
  orphaned-`RUNNING` nodes (a node left `running` with no result has no
  artifact to reuse).

## Which runs can be resumed

| Parent status | Behaviour |
|---|---|
| `failed` / `timed_out` | Resumes freely |
| `cancelled` / `stopped` | Resumes, but warns — the stop was deliberate; the explicit `resume` command is your intent |
| `running` | **Refused** by default — the run may still be live in another process (two orchestrators writing the same DB). Use `--force` only when the process is confirmed dead |
| `completed` | Error — nothing to resume |

## Workflow drift

If you edit the workflow between the failed run and the resume, `resume`
detects it **per node**:

- A completed node whose definition (agent, prompt, inputs, config, tools,
  dependencies) is unchanged → its cached artifact is reused.
- A completed node whose definition changed → it and everything downstream are
  re-run, so a stale artifact is never fed into a changed node.
- A **topology change** (a depended-on node removed) → resume is **refused**
  unless you pass `--force`.

## `--from` — force re-execution

```bash
# Redo node "enrich" and every node that depends on it, even if they completed
binex resume run_a1b2c3d4 --from enrich
```

This is the manual override: the node and all its descendants move from cached
to re-run.

## Budget

Budget is cumulative across a resume chain: the child run starts from the
parent's accumulated cost, so a workflow budget cap cannot be evaded by
resuming.

## See also

- [`replay`](replay.md) — re-execute from a chosen step, or swap agents
- [`debug`](debug.md) — inspect why a run failed before resuming
