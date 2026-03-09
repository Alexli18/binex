# binex explore

## Synopsis

```
binex explore [RUN_ID]
```

## Description

Interactive browser for navigating runs and artifacts without copying IDs. Three-level navigation:

1. **Runs** — see recent runs with status, node counts, and relative time
2. **Artifacts** — browse artifacts for a selected run with node name, type, and content preview
3. **Detail** — view full artifact content with options to inspect lineage

Requires `rich` for styled tables and panels (falls back to plain text without it).

## Arguments

| Argument | Required | Description |
|---|---|---|
| `RUN_ID` | No | Jump directly to artifacts for this run (skips run selection) |

## Navigation

### Level 1: Run Selection

Shows the 20 most recent runs sorted by start time.

| Input | Action |
|---|---|
| `1`-`20` | Select a run to browse its artifacts |
| `q` | Quit |

### Level 2: Artifact List

Shows all artifacts for the selected run.

| Input | Action |
|---|---|
| `1`-`N` | Select an artifact to view details |
| `b` | Back to run list |
| `q` | Quit |

### Level 3: Artifact Detail

Shows full content in a rich panel with metadata.

| Input | Action |
|---|---|
| `l` | Show artifact lineage tree |
| `b` | Back to artifact list |
| `q` | Quit |

## Examples

```bash
# Browse interactively from run list
binex explore

# Jump directly to a specific run
binex explore run_d71c9a50b47e
```

### Sample Output

```
                  Recent Runs
┏━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃  # ┃ Run ID           ┃ Workflow        ┃ Status    ┃ Nodes ┃ When   ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│  1 │ run_69651bec83e5 │ simple-pipeline │ completed │  2/2  │ 1h ago │
│  2 │ run_d71c9a50b47e │ hello-world     │ completed │  2/2  │ 1h ago │
└────┴──────────────────┴─────────────────┴───────────┴───────┴────────┘
```

## See Also

- [binex run](run.md) — execute a workflow
- [binex debug](debug.md) — post-mortem inspection of a run
- [binex artifacts](artifacts.md) — non-interactive artifact management
- [binex trace](trace.md) — execution timeline
