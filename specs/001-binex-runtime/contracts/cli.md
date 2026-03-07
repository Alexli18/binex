# CLI Contract: Binex

## Command Structure

```
binex <command> [subcommand] [args] [options]
```

All commands output human-readable text by default. JSON output available via `--json` flag where applicable.

## Commands

### binex run

Execute a workflow.

```
binex run <workflow-file> [--var key=value ...] [--json]
```

| Arg/Option | Required | Description |
|------------|----------|-------------|
| workflow-file | yes | Path to YAML/JSON workflow definition |
| --var key=value | no | Variable substitutions for workflow inputs |
| --json | no | Output results as JSON |

**Exit codes**: 0 = success, 1 = workflow failed, 2 = invalid workflow

**Output**: Run ID, per-node status, final artifact summary. Streams progress during execution.

---

### binex trace

Inspect execution trace.

```
binex trace <run-id> [--json]
binex trace graph <run-id>
binex trace node <run-id> <step>
```

| Subcommand | Description |
|------------|-------------|
| (default) | Human-readable timeline of all steps |
| graph | DAG visualization (ASCII art) |
| node | Detailed view of a single step |

---

### binex replay

Replay a run from a specific step or with agent swaps.

```
binex replay <run-id> --from <step> [--json]
binex replay <run-id> --agent <node>=<agent> [--json]
binex replay <run-id> --deterministic [--json]
```

| Option | Description |
|--------|-------------|
| --from step | Re-execute from this step, reusing cached upstream artifacts |
| --agent node=agent | Swap agent binding for a specific node |
| --deterministic | Phase 2 — deterministic execution mode |

**Output**: New run ID, per-node status (cached/re-executed), final artifact summary.

---

### binex diff

Compare two runs.

```
binex diff <run-a> <run-b> [--json]
```

**Output**: Side-by-side comparison at artifact and execution metadata levels.

---

### binex artifacts

Manage and inspect artifacts.

```
binex artifacts list <run-id> [--json]
binex artifacts show <artifact-id> [--json]
binex artifacts lineage <artifact-id> [--json]
```

| Subcommand | Description |
|------------|-------------|
| list | List all artifacts for a run |
| show | Display artifact content |
| lineage | Show full provenance chain (tree view) |

---

### binex dev

Start local development environment.

```
binex dev [--detach]
```

| Option | Description |
|--------|-------------|
| --detach | Run in background |

Starts Docker Compose stack: LLM inference (Ollama + LiteLLM), 4 reference agents, registry.

---

### binex doctor

Check system health.

```
binex doctor [--json]
```

Checks: Docker, Ollama, agents reachability, registry status, store backends.

---

### binex validate

Validate a workflow definition.

```
binex validate <workflow-file> [--json]
```

Checks: YAML syntax, DAG structure (cycles, missing refs), agent availability.

---

### binex cancel

Cancel a running workflow.

```
binex cancel <run-id>
```

---

### binex scaffold

Generate agent boilerplate.

```
binex scaffold agent [--name <name>] [--dir <directory>]
```

Generates a template agent project with A2A server setup, agent card, and basic handler.
