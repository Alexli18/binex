# Tools & MCP

## Overview

Binex agents can use **tools** — callable functions that extend LLM capabilities beyond text generation. Tools let agents perform calculations, make HTTP requests, read/write files, execute shell commands, and interact with external services via MCP (Model Context Protocol).

Tools are specified per-node in the `tools` field using URI schemes:

```yaml
nodes:
  researcher:
    agent: "llm://openai/gpt-4o"
    system_prompt: "Research the topic using web search and calculations."
    tools:
      - "builtin://web_search"
      - "builtin://calculator"
      - "mcp://my-server"
      - "python://my_tools.custom_tool"
    inputs:
      topic: "${user.topic}"
    outputs: [report]
```

## URI Schemes

| Scheme | Description | Example |
|---|---|---|
| `builtin://` | 10 built-in tools bundled with Binex | `builtin://calculator` |
| `mcp://` | Tools from an MCP server (requires `mcp_servers` config) | `mcp://my-server` |
| `python://` | User-defined Python function | `python://my_tools.analyze` |

## Built-in Tools

Binex ships with 10 built-in tools, available immediately via `builtin://name`.

### calculator

Evaluate mathematical expressions safely. Supports standard math functions (`sin`, `cos`, `sqrt`, `log`, `pi`, `e`, etc.) plus `abs`, `round`, `min`, `max`.

```yaml
tools: ["builtin://calculator"]
```

Uses restricted `eval` with `{"__builtins__": {}}` — only math functions are exposed.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `expression` | string | yes | Mathematical expression to evaluate |

**Example:** `"sqrt(144) + pi"` → `"15.141592653589793"`

### dice_roll

Roll dice using D&D notation (NdM+K).

```yaml
tools: ["builtin://dice_roll"]
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `notation` | string | yes | Dice notation (e.g., `2d6+3`, `1d20`, `4d6`) |

**Limits:** 1-100 dice, 2-1000 sides.

**Example:** `"2d6+3"` → `"2d6+3: [4, 5]+3 = 12"`

### fetch_url

Fetch contents of a URL via HTTP GET. Async, follows redirects, 30s timeout, output truncated at 50KB.

```yaml
tools: ["builtin://fetch_url"]
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `url` | string | yes | URL to fetch |

### http_request

Make an HTTP request with any method (GET/POST/PUT/DELETE/PATCH). Async, 30s timeout, output truncated at 50KB.

```yaml
tools: ["builtin://http_request"]
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `url` | string | yes | Target URL |
| `method` | string | no | HTTP method (default: `GET`) |
| `body` | string | no | Request body (for POST/PUT/PATCH, sent as `application/json`) |

**Example response:** `"HTTP 200\n{\"status\": \"ok\"}"`

### web_search

Search the web using DuckDuckGo and return HTML results. Async, 15s timeout.

```yaml
tools: ["builtin://web_search"]
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | Search query |

### read_file

Read file contents from the workflow working directory. Only relative paths allowed.

```yaml
tools: ["builtin://read_file"]
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `path` | string | yes | Relative file path |

**Security:** Rejects `..` (path traversal) and absolute paths. Validates that resolved path stays within the working directory.

### write_file

Write content to a file in the workflow working directory. Max 10MB.

```yaml
tools: ["builtin://write_file"]
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `path` | string | yes | Relative file path |
| `content` | string | yes | Content to write |

**Security:** Same restrictions as `read_file` — no `..`, no absolute paths, stays within working directory.

### shell_command

Execute a shell command with safety constraints.

```yaml
tools: ["builtin://shell_command"]
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `command` | string | yes | Shell command to execute |

**Limits:** 30-second timeout, output truncated at 10KB. Uses `subprocess.run(shell=True)`.

### json_parse

Parse a JSON string and optionally extract specific fields.

```yaml
tools: ["builtin://json_parse"]
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `json_string` | string | yes | JSON string to parse |
| `fields` | string | no | Comma-separated field names to extract (empty = return all) |

**Example:** `json_parse('{"a": 1, "b": 2}', fields="a")` → `'{"a": 1}'`

### random_choice

Pick a random item from a comma-separated list.

```yaml
tools: ["builtin://random_choice"]
```

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `options` | string | yes | Comma-separated list of options |

**Example:** `"red, green, blue"` → `"green"`

## User-Defined Tools (python://)

Create custom tools by writing a Python function and decorating it with `@tool`:

```python
# my_tools.py
from binex.tools import tool

@tool(description="Look up a user by email")
async def user_lookup(email: str) -> str:
    # your logic here
    return f"User: {email}"
```

Reference it in the workflow:

```yaml
nodes:
  lookup:
    agent: "llm://openai/gpt-4o"
    tools: ["python://my_tools.user_lookup"]
    outputs: [result]
```

The `python://` loader adds the workflow directory to `sys.path` so project-local modules can be imported.

## MCP Server Integration

[Model Context Protocol](https://modelcontextprotocol.io/) (MCP) lets Binex connect to external tool servers. Configure MCP servers at the workflow level, then reference them per-node.

### Configuration

Add `mcp_servers` to the top level of your workflow YAML:

```yaml
mcp_servers:
  my-server:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/workspace"]

  remote-server:
    url: "http://localhost:3001/sse"
```

Each server uses one of two transports:

| Transport | Fields | Description |
|---|---|---|
| **stdio** | `command`, `args`, `env` | Starts a subprocess and communicates via stdin/stdout |
| **HTTP/SSE** | `url` | Connects to a running server via Server-Sent Events |

You must specify exactly one of `command` or `url` (not both).

### McpServerConfig Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `command` | string | stdio | Command to start the MCP server process |
| `args` | list[string] | no | Command arguments (default: `[]`) |
| `env` | dict[string, string] | no | Environment variables for the subprocess (default: `{}`) |
| `url` | string | HTTP/SSE | URL of the running MCP server |

### Using MCP Tools

Reference MCP servers per-node with `mcp://server-name`:

```yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]

nodes:
  file_processor:
    agent: "llm://openai/gpt-4o"
    system_prompt: "Process files in the data directory."
    tools:
      - "mcp://filesystem"
      - "builtin://calculator"
    outputs: [result]
```

### How MCP Works at Runtime

1. `mcp://` tools are resolved as **placeholders** with a `_mcp_server` attribute during workflow loading
2. `McpClientManager` is created during adapter registration and stored on the dispatcher
3. At execution time, `LLMAdapter._expand_mcp_tools()` connects to the MCP server and fetches actual tool definitions
4. Tool names are **namespaced** as `{server_name}__{tool_name}` to prevent collisions
5. After workflow execution, `McpClientManager.close_all()` closes all connections

### Mixing Tool Types

A single node can use tools from multiple sources:

```yaml
nodes:
  analyst:
    agent: "llm://openai/gpt-4o"
    tools:
      - "builtin://calculator"         # built-in
      - "builtin://web_search"         # built-in
      - "mcp://database"              # MCP server
      - "python://my_tools.analyze"    # custom Python
    outputs: [analysis]
```

## Complete Example

```yaml
name: research-with-tools
description: "Research pipeline using built-in and MCP tools"

mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "./data"]

nodes:
  search:
    agent: "llm://openai/gpt-4o"
    system_prompt: "Search the web for the given topic and summarize findings."
    tools:
      - "builtin://web_search"
      - "builtin://fetch_url"
    inputs:
      topic: "${user.topic}"
    outputs: [findings]

  analyze:
    agent: "llm://openai/gpt-4o"
    system_prompt: "Analyze the findings. Use calculator for any numeric analysis. Save results to a file."
    tools:
      - "builtin://calculator"
      - "mcp://filesystem"
    inputs:
      data: "${search.findings}"
    outputs: [analysis]
    depends_on: [search]
```

## Security Notes

- **calculator**: Uses restricted `eval` with empty `__builtins__` — only `math` functions exposed
- **read_file / write_file**: Reject `..` and absolute paths; validate resolved path stays within working directory
- **write_file**: Max file size 10MB
- **shell_command**: 30-second timeout, 10KB output limit; uses `shell=True` — intended for workflow automation, not user-facing
- **fetch_url / http_request**: No SSRF protection (same as A2A adapter) — by design for workflow flexibility
- **MCP servers**: Connections are workflow-scoped and closed after execution

## Web UI

The Editor page includes a **Tools** section for each LLM node:

- Collapsible tool picker with all 10 built-in tools
- MCP server configuration panel (stdio/HTTP transport) in the Settings panel
- Changes sync bidirectionally between the visual editor and YAML

## API

```
GET /api/v1/tools/builtins
```

Returns all 10 built-in tools with name, description, category, and parameters.

## See Also

- [Agents](agents.md) — agent types that can use tools (LLM agents)
- [Workflows](workflows.md) — how tools fit into the workflow DAG
- [Architecture > Adapters](../architecture/adapters.md) — how LLMAdapter handles tool calling
