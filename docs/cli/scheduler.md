# binex scheduler

## Synopsis

```
binex scheduler start [DIRECTORY]
binex scheduler list  [DIRECTORY] [--json]
binex scheduler add   FILE
binex scheduler remove FILE
```

## Description

`binex scheduler` runs workflows on a cron schedule. Any workflow YAML file that contains a `schedule` field is eligible for automatic recurring execution. The scheduler runs in the foreground, polling for due workflows and launching them via the standard orchestrator.

## Adding a Schedule to a Workflow

Add a `schedule` field with a standard 5-field cron expression to any workflow file:

```yaml
name: daily-report
schedule: "0 9 * * *"   # every day at 09:00 UTC

nodes:
  gather:
    agent: llm://openai/gpt-4o
    inputs: { topic: "${user.topic}" }
    outputs: [report]
```

The cron expression is validated with [croniter](https://github.com/kiorber/croniter). Files with invalid cron syntax are skipped with a warning.

### Cron Expression Reference

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sun=0)
│ │ │ │ │
* * * * *
```

| Expression | Meaning |
|---|---|
| `*/5 * * * *` | Every 5 minutes |
| `0 * * * *` | Every hour |
| `0 9 * * *` | Daily at 09:00 UTC |
| `0 9 * * 1-5` | Weekdays at 09:00 UTC |
| `0 0 1 * *` | First day of each month at midnight |

## CLI Commands

### `binex scheduler start [DIRECTORY]`

Start the scheduler in the foreground. The scheduler scans the given directory (default `.`) for workflow files containing a `schedule` field, then enters a loop that checks and executes due workflows.

```bash
$ binex scheduler start .

Starting scheduler with 2 workflow(s):
  daily-report  [0 9 * * *]  next: 2026-03-23 09:00
  hourly-check  [0 * * * *]  next: 2026-03-22 15:00
```

Stop with `Ctrl+C` (SIGINT). The scheduler waits for any in-progress workflows to finish before exiting, then saves state.

### `binex scheduler list [DIRECTORY]`

List all discovered scheduled workflows without starting the scheduler.

```bash
$ binex scheduler list .

Scheduled workflows (2):

  daily-report
    schedule: 0 9 * * *
    path:     /home/user/project/daily-report.yaml
    next_run: 2026-03-23 09:00 UTC

  hourly-check
    schedule: 0 * * * *
    path:     /home/user/project/hourly-check.yaml
    next_run: 2026-03-22 15:00 UTC
```

#### JSON Output

```bash
$ binex scheduler list . --json
```

```json
[
  {
    "name": "daily-report",
    "schedule": "0 9 * * *",
    "path": "/home/user/project/daily-report.yaml",
    "next_run": "2026-03-23T09:00:00+00:00"
  }
]
```

### `binex scheduler add FILE`

Register a workflow file for scheduling. Registered files are included even when the scheduler scans a different directory.

```bash
$ binex scheduler add /path/to/other-workflow.yaml
Registered: /path/to/other-workflow.yaml
```

### `binex scheduler remove FILE`

Unregister a previously registered workflow file.

```bash
$ binex scheduler remove /path/to/other-workflow.yaml
Removed: /path/to/other-workflow.yaml
```

## How It Works

The scheduler engine is an asyncio loop that performs three activities:

1. **Tick** — checks each workflow's `next_run` timestamp against the current time. Due workflows are launched as background asyncio tasks using the standard `Orchestrator`. After launching, `next_run` advances to the next cron occurrence.

2. **Skip overlapping** — if a workflow is due but its previous run is still in progress, the execution is skipped and recorded as `skipped` with reason `previous_still_running`. This prevents unbounded parallelism for slow workflows.

3. **Rescan directory** — every 60 seconds, the engine re-scans the target directory for new workflow files. Newly discovered files with a `schedule` field are added to the active set automatically.

### Run IDs

Scheduled runs use the format `sched-{workflow_name}-{unix_timestamp}` (e.g., `sched-daily-report-1711108800`). These IDs appear in `binex debug`, `binex cost`, and the Web UI dashboard.

### Graceful Shutdown

On SIGINT or SIGTERM, the scheduler:

1. Stops scheduling new workflows
2. Waits for all in-progress runs to complete
3. Saves state to disk

## State File

The scheduler persists its state in `.binex/scheduler.json`. This file contains:

- **`registered`** — list of absolute paths added via `binex scheduler add`
- **`history`** — execution log (capped at 1000 entries)

Each history entry records:

| Field | Description |
|---|---|
| `workflow` | Workflow name |
| `timestamp` | ISO 8601 timestamp |
| `run_id` | Run ID (null for skipped entries) |
| `status` | `completed`, `failed`, or `skipped` |
| `reason` | Skip reason (e.g., `previous_still_running`) |
| `duration_s` | Execution duration in seconds |
| `cost` | Total cost in USD (null if unavailable) |

State is written atomically (tempfile + rename) to prevent corruption on crash.

## Web UI

The scheduler is also available from the Web UI at the `/scheduler` route (accessible via **System > Scheduler** in the sidebar). Launch it with:

```bash
binex ui
```

The Scheduler page provides:

- **KPI cards** — running status, workflow count, today's cost
- **Start / Stop** buttons — starts/stops the scheduler subprocess from the browser
- **History table** — recent executions with status, duration, and cost
- **Auto-refresh** — page refreshes every 10 seconds

### API Endpoints

All endpoints are under `/api/v1/scheduler/`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/status` | Running state, PID, discovered workflows |
| `GET` | `/history?limit=50` | Execution history (newest first) |
| `POST` | `/start` | Start scheduler subprocess |
| `POST` | `/stop` | Stop scheduler (SIGINT, 30s timeout) |
| `POST` | `/add` | Register a workflow path |
| `POST` | `/remove` | Unregister a workflow path |

## Examples

### Run a workflow every 5 minutes

```yaml
name: health-check
schedule: "*/5 * * * *"

nodes:
  check:
    agent: llm://openai/gpt-4o-mini
    inputs: { task: "Check system status and summarize" }
    outputs: [status]
```

```bash
binex scheduler start .
```

### Register a workflow from another directory

```bash
# Register a file outside the scan directory
binex scheduler add ~/workflows/nightly-backup.yaml

# Start scheduler — picks up both local and registered workflows
binex scheduler start .
```

### Check what will run without starting

```bash
binex scheduler list . --json | python -m json.tool
```

### Inspect a scheduled run after execution

```bash
# Find the run ID in scheduler history or dashboard
binex debug sched-health-check-1711108800
binex cost show sched-health-check-1711108800
```

## See Also

- [binex run](run.md) — execute a workflow manually
- [binex cost](cost.md) — inspect execution costs
- [binex ui](ui.md) — launch the web dashboard
- [Workflow Format](../workflows/format.md) — full YAML reference
