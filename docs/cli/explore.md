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

Shows the 20 most recent runs sorted by start time (newest first). Each row displays:

- **#** — row number for selection
- **Run ID** — first 16 characters of the full run ID
- **Workflow** — workflow name from the YAML
- **Status** — `completed` (green), `FAILED` (red), `running` (yellow)
- **Nodes** — completed/total node count
- **When** — relative time (e.g., `3m ago`, `2h ago`, `1d ago`)

| Input | Action |
|---|---|
| `1`-`20` | Select a run to browse its artifacts |
| `q` | Quit |

**Example screen (with `rich` installed):**

```
                  Recent Runs
┏━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃  # ┃ Run ID           ┃ Workflow                ┃ Status    ┃ Nodes ┃ When   ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│  1 │ run_69651bec83e5 │ research                │ completed │  4/4  │ 3m ago │
│  2 │ run_d71c9a50b47e │ simple-pipeline         │ FAILED    │  1/2  │ 1h ago │
│  3 │ run_a3f8c21e0094 │ hello-world             │ completed │  2/2  │ 2h ago │
│  4 │ run_55bc02ef1177 │ multi-provider          │ running   │  2/3  │ 5h ago │
│  5 │ run_ee1042ca6b5f │ human-approval          │ completed │  3/3  │ 1d ago │
└────┴──────────────────┴─────────────────────────┴───────────┴───────┴────────┘

  Select run (or q to quit) [1]:
```

**Fallback output (without `rich`):**

```
  Recent runs:

    1)  run_69651bec83e5   research                  completed    3m ago
    2)  run_d71c9a50b47e   simple-pipeline           FAILED       1h ago
    3)  run_a3f8c21e0094   hello-world               completed    2h ago

  Select run (or q to quit) [1]:
```

### Level 2: Artifact List

Shows all artifacts for the selected run. Each row displays the producing node, artifact type, and a truncated content preview (up to 60 characters).

| Input | Action |
|---|---|
| `1`-`N` | Select an artifact to view details |
| `b` | Back to run list |
| `q` | Quit |

**Example screen:**

```
           Artifacts — run_69651bec83e5
┏━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  # ┃ Node             ┃ Type      ┃ Preview                                     ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│  1 │ planner          │ text      │ Research plan: 1. Gather sources 2. Anal... │
│  2 │ researcher1      │ text      │ Found 15 relevant papers on distributed ... │
│  3 │ researcher2      │ text      │ Market analysis shows 23% growth in Q4 2... │
│  4 │ summarizer       │ text      │ Combined findings indicate strong potenti... │
└────┴──────────────────┴───────────┴─────────────────────────────────────────────┘

  Select artifact (or b=back, q=quit) [1]:
```

### Level 3: Artifact Detail

Shows full artifact content rendered in a rich panel with metadata header. The metadata line displays the producing node, artifact type, and status with color coding.

| Input | Action |
|---|---|
| `l` | Show artifact lineage tree |
| `b` | Back to artifact list |
| `q` | Quit |

**Example screen:**

```
Node: summarizer  Type: text  Status: completed

╭─────────────────── summarizer / text ────────────────────╮
│                                                          │
│  Combined findings indicate strong potential for growth   │
│  in the distributed systems market. Key drivers include   │
│  cloud adoption (23% YoY) and edge computing demand.     │
│                                                          │
│  Recommendations:                                        │
│  1. Focus on hybrid architectures                        │
│  2. Invest in developer tooling                          │
│  3. Target mid-market enterprises                        │
│                                                          │
│        id: art_7f2e1a3b9c04d8e6f510273849ab6cde          │
╰──────────────────────────────────────────────────────────╯

  [l] lineage  [b] back  [q] quit
  Action [b]:
```

**Lineage tree (after pressing `l`):**

```
╭──────────────── Artifact Lineage ─────────────────╮
│                                                    │
│  summarizer (art_7f2e1a3b...) text                │
│  ├── researcher1 (art_3c8d4e5f...) text           │
│  │   └── planner (art_a1b2c3d4...) text           │
│  └── researcher2 (art_9e0f1a2b...) text           │
│      └── planner (art_a1b2c3d4...) text           │
│                                                    │
╰────────────────────────────────────────────────────╯
```

## Examples

```bash
# Browse interactively from run list
binex explore

# Jump directly to a specific run (skips Level 1)
binex explore run_d71c9a50b47e
```

## Tips for Exploring Large Runs

- **Jump directly to a run** if you know the ID — `binex explore <run_id>` skips the run selection screen entirely.
- **Use `binex debug` for programmatic access** — `explore` is designed for interactive browsing; for scripting or filtering by node/error, use `binex debug <run_id>` with `--node`, `--errors`, or `--json` flags.
- **Install `rich` for readability** — the plain-text fallback works but rich tables and panels make it much easier to scan through many artifacts. Install with `pip install rich`.
- **Lineage is most useful for multi-stage workflows** — press `l` on a final artifact to trace how data flowed through all upstream nodes.
- The run list shows a **maximum of 20 recent runs**. For older runs, use `binex debug <run_id>` with the full run ID.

## See Also

- [binex run](run.md) — execute a workflow
- [binex debug](debug.md) — post-mortem inspection of a run
- [binex artifacts](artifacts.md) — non-interactive artifact management
- [binex trace](trace.md) — execution timeline
