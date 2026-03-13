# binex plugins

Manage adapter plugins for Binex workflows.

## plugins list

Show all built-in adapters and installed plugins.

```bash
binex plugins list
```

Output:

```
Built-in adapters:
  local://     LocalPythonAdapter
  llm://       LLMAdapter (litellm)
  human://     HumanApprovalAdapter / HumanInputAdapter
  a2a://       A2AAgentAdapter

Installed plugins:
  langchain:// binex (0.2.5)
  crewai://    binex (0.2.5)
  autogen://   binex (0.2.5)
```

### JSON output

```bash
binex plugins list --json
```

Returns a JSON array of installed plugin metadata (prefix, name, package, version).

## plugins check

Verify that all adapters required by a workflow are available.

```bash
binex plugins check workflow.yaml
```

Output on success (exit code 0):

```
Checking adapters for workflow.yaml...
  llm://gpt-4o           built-in
  langchain://mymod.chain binex (0.2.5)

All adapters available.
```

Output on failure (exit code 1):

```
Checking adapters for workflow.yaml...
  llm://gpt-4o           built-in
  crewai://mymod.crew    not found — pip install binex[crewai]

1 missing adapter(s). Workflow cannot run.
```

Use in CI to catch missing dependencies before deployment.
