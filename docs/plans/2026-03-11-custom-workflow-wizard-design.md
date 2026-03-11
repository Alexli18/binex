# Custom Workflow Wizard — Design

## Goal

Replace the current "Custom (DSL only)" option in `binex start` with a full interactive wizard that lets users build custom workflows node-by-node with per-node configuration.

## Architecture

Three-phase wizard inside existing `binex start`:

1. **Topology** — DSL input or step-by-step builder (hybrid)
2. **Node configuration** — per-node: agent type, provider, prompt, back-edge, advanced params
3. **Finalization** — YAML preview, save, optional run

All code lives in `src/binex/cli/start.py`, reusing existing `PROVIDERS`, `BUNDLED_PROMPTS`, `build_start_workflow()`.

## Phase 1: Topology

User chooses DSL or step mode:

- **DSL**: `"planner -> researcher1, researcher2 -> writer"` — parsed as today
- **Step mode** (`step`): interactive dialog:
  - "Name first node:" → planner
  - "Nodes after 'planner'? (comma-separated, or 'done'):" → researcher1, researcher2
  - "Nodes after 'researcher1, researcher2'? (comma-separated, or 'done'):" → writer
  - Shows current graph after each step

## Phase 2: Node Configuration

For each node, wizard asks:

### Required:

**Agent type:**
1. LLM (language model)
2. Human review (approve/reject)
3. Human input (free text)
4. A2A (external agent)

- LLM → provider + model selection
- Human review → `human://review`, no provider questions
- Human input → `human://input`, prompt text only
- A2A → endpoint URL

**System prompt** (for LLM/human input):
- List of bundled prompts (matching node name marked as recommended)
- "Write custom text"
- "Provide file path"

**Back-edge** (for human review nodes):
- "Add review loop? (y/n)"
- If yes: target node (list of upstream) + max_iterations (default 3)

### Optional:

"Configure advanced parameters? (y/n)" — if yes:
- Budget: max_cost (float)
- Retry: max_retries + backoff (fixed/exponential)
- Deadline: timeout in seconds (converted to deadline_ms)
- Config: temperature, max_tokens

## Phase 3: Finalization

1. Preview YAML with Rich syntax highlighting
2. "Save? (y/n)" — if no: "[1] Return to node config [2] Cancel"
3. Generate files: `workflow.yaml`, `prompts/`, `.env`, `.gitignore`
4. "Run workflow? (y/n)" → `binex run workflow.yaml -v`

## New Functions (all in start.py)

- `_custom_interactive_wizard()` — main entry, replaces DSL-only custom
- `_step_mode_topology()` — step-by-step graph builder, returns DSL string
- `_configure_node(node_id, dependencies, bundled_prompts)` — one node setup
- `_configure_advanced_params()` — budget, retry, deadline, config
- `_select_prompt(bundled_prompts, node_id)` — prompt picker (list + custom + file)
- `_configure_back_edge(node_id, upstream_nodes)` — back-edge setup
- `_preview_yaml(yaml_content)` — Rich YAML preview
- `build_custom_workflow(nodes_config)` — assemble final YAML

## Testing

**Unit tests:**
- Step mode topology builder
- Node configuration (type, provider, prompt, back-edge)
- YAML generation with various parameter combinations
- Advanced params (budget, retry, deadline, config)
- Prompt selection (bundled, custom, file path)

**Integration tests:**
- Full flow: step mode → configure → preview → save
- Full flow: DSL → configure → save
- Generated YAML passes `load_workflow()` + `validate_workflow()`

All tests via `CliRunner` + `patch` on `click.prompt`/`click.echo`.
