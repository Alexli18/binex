# Design: system_prompt as file path

## Summary
Support `file://` prefix in `system_prompt` field to load prompt content from a file at YAML parse time.

## YAML syntax
```yaml
nodes:
  researcher:
    agent: llm://openai/gpt-4
    system_prompt: "file://prompts/researcher.md"
    outputs: [research]
```

## Mechanics
- Resolution happens at YAML parse time, before runtime starts.
- If `system_prompt` starts with `file://`, the suffix is treated as a file path.
- Relative paths resolve relative to the YAML file's directory.
- Absolute paths are used as-is.
- File content replaces `system_prompt` — adapters are unaware of files.

## Error handling
- File not found → `ValueError` at parse time with clear message (file path, node name).
- File not readable (permissions) → same.

## Change scope
- A resolution function called after YAML load, before `WorkflowSpec` construction, with YAML directory context.
- No changes to `TaskNode`, adapters (LLM, Human, A2A), orchestrator, or replay.
- Plain string `system_prompt` values work as before.
