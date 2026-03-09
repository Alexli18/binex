# binex scaffold

## Synopsis

```
binex scaffold agent [OPTIONS]
```

## Description

Generate template projects for Binex agents. Currently supports the `agent` subcommand, which creates a ready-to-run A2A agent project with a FastAPI server, agent handler, agent card, and dependency file.

Generated files:

| File | Purpose |
|---|---|
| `__init__.py` | Python package marker (empty) |
| `agent.py` | Agent handler class with `handle()` method |
| `agent_card.json` | A2A agent card served at `/.well-known/agent.json` |
| `server.py` | FastAPI server with `/` and `/.well-known/agent.json` routes |
| `requirements.txt` | Dependencies: `a2a-sdk`, `fastapi`, `uvicorn` |

## Options

### scaffold agent

| Option | Type | Default | Description |
|---|---|---|---|
| `--name` | `string` | `my-agent` | Agent name (used for class and directory) |
| `--dir` | `Path` | `./<name>` | Target directory (created if missing) |

## Example

```bash
# Scaffold with defaults
binex scaffold agent

# Custom name and directory
binex scaffold agent --name planner --dir ./agents/planner
```

## Output

```
Agent 'planner' scaffolded at agents/planner
```

The generated directory:

```
planner/
  __init__.py
  agent.py
  agent_card.json
  server.py
  requirements.txt
```

## See Also

- [binex validate](validate.md) -- validate workflows that reference your agent
- [binex dev](dev.md) -- run agents in the local development environment
