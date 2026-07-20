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
- **Executable allowlist (issue #58):** even with `shell=False`, the tool would
  still run *any* binary the model named (`rm`, `curl`, `python -c ...`). It now
  runs only a conservative allowlist by default — `ls`, `cat`, `head`, `tail`,
  `grep`, `wc`, `echo`, `pwd`, `find`, `sort`, `uniq`, `cut`, `tr`, `date`,
  `basename`, `dirname`, `stat`, `file`, `which`. Anything else is blocked with a
  clear message. An absolute path (`/usr/bin/curl`) can't bypass it — the check
  is on the basename.

**Widening the policy (opt-in, explicit):**
- `BINEX_SHELL_ALLOW="python3,git"` — add specific executables to the allowlist.
- `BINEX_SHELL_ALLOW_ALL=1` — disable the allowlist entirely (not recommended;
  restores arbitrary command execution).

**Follow-ups (tracked in #58):** per-workflow `tools_policy`, an optional
`human://approve` gate showing the exact command before it runs, and sandboxed
execution (container / restricted user).

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
