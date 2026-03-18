# binex scheduler

## Synopsis

```
binex scheduler start [DIRECTORY]
binex scheduler list [DIRECTORY] [--json]
binex scheduler add <FILE>
binex scheduler remove <FILE>
```

## Description

`binex scheduler` manages cron-based workflow scheduling. It discovers workflows with a `schedule` field and executes them on a recurring basis.

The scheduler:

1. Scans a directory (recursively) for `.yaml`/`.yml` files containing a `schedule` field
2. Combines discovered workflows with manually registered files
3. Runs a foreground asyncio loop that ticks every 60 seconds
4. Executes due workflows, skips overlapping runs, and rescans the directory every 60 seconds for new workflows
5. Persists execution history and registered paths in `.binex/scheduler.json`

Press `Ctrl+C` (SIGINT) or send SIGTERM to gracefully stop the scheduler. It will wait for in-progress workflows to complete before exiting.

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | No scheduled workflows found, or clean shutdown |
| `1` | Error |

## Commands

### start

Start the scheduler in the foreground for a given directory.

```
binex scheduler start [DIRECTORY]
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `DIRECTORY` | path (directory) | `.` | Directory to scan for workflow files |

The scheduler discovers all workflows with a `schedule` field in the directory tree, merges them with any manually registered files, and begins the execution loop.

```bash
$ binex scheduler start .

Starting scheduler with 2 workflow(s):
  scheduled-report  [*/30 * * * *]  next: 2026-03-18 19:30
  daily-digest      [0 9 * * *]     next: 2026-03-19 09:00
```

### list

List all scheduled workflows discovered in a directory.

```
binex scheduler list [DIRECTORY] [--json]
```

| Argument/Option | Type | Default | Description |
|---|---|---|---|
| `DIRECTORY` | path (directory) | `.` | Directory to scan |
| `--json` | flag | off | Output as JSON |

```bash
$ binex scheduler list .

Scheduled workflows (2):

  scheduled-report
    schedule: */30 * * * *
    path:     /Users/alex/project/examples/scheduled-report.yaml
    next_run: 2026-03-18 19:30 UTC

  daily-digest
    schedule: 0 9 * * *
    path:     /Users/alex/project/workflows/daily-digest.yaml
    next_run: 2026-03-19 09:00 UTC
```

#### JSON Output

```bash
$ binex scheduler list . --json
```

```json
[
  {
    "name": "scheduled-report",
    "schedule": "*/30 * * * *",
    "path": "/Users/alex/project/examples/scheduled-report.yaml",
    "next_run": "2026-03-18T19:30:00+00:00"
  }
]
```

### add

Manually register a workflow file for scheduling. The file is added to `.binex/scheduler.json` so it's picked up even if outside the scan directory.

```
binex scheduler add <FILE>
```

| Argument | Type | Description |
|---|---|---|
| `FILE` | path (file, must exist) | Path to a workflow YAML file |

```bash
$ binex scheduler add /opt/workflows/nightly-backup.yaml

Registered: /opt/workflows/nightly-backup.yaml
```

If the file is already registered:

```bash
$ binex scheduler add /opt/workflows/nightly-backup.yaml

Already registered: /opt/workflows/nightly-backup.yaml
```

### remove

Unregister a previously registered workflow file.

```
binex scheduler remove <FILE>
```

| Argument | Type | Description |
|---|---|---|
| `FILE` | path | Path to the workflow file to unregister |

```bash
$ binex scheduler remove /opt/workflows/nightly-backup.yaml

Removed: /opt/workflows/nightly-backup.yaml
```

If the file is not registered:

```bash
$ binex scheduler remove /opt/workflows/unknown.yaml

Not registered: /opt/workflows/unknown.yaml
```

## Cron Expression Format

The `schedule` field uses standard 5-field cron syntax, validated via [croniter](https://github.com/kiorky/croniter):

```
 ┌───────── minute (0-59)
 │ ┌─────── hour (0-23)
 │ │ ┌───── day of month (1-31)
 │ │ │ ┌─── month (1-12)
 │ │ │ │ ┌─ day of week (0-6, 0 = Sunday)
 │ │ │ │ │
 * * * * *
```

### Common Expressions

| Expression | Meaning |
|---|---|
| `*/30 * * * *` | Every 30 minutes |
| `0 * * * *` | Every hour |
| `0 9 * * *` | Daily at 9:00 AM |
| `0 9 * * 1-5` | Weekdays at 9:00 AM |
| `0 0 * * 0` | Weekly on Sunday at midnight |
| `0 0 1 * *` | Monthly on the 1st at midnight |

## Workflow YAML with Schedule

Add a `schedule` field at the top level of any workflow YAML to make it schedulable:

```yaml
name: scheduled-report
description: "Periodic report generation"
schedule: "*/30 * * * *"

nodes:
  gather:
    agent: "llm://openai/gpt-4o-mini"
    system_prompt: "Gather key metrics for a status report."
    inputs:
      topic: "${user.topic}"
    outputs: [raw_data]

  summarize:
    agent: "llm://openai/gpt-4o-mini"
    system_prompt: "Summarize the data into a concise report."
    inputs:
      data: "${gather.raw_data}"
    outputs: [report]
    depends_on: [gather]
```

The workflow can still be run manually with `binex run` -- the `schedule` field is ignored unless the scheduler is active.

## State File

The scheduler persists its state in `.binex/scheduler.json`:

```json
{
  "registered": [
    "/opt/workflows/nightly-backup.yaml"
  ],
  "history": [
    {
      "workflow": "scheduled-report",
      "timestamp": "2026-03-18T19:30:00+00:00",
      "run_id": "sched-scheduled-report-1742324400",
      "status": "completed",
      "duration_s": 12.3,
      "cost": 0.0042
    }
  ]
}
```

| Field | Description |
|---|---|
| `registered` | Absolute paths of manually registered workflow files |
| `history` | Execution log (capped at 1000 entries) |

### History Entry Fields

| Field | Type | Description |
|---|---|---|
| `workflow` | string | Workflow name |
| `timestamp` | datetime | When the execution occurred |
| `run_id` | string or null | Run ID (format: `sched-{name}-{unix_timestamp}`) |
| `status` | `completed` / `failed` / `skipped` | Execution result |
| `reason` | string or null | Reason for skip (e.g., `previous_still_running`) |
| `duration_s` | float or null | Execution duration in seconds |
| `cost` | float or null | Total LLM cost for the run |

## Behavior Details

- **Overlapping runs**: If a workflow is still running when its next scheduled time arrives, the execution is skipped and recorded with status `skipped` and reason `previous_still_running`.
- **Directory rescan**: Every 60 seconds, the scheduler rescans the directory for new workflow files. Removed files are not automatically deregistered.
- **Atomic state writes**: State is persisted via tempfile + rename to avoid corruption on crash.
- **Graceful shutdown**: SIGINT/SIGTERM triggers a clean shutdown. The scheduler waits for all in-progress workflows to complete before saving state and exiting.
- **Run ID format**: `sched-{workflow_name}-{unix_timestamp}` -- these runs appear in `binex debug` and `binex cost` like any other run.

## Web UI

The scheduler is also accessible via the Web UI at `/scheduler`:

- Start/stop the scheduler from the browser
- View scheduled workflows and next run times
- Browse execution history with status, duration, and cost
- Add/remove registered workflows

Launch the Web UI with `binex ui` and navigate to the Scheduler page in the sidebar.

## Tips

- Use `binex scheduler list . --json` in CI to verify which workflows are scheduled before deploying.
- The scheduler runs in the foreground -- use a process manager (systemd, supervisord, Docker) for production deployments.
- Combine with budget tracking: set `budget` in your workflow to cap per-run costs. The scheduler records cost per execution in history.
- Workflows without a `schedule` field are ignored by the scanner.
- The state file is in `.binex/` which is gitignored by default.

## See Also

- [binex run](run.md) -- execute a workflow once
- [binex cost](cost.md) -- view cost breakdown for scheduled runs
- [binex ui](ui.md) -- web dashboard with scheduler management
