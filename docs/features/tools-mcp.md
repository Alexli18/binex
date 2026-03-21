# Tools & MCP Integration

Binex supports tool calling in LLM-powered workflow nodes. Tools give agents the ability to perform actions — run calculations, fetch URLs, read files, execute shell commands, or call external services via the Model Context Protocol (MCP).

Tools are declared per-node in workflow YAML and resolved at execution time. The LLM adapter converts tool definitions to OpenAI-compatible function schemas and handles tool call responses automatically.

## Tool URI Schemes

Binex uses URI schemes to identify tool sources:

| Scheme | Format | Description |
|---|---|---|
| `builtin://` | `builtin://calculator` | One of 10 built-in tools shipped with Binex |
| `python://` | `python://mymodule.my_func` | User-defined Python function (loaded from workflow directory) |
| `mcp://` | `mcp://server_name` | All tools from an MCP server declared in `mcp_servers:` |

## Adding Tools to Workflow Nodes

Add a `tools:` list to any `llm://` node:

```yaml
name: tool-demo
nodes:
  researcher:
    agent: "llm://gpt-4o"
    system_prompt: "Research the topic and provide a summary with calculations."
    tools:
      - "builtin://fetch_url"
      - "builtin://calculator"
    outputs: [summary]
```

You can mix URI schemes in a single node:

```yaml
tools:
  - "builtin://read_file"
  - "python://helpers.extract_data"
  - "mcp://my_server"
```

## Built-in Tools

All 10 built-in tools are available via `builtin://name`. They are registered at import time and require no additional configuration.

### calculator

Evaluate a mathematical expression safely. Supports `math` module functions (`sin`, `cos`, `sqrt`, `log`, etc.), `abs`, `round`, `min`, `max`.

- **Parameters**: `expression` (string, required)
- **Example**: `"sqrt(144) + 2 * pi"` returns `"15.283185307179586"`
- **Safety**: Uses restricted `eval` with `{"__builtins__": {}}` — only math functions are exposed.

### dice_roll

Roll dice using D&D notation (`NdM` or `NdM+K`).

- **Parameters**: `notation` (string, required)
- **Example**: `"2d6+3"` returns `"2d6+3: [4, 2]+3 = 9"`
- **Limits**: 1-100 dice, 2-1000 sides.

### fetch_url

Fetch contents of a URL via HTTP GET (async).

- **Parameters**: `url` (string, required)
- **Limits**: 30s timeout, response truncated at 50KB. Follows redirects.

### http_request

Make an HTTP request with a configurable method (async).

- **Parameters**: `url` (string, required), `method` (string, default `"GET"`), `body` (string, default `""`)
- **Methods**: GET, POST, PUT, DELETE, PATCH.
- **Limits**: 30s timeout, response truncated at 50KB.

### web_search

Search the web using DuckDuckGo and return results.

- **Parameters**: `query` (string, required)
- **Limits**: 15s timeout, response truncated at 50KB.

### read_file

Read file contents from the workflow working directory.

- **Parameters**: `path` (string, required)
- **Restrictions**: Relative paths only. Rejects `..` and absolute paths. Path must resolve within the current working directory.

### write_file

Write content to a file in the workflow working directory.

- **Parameters**: `path` (string, required), `content` (string, required)
- **Restrictions**: Relative paths only. Rejects `..` and absolute paths. Maximum file size 10MB. Creates parent directories automatically.

### shell_command

Execute a shell command with safety constraints.

- **Parameters**: `command` (string, required)
- **Restrictions**: 30-second timeout. Output truncated at 10KB. Runs via `subprocess.run(shell=True)` in the current working directory.

### json_parse

Parse a JSON string and optionally extract specific fields.

- **Parameters**: `json_string` (string, required), `fields` (string, default `""` — comma-separated field names)
- **Example**: `json_parse('{"a": 1, "b": 2}', "a")` returns `{"a": 1}`

### random_choice

Pick a random item from a comma-separated list.

- **Parameters**: `options` (string, required)
- **Example**: `"red, green, blue"` returns one of the three.

## Custom Python Tools

Define a tool as a Python function and reference it via `python://module.function`:

```python
# tools.py (in your workflow directory)
from binex.tools import tool

@tool(description="Convert temperature from Celsius to Fahrenheit")
def celsius_to_fahrenheit(celsius: float) -> str:
    return str(celsius * 9 / 5 + 32)
```

```yaml
nodes:
  converter:
    agent: "llm://gpt-4o"
    tools:
      - "python://tools.celsius_to_fahrenheit"
    outputs: [result]
```

The `@tool` decorator is optional but recommended — it lets you set a custom `name`, `description`, and `parameter_descriptions`. Without it, Binex infers the schema from the function signature, type hints, and docstring.

```python
@tool(
    name="temp_convert",
    description="Convert Celsius to Fahrenheit",
    parameter_descriptions={"celsius": "Temperature in degrees Celsius"},
)
def celsius_to_fahrenheit(celsius: float) -> str:
    return str(celsius * 9 / 5 + 32)
```

Async functions are supported — Binex detects `async def` and awaits them automatically.

## MCP Server Configuration

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) lets Binex connect to external tool servers. Declare MCP servers at the workflow level under `mcp_servers:`, then reference them in node `tools:` via `mcp://server_name`.

### Stdio Transport

For MCP servers that run as a subprocess:

```yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/workspace"]

nodes:
  file_worker:
    agent: "llm://gpt-4o"
    tools:
      - "mcp://filesystem"
    outputs: [result]
```

### HTTP/SSE Transport

For MCP servers accessible via HTTP:

```yaml
mcp_servers:
  remote_tools:
    url: "http://localhost:3000/sse"

nodes:
  worker:
    agent: "llm://gpt-4o"
    tools:
      - "mcp://remote_tools"
    outputs: [result]
```

### `McpServerConfig` Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `command` | string or null | `null` | Executable command for stdio transport (e.g. `"npx"`, `"python"`) |
| `args` | list of strings | `[]` | Arguments passed to the command |
| `env` | dict | `{}` | Environment variables for the subprocess |
| `url` | string or null | `null` | URL for HTTP/SSE transport |

Exactly one of `command` or `url` must be provided — not both.

### How MCP Tools Are Resolved

MCP tools use lazy resolution:

1. At workflow load time, `mcp://server_name` creates a placeholder `ToolDefinition` with `_mcp_server` set.
2. At node execution time, the LLM adapter calls `McpClientManager.get_tools(server_name)` which connects to the MCP server (if not already connected) and fetches the tool list.
3. Tool names are namespaced as `{server_name}__{tool_name}` to avoid collisions between servers or with built-in tools.
4. After the workflow completes, `McpClientManager.close_all()` shuts down all connections.

Connection timeout is 30 seconds per server.

## Inline Tool Definitions

You can define tools inline in YAML without any Python code. These become schema-only tools — the LLM sees them and can call them, but they have no executable handler (useful for prompt engineering or when tool execution is handled externally):

```yaml
tools:
  - name: "lookup_user"
    description: "Look up user information by ID"
    parameters:
      user_id:
        type: string
        description: "The user ID to look up"
```

## Security Notes

- **read_file / write_file**: Reject path traversal (`..`) and absolute paths. All paths must resolve within the current working directory.
- **write_file**: Maximum content size is 10MB.
- **shell_command**: Runs with `shell=True` (intentional for workflow automation). Has a 30-second timeout and 10KB output limit.
- **calculator**: Uses restricted `eval` with empty `__builtins__` — only math functions are exposed.
- **fetch_url / http_request / web_search**: No SSRF protection (by design, same as A2A adapter).
- **MCP servers**: Binex does not sandbox MCP server processes. Only connect to trusted servers.

## Full Example

A workflow that uses all three tool sources:

```yaml
name: research-with-tools
description: "Research a topic using built-in, custom, and MCP tools"

mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "${user.github_token}"

nodes:
  researcher:
    agent: "llm://claude-sonnet-4-20250514"
    system_prompt: |
      Research the given topic. Use web search for general info,
      fetch specific URLs for details, and check GitHub for code examples.
    tools:
      - "builtin://web_search"
      - "builtin://fetch_url"
      - "builtin://json_parse"
      - "mcp://github"
    outputs: [research]

  writer:
    agent: "llm://gpt-4o"
    depends_on: [researcher]
    inputs:
      research: "${researcher.research}"
    system_prompt: |
      Write a report based on the research. Save it to report.md.
    tools:
      - "builtin://write_file"
      - "python://helpers.format_markdown"
    outputs: [report]
```

Run it:

```bash
binex run research-with-tools.yaml --var github_token=ghp_xxx
```
