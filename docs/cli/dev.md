# binex dev

## Synopsis

```
binex dev [OPTIONS]
```

## Description

Start the local development environment using Docker Compose. Brings up all Binex services, waits for health checks, and reports readiness. In foreground mode (default), Ctrl+C stops all services. In detached mode (`--detach`), services run in the background.

Services started:

| Service | Port |
|---|---|
| Ollama | 11434 |
| LiteLLM Proxy | 4000 |
| Registry | 8000 |
| Planner Agent | 8001 |
| Researcher Agent | 8002 |
| Validator Agent | 8003 |
| Summarizer Agent | 8004 |

## Options

| Option | Type | Description |
|---|---|---|
| `--detach` | flag | Run services in the background |

## Example

```bash
# Start in foreground (Ctrl+C to stop)
binex dev

# Start in background
binex dev --detach
```

## Output

```
Starting Binex local development environment...
Using compose file: /path/to/docker/docker-compose.yml

Waiting for services to be healthy...
  ✓ Ollama is healthy
  ✓ LiteLLM Proxy is healthy
  ✓ Registry is healthy
  ✓ Planner Agent is healthy
  ✓ Researcher Agent is healthy
  ✓ Validator Agent is healthy
  ✓ Summarizer Agent is healthy

✓ All services are running. Use 'binex doctor' to verify.
```

## See Also

- [binex doctor](doctor.md) -- verify service health
- [binex run](run.md) -- execute workflows against running services
