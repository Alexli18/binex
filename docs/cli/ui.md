# binex ui

## Synopsis

```
binex ui [OPTIONS]
```

## Description

`binex ui` launches the Binex web dashboard in your browser. The dashboard provides:

- **Runs Dashboard** — view, filter, and search all workflow runs
- **Workflow Editor** — create and edit workflow YAML with live validation
  - **Tool Picker** — add built-in tools, MCP server tools, or custom Python tools to LLM nodes
  - **Collapsible sections** — Model, Prompt, Tools, Advanced for each LLM node
  - **Workflow Settings** — configure MCP servers (stdio/HTTP) and cron schedules
- **Scaffold** — generate workflows from DSL patterns or templates
- **Run Detail** — inspect nodes, artifacts, costs, and execution timeline
- **Compare & Bisect** — diff two runs or find where they diverge
- **Live View** — watch a running workflow in real time with SSE updates
- **Scheduler** — manage cron-based workflow scheduling
- **Cost Dashboard** — cost trends, breakdowns, and budget status

The server reads data from the same `.binex/` store used by the CLI.

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `8420` | Port to serve on |
| `--host` | `127.0.0.1` | Host to bind to |
| `--dev` | off | Dev mode — proxy frontend requests to Vite dev server |
| `--no-browser` | off | Don't open the browser automatically |

## Examples

```bash
# Launch with default settings (opens browser at http://127.0.0.1:8420)
binex ui

# Use a custom port
binex ui --port 9000

# Headless mode (CI, remote server)
binex ui --host 0.0.0.0 --no-browser

# Development mode (requires `cd ui && npm run dev` in another terminal)
binex ui --dev
```

## Troubleshooting

**Port already in use:**

```bash
# Find what's using the port
lsof -i :8420
# Use a different port
binex ui --port 8421
```

**No runs showing up:**
Make sure you've run workflows with `binex run` first. The UI reads from `.binex/` in the current directory.

**Blank page after launch:**
If the pre-built frontend assets are missing, rebuild them:
```bash
./scripts/build-ui.sh
```
