# binex dev

## Synopsis

```
binex dev [OPTIONS]
```

## Description

Start the local development environment using Docker Compose. Brings up all Binex services, waits for health checks, and reports readiness. In foreground mode (default), Ctrl+C stops all services gracefully. In detached mode (`--detach`), services run in the background and health checks are performed automatically.

The command looks for `docker-compose.yml` in `./docker/docker-compose.yml` relative to the current directory (or the package root as a fallback).

## Prerequisites

- **Docker** must be installed and the Docker daemon must be running. Verify with:

    ```bash
    docker info
    ```

- **Docker Compose v2** (the `docker compose` subcommand) is required. The command uses `docker compose` (not the legacy `docker-compose` binary).

- **Ports must be available.** The following ports are used by Binex services:

    | Service | Port | Health Endpoint |
    |---|---|---|
    | Ollama | 11434 | `GET /api/tags` |
    | LiteLLM Proxy | 4000 | `GET /health` |
    | Registry | 8000 | `GET /health` |
    | Planner Agent | 8001 | `GET /health` |
    | Researcher Agent | 8002 | `GET /health` |
    | Validator Agent | 8003 | `GET /health` |
    | Summarizer Agent | 8004 | `GET /health` |

## Options

| Option | Type | Description |
|---|---|---|
| `--detach` | flag | Run services in the background |

## Examples

```bash
# Start in foreground (Ctrl+C to stop)
binex dev

# Start in background
binex dev --detach

# Verify everything is running after detached start
binex doctor
```

## Output

### Successful Start (Detached Mode)

```
Starting Binex local development environment...
Using compose file: /home/user/project/docker/docker-compose.yml

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

### Partial Failure (Detached Mode)

If some services fail to start within the 120-second timeout:

```
Starting Binex local development environment...
Using compose file: /home/user/project/docker/docker-compose.yml

Waiting for services to be healthy...
  ✓ Ollama is healthy
  ✗ LiteLLM Proxy failed to start within 120s
  ✓ Registry is healthy
  ✓ Planner Agent is healthy
  ✓ Researcher Agent is healthy
  ✗ Validator Agent failed to start within 120s
  ✓ Summarizer Agent is healthy

⚠ Some services failed to start. Run 'binex doctor' for details.
```

### Missing Compose File

```
Error: docker-compose.yml not found at ./docker/docker-compose.yml
```

## How Health Checks Work

In detached mode, after starting the containers, `binex dev` polls each service's health endpoint every 2 seconds for up to 120 seconds. A service is considered healthy when it returns HTTP 200. Foreground mode does not perform health checks (the output streams directly to your terminal).

## Verifying Services Are Running

After a detached start, you can verify services in several ways:

```bash
# Use binex doctor for a full health report
binex doctor

# Check Docker containers directly
docker compose -f docker/docker-compose.yml ps

# Test a specific service
curl http://localhost:4000/health
```

## Stopping Services

```bash
# If running in foreground: press Ctrl+C

# If running in detached mode:
docker compose -f docker/docker-compose.yml down
```

## Troubleshooting

### Docker Daemon Not Running

```
Error starting services:
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

**Fix:** Start Docker Desktop or the Docker daemon (`sudo systemctl start docker` on Linux).

### Port Already in Use

```
Error starting services:
Bind for 0.0.0.0:8000 failed: port is already allocated
```

**Fix:** Stop the conflicting process or change the port mapping in `docker/docker-compose.yml`. Find what is using the port:

```bash
lsof -i :8000
```

### Service Fails Health Check

If a service starts but fails health checks, inspect its logs:

```bash
docker compose -f docker/docker-compose.yml logs <service-name>

# Example: check why LiteLLM Proxy is not healthy
docker compose -f docker/docker-compose.yml logs litellm
```

### Ollama Model Not Downloaded

Ollama may be healthy but fail during workflow execution if the required model is not pulled:

```bash
# Pull a model into the running Ollama container
docker exec -it <ollama-container-id> ollama pull llama3.2
```

### Out of Memory

Large LLM models require significant RAM. If containers are being killed:

- Increase Docker memory allocation (Docker Desktop > Settings > Resources)
- Use smaller models (e.g., `ollama/llama3.2` instead of larger variants)

## See Also

- [binex doctor](doctor.md) — verify service health
- [binex run](run.md) — execute workflows against running services
