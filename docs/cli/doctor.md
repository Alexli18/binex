# binex doctor

## Synopsis

```
binex doctor [OPTIONS]
```

## Description

Run health checks against all Binex components and report their status. Checks Docker availability, all development services, and the local store backend. Exits `0` if all checks pass, `1` if any critical check fails.

Health checks performed:

| Check | What it verifies |
|---|---|
| Docker binary | `docker` on PATH |
| Docker Daemon | `docker info` succeeds |
| Ollama | `localhost:11434` responds |
| LiteLLM Proxy | `localhost:4000` responds |
| Registry | `localhost:8000` responds |
| Planner Agent | `localhost:8001` responds |
| Researcher Agent | `localhost:8002` responds |
| Validator Agent | `localhost:8003` responds |
| Summarizer Agent | `localhost:8004` responds |
| Store Backend | `.binex/` directory exists |

Status icons: `✓` ok, `✗` missing/error/unreachable, `⚠` degraded/timeout, `○` not initialized.

## Options

| Option | Type | Description |
|---|---|---|
| `--json` | flag | Output as JSON |

## Example

```bash
binex doctor

binex doctor --json
```

## Output

```
Binex System Health Check

  ✓ docker: ok — /usr/local/bin/docker
  ✓ Docker Daemon: ok — running
  ✗ Ollama: unreachable — http://localhost:11434 connection refused
  ✓ LiteLLM Proxy: ok — http://localhost:4000/health
  ○ Store Backend: not initialized — .binex does not exist

⚠ Some checks failed. Run 'binex dev' to start services.
```

## See Also

- [binex dev](dev.md) -- start services that doctor checks
