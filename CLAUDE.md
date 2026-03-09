# Binex Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-08

## Active Technologies
- Python 3.11+ + mkdocs, mkdocs-material, pymdownx (extensions bundled with mkdocs-material) (002-documentation)
- N/A (static documentation site) (002-documentation)
- Python 3.11+ + click (CLI), pydantic 2.0+ (models), rich (optional, colored output) (003-debug-command)
- Existing SqliteExecutionStore + FilesystemArtifactStore (read-only for debug) (003-debug-command)
- Python 3.11+ + click (CLI), pydantic 2.0+ (models), rich (optional output), litellm (LLM calls), pyyaml (004-cli-dx)
- Python 3.11+ + click (CLI), pyyaml (YAML generation), existing binex modules (dsl_parser, providers, adapters, orchestrator) (005-start-wizard)
- Filesystem only (generates project directory with workflow.yaml, .env, .gitignore) (005-start-wizard)
- Python 3.11+ + click (CLI), litellm (LLM calls with native tool calling support), pydantic 2.0+ (models), pyyaml (006-system-prompt-tools)
- N/A (tools are in-memory only, no persistence changes) (006-system-prompt-tools)

- Python 3.11+ + a2a-sdk, litellm, fastapi, uvicorn, httpx, pydantic 2.0+, pyyaml, click, aiosqlite, python-dotenv (001-binex-runtime)

## Project Structure

```text
src/
tests/
```

## Commands

- `python -m pytest tests/` — run all tests (870 tests)
- `ruff check src/` — lint check
- `binex hello` — zero-config demo (verifies installation)
- `binex init` — interactive project initialization (workflow/agent/full mode)
- `binex scaffold workflow "A -> B -> C"` — generate workflow YAML from DSL
- `binex run examples/simple.yaml` — quick smoke test
- `binex debug <run_id>` — post-mortem inspection (supports `--json`, `--errors`, `--node`, `--rich`)

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 006-system-prompt-tools: Added Python 3.11+ + click (CLI), litellm (LLM calls with native tool calling support), pydantic 2.0+ (models), pyyaml
- 005-start-wizard: Added Python 3.11+ + click (CLI), pyyaml (YAML generation), existing binex modules (dsl_parser, providers, adapters, orchestrator)
- 004-cli-dx: Added Python 3.11+ + click (CLI), pydantic 2.0+ (models), rich (optional output), litellm (LLM calls), pyyaml


<!-- MANUAL ADDITIONS START -->
## Architecture

- Layered deps: models → stores → adapters/graph/workflow_spec → trace → runtime → cli
- CLI commands use `_get_stores()` helper (returns sqlite + filesystem stores) — patch this in tests
- SqliteExecutionStore has lazy-init; **must call `await store.close()` in every async CLI function** (aiosqlite hangs otherwise)
- FilesystemArtifactStore.get() scans filesystem via rglob (in-memory index is empty on fresh CLI invocations)
- Workflow `${user.*}` vars resolved at load time; `${node.*}` refs are runtime artifact references
- Agent prefixes in workflow YAML: `local://`, `llm://`, `a2a://`, `human://` — each registered in `cli/run.py` and `cli/replay.py`
- `NodeSpec.when: str | None` — conditional execution (`${node.output} == value` or `!= value`), evaluated at runtime
- Scheduler `_skipped` set: skipped nodes count as resolved for dependency purposes
- `HumanApprovalAdapter`: prompts user via `click.prompt`, returns artifact with type `"decision"` and content `"approved"`/`"rejected"`
- Provider registry in `cli/providers.py`: 8 providers (ollama, openai, anthropic, gemini, groq, mistral, deepseek, together)
- DSL parser in `cli/dsl_parser.py`: `"A -> B, C -> D"` syntax with 9 predefined patterns
- `NodeSpec.config: dict` — per-node LLM params (temperature, api_base, api_key, max_tokens) forwarded to LLMAdapter
- `LLMAdapter` forwards optional kwargs to `litellm.acompletion()` only when not None
- `.env` loaded via `python-dotenv` in `cli/main.py:main()` — entry point is `binex.cli.main:main` (not `:cli`)
- A2A agent contract: `POST /execute` (receives `{task_id, skill, trace_id, artifacts}`, returns `{artifacts}`) + `GET /health`
- Data persisted in `.binex/` (gitignored): `.binex/binex.db` (sqlite) + `.binex/artifacts/` (JSON files)

## Testing Patterns

- Use `click.testing.CliRunner` + `patch("binex.cli.<module>._get_stores", ...)` for CLI tests
- `InMemoryExecutionStore` and `InMemoryArtifactStore` for unit tests
- QA test files use `test_qa_*.py` naming convention
- QA v1: `tests/docs/QA-TEST-PLAN.md` (65 cases) + `TEST-EXECUTION-TRACKING.csv` + `BUG-TRACKING.csv`
- QA v2: `tests/docs/QA-TEST-PLAN-v2.md` (125 cases) + `TEST-EXECUTION-TRACKING-v2.csv` + `BUG-TRACKING-v2.csv`

## Security Notes

- `FilesystemArtifactStore._sanitize_component()` rejects `..`, `/`, `\` in run_id/artifact_id (path traversal protection)
- `build_lineage_tree()` uses `_ancestors` frozenset to prevent infinite recursion on circular derived_from
- `yaml.safe_load()` used everywhere (never `yaml.load()`)
- SQLite stores use parameterized queries (SQL injection safe)
- A2A adapter does NOT validate endpoint IPs (no SSRF protection) — by design
<!-- MANUAL ADDITIONS END -->
