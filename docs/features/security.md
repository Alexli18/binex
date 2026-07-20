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

### fetch_url / http_request — SSRF (patched, issue #59)

**Before:** Both tools fetched any URL the model produced, with redirects
enabled and no address filtering. On a server (Binex ships `binex gateway` and
`binex scheduler`), an LLM-controlled HTTP client could reach cloud metadata
endpoints (`169.254.169.254`), localhost admin panels, and internal services.

**After:** Before connecting, the URL's host is resolved and rejected if it maps
to a private, loopback, link-local, reserved, multicast, or unspecified address
(RFC 1918, `127.0.0.0/8`, `169.254.0.0/16`, `::1`, `fc00::/7`, `0.0.0.0`).
Redirects are followed manually and **every hop is re-validated**, so a public
URL can't `302` into the metadata service. Only `http`/`https` schemes are
allowed.

**Opt-out:** set `BINEX_ALLOW_PRIVATE_URLS=1` for legitimate local requests.

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
