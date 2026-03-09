# Changelog

## v0.1.0

First public release.

### Features

- DAG-based workflow runtime with topological scheduling
- Artifact lineage tracking across pipeline steps
- Replayable workflows with agent swap support
- Run diffing for side-by-side comparison
- CLI interface: run, debug, trace, replay, diff, artifacts, explore, scaffold, validate, doctor
- Agent adapters: LLM (via LiteLLM), local Python, A2A protocol, human-in-the-loop
- Human approval gates with conditional branching
- 9 LLM providers out of the box (OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Groq, Mistral, DeepSeek, Together)
- Rich colored output (optional)
- SQLite execution store + filesystem artifact store
- Interactive project initialization wizard
- DSL shorthand for workflow generation
- MkDocs documentation site
