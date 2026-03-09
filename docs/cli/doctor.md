# binex doctor

## Synopsis

```
binex doctor [OPTIONS]
```

## Description

Run health checks against all Binex components and report their status. Checks Docker availability, all development services, and the local store backend. Exits `0` if all checks pass, `1` if any critical check fails.

## Health Checks

| Check | What it verifies | How |
|---|---|---|
| Docker binary | `docker` on PATH | `shutil.which("docker")` |
| Docker Daemon | Docker engine is responsive | `docker info` (10s timeout) |
| Ollama | LLM inference service | HTTP GET `localhost:11434/api/tags` |
| LiteLLM Proxy | LLM routing proxy | HTTP GET `localhost:4000/health` |
| Registry | Agent registry service | HTTP GET `localhost:8000/health` |
| Planner Agent | Planner A2A agent | HTTP GET `localhost:8001/health` |
| Researcher Agent | Researcher A2A agent | HTTP GET `localhost:8002/health` |
| Validator Agent | Validator A2A agent | HTTP GET `localhost:8003/health` |
| Summarizer Agent | Summarizer A2A agent | HTTP GET `localhost:8004/health` |
| Store Backend | Local `.binex/` data directory | Checks if directory exists on disk |

## Status Icons

| Icon | Status | Meaning |
|---|---|---|
| `✓` | `ok` | Component is healthy and working |
| `✗` | `missing` | Binary not found on PATH |
| `✗` | `error` | Component returned an error or is not running |
| `✗` | `unreachable` | HTTP connection refused (service not started) |
| `⚠` | `degraded` | Service responded with non-200 status code |
| `⚠` | `timeout` | Service did not respond within 5 seconds |
| `○` | `not initialized` | Store directory does not exist yet (created on first run) |

## Options

| Option | Type | Description |
|---|---|---|
| `--json` | flag | Output results as JSON array |

## Examples

```bash
# Standard health check
binex doctor

# JSON output (for scripting)
binex doctor --json
```

## Example Output

### All Services Running

```
Binex System Health Check

  ✓ docker: ok — /usr/local/bin/docker
  ✓ Docker Daemon: ok — running
  ✓ Ollama: ok — http://localhost:11434/api/tags
  ✓ LiteLLM Proxy: ok — http://localhost:4000/health
  ✓ Registry: ok — http://localhost:8000/health
  ✓ Planner Agent: ok — http://localhost:8001/health
  ✓ Researcher Agent: ok — http://localhost:8002/health
  ✓ Validator Agent: ok — http://localhost:8003/health
  ✓ Summarizer Agent: ok — http://localhost:8004/health
  ✓ Store Backend: ok — /home/user/project/.binex

✓ All checks passed.
```

### Mixed Results (Typical After Partial Setup)

```
Binex System Health Check

  ✓ docker: ok — /usr/local/bin/docker
  ✓ Docker Daemon: ok — running
  ✗ Ollama: unreachable — http://localhost:11434/api/tags connection refused
  ✓ LiteLLM Proxy: ok — http://localhost:4000/health
  ✓ Registry: ok — http://localhost:8000/health
  ✓ Planner Agent: ok — http://localhost:8001/health
  ✗ Researcher Agent: unreachable — http://localhost:8002/health connection refused
  ⚠ Validator Agent: timeout — http://localhost:8003/health timed out
  ✓ Summarizer Agent: ok — http://localhost:8004/health
  ○ Store Backend: not initialized — .binex does not exist (will be created on first run)

⚠ Some checks failed. Run 'binex dev' to start services.
```

### No Docker Installed

```
Binex System Health Check

  ✗ docker: missing — docker not found on PATH
  ✗ Docker Daemon: error — cannot connect
  ✗ Ollama: unreachable — http://localhost:11434/api/tags connection refused
  ✗ LiteLLM Proxy: unreachable — http://localhost:4000/health connection refused
  ✗ Registry: unreachable — http://localhost:8000/health connection refused
  ✗ Planner Agent: unreachable — http://localhost:8001/health connection refused
  ✗ Researcher Agent: unreachable — http://localhost:8002/health connection refused
  ✗ Validator Agent: unreachable — http://localhost:8003/health connection refused
  ✗ Summarizer Agent: unreachable — http://localhost:8004/health connection refused
  ○ Store Backend: not initialized — .binex does not exist (will be created on first run)

⚠ Some checks failed. Run 'binex dev' to start services.
```

### JSON Output

```json
[
  {"name": "docker", "status": "ok", "detail": "/usr/local/bin/docker"},
  {"name": "Docker Daemon", "status": "ok", "detail": "running"},
  {"name": "Ollama", "status": "unreachable", "detail": "http://localhost:11434/api/tags connection refused"},
  {"name": "LiteLLM Proxy", "status": "ok", "detail": "http://localhost:4000/health"},
  {"name": "Registry", "status": "ok", "detail": "http://localhost:8000/health"},
  {"name": "Planner Agent", "status": "ok", "detail": "http://localhost:8001/health"},
  {"name": "Researcher Agent", "status": "ok", "detail": "http://localhost:8002/health"},
  {"name": "Validator Agent", "status": "ok", "detail": "http://localhost:8003/health"},
  {"name": "Summarizer Agent", "status": "ok", "detail": "http://localhost:8004/health"},
  {"name": "Store Backend", "status": "ok", "detail": "/home/user/project/.binex"}
]
```

## What to Do When a Check Fails

| Failed Check | Action |
|---|---|
| `docker: missing` | Install Docker: [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| `Docker Daemon: error` | Start Docker Desktop or run `sudo systemctl start docker` |
| Any service `unreachable` | Run `binex dev --detach` to start all services |
| Service `degraded` (non-200) | Check service logs: `docker compose -f docker/docker-compose.yml logs <service>` |
| Service `timeout` | The service may be overloaded or starting up — wait and retry |
| Store Backend `not initialized` | This is normal before the first `binex run` — the directory is created automatically |

## Integration with Other Commands

`binex doctor` works well as a pre-flight check before other commands:

```bash
# Verify environment before running a workflow
binex doctor && binex run workflow.yaml --var query="test"

# Use in CI/CD to gate deployment
binex doctor --json | python -c "
import json, sys
checks = json.load(sys.stdin)
failed = [c for c in checks if c['status'] in ('missing', 'error', 'unreachable')]
if failed:
    for c in failed:
        print(f'FAIL: {c[\"name\"]} — {c[\"detail\"]}', file=sys.stderr)
    sys.exit(1)
print('All checks passed')
"
```

After `binex dev --detach`, the typical workflow is:

```bash
binex dev --detach    # Start services
binex doctor          # Verify everything is healthy
binex run workflow.yaml --var query="hello"  # Run your workflow
```

## See Also

- [binex dev](dev.md) — start services that doctor checks
- [binex validate](validate.md) — validate workflow files before running
