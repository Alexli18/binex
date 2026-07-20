# Security

## Built-in Tools Security Model

Binex built-in tools run with the permissions of the orchestrator process. Two tools had critical vulnerabilities that were patched:

### shell_command — Command Injection (CRITICAL, patched)

**Before:** Used `subprocess.run(cmd, shell=True)` — any agent could inject arbitrary shell commands.

**After:** Uses `subprocess.run(shlex.split(cmd), shell=False)`. The command is parsed into a safe argument list. Shell metacharacters are no longer interpreted.

**Mitigations:**
- 30-second timeout on all shell commands
- Output truncated to 10KB
- No shell expansion (`|`, `&&`, `;`, backticks have no effect)

### Scaffolded agent server — network exposure (patched, issue #61)

**Before:** `binex scaffold agent` generated a `server.py` that ran
`uvicorn.run(app, host="0.0.0.0", ...)` — exposing the new agent to the whole
local network, with no auth, the moment it was started.

**After:** the generated server binds to `127.0.0.1` by default and accepts a
`--host` flag (mirroring `binex ui`). Exposing it on the network is now an
explicit `--host 0.0.0.0` decision.

### calculator — Arbitrary Code Execution (CRITICAL, patched)

**Before:** Used raw `eval(expression)` — any agent could execute arbitrary Python code.

**After:** Uses AST whitelist validation before eval:
1. Parse expression with `ast.parse(expression, mode="eval")`
2. Walk AST tree, verify every node is in allowed set
3. Only literals, math operators, comparisons, and whitelisted names (math functions + abs/round/min/max) are permitted
4. `__builtins__` is set to empty dict

**Allowed:** `2 + 2`, `math.sqrt(16)`, `max(1, 2, 3)`, `3.14 * r**2`
**Blocked:** `__import__('os').system('rm -rf /')`, `open('/etc/passwd').read()`, any attribute access on non-math objects

### Other Tools

| Tool | Risk | Mitigation |
|------|------|------------|
| read_file | Path traversal | Resolved paths, no symlink following |
| write_file | Arbitrary write | Resolved paths, no symlink following |
| shell_command | Command injection | shell=False + shlex.split |
| calculator | Code execution | AST whitelist |
| http_request | SSRF | No mitigation (by design — agents need HTTP) |

## Recommendations

- Run binex in a sandboxed environment when using untrusted agents
- Review workflow definitions before execution
- Monitor shell_command usage via trace logs

## See Also
- [Tools & MCP](tools-mcp.md)
