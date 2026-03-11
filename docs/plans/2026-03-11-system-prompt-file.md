# system_prompt file:// Support — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Support `file://` prefix in `system_prompt` to load prompt content from external files at YAML parse time.

**Architecture:** Add a `_resolve_file_prompts(data, base_dir)` function in `workflow_spec/loader.py` that walks `nodes` and replaces any `system_prompt` starting with `file://` with the file's content. Called in `load_workflow()` after env/user var interpolation, before `WorkflowSpec` construction. `load_workflow_from_string()` gains an optional `base_dir` parameter.

**Tech Stack:** Python 3.11+, pathlib, existing loader infrastructure.

---

### Task 1: Write failing tests for `_resolve_file_prompts`

**Files:**
- Modify: `tests/unit/test_workflow_loader.py`

**Step 1: Write the failing tests**

```python
import pytest
from pathlib import Path


class TestResolveFilePrompts:
    """Tests for file:// system_prompt resolution."""

    def test_resolve_file_prompt_relative(self, tmp_path):
        """Relative file:// path resolves relative to base_dir."""
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "agent.md").write_text("You are a helpful agent.")

        data = {
            "name": "test",
            "nodes": {
                "a": {
                    "agent": "llm://openai/gpt-4",
                    "system_prompt": "file://prompts/agent.md",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts

        _resolve_file_prompts(data, base_dir=tmp_path)
        assert data["nodes"]["a"]["system_prompt"] == "You are a helpful agent."

    def test_resolve_file_prompt_absolute(self, tmp_path):
        """Absolute file:// path is used as-is."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Absolute prompt content.")

        data = {
            "name": "test",
            "nodes": {
                "a": {
                    "agent": "llm://openai/gpt-4",
                    "system_prompt": f"file://{prompt_file}",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts

        _resolve_file_prompts(data, base_dir=tmp_path)
        assert data["nodes"]["a"]["system_prompt"] == "Absolute prompt content."

    def test_resolve_file_prompt_not_found(self, tmp_path):
        """Missing file raises ValueError with node name and path."""
        data = {
            "name": "test",
            "nodes": {
                "researcher": {
                    "agent": "llm://openai/gpt-4",
                    "system_prompt": "file://missing.md",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts

        with pytest.raises(ValueError, match="researcher"):
            _resolve_file_prompts(data, base_dir=tmp_path)

    def test_plain_system_prompt_unchanged(self, tmp_path):
        """Plain string system_prompt is not affected."""
        data = {
            "name": "test",
            "nodes": {
                "a": {
                    "agent": "llm://openai/gpt-4",
                    "system_prompt": "Just a regular prompt",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts

        _resolve_file_prompts(data, base_dir=tmp_path)
        assert data["nodes"]["a"]["system_prompt"] == "Just a regular prompt"

    def test_no_system_prompt_unchanged(self, tmp_path):
        """Node without system_prompt is not affected."""
        data = {
            "name": "test",
            "nodes": {
                "a": {
                    "agent": "llm://openai/gpt-4",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts

        _resolve_file_prompts(data, base_dir=tmp_path)
        assert "system_prompt" not in data["nodes"]["a"]
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_workflow_loader.py::TestResolveFilePrompts -v`
Expected: FAIL with `ImportError` — `_resolve_file_prompts` doesn't exist yet.

---

### Task 2: Implement `_resolve_file_prompts`

**Files:**
- Modify: `src/binex/workflow_spec/loader.py`

**Step 1: Add the function**

Add after `_interpolate` function:

```python
def _resolve_file_prompts(data: dict[str, Any], base_dir: Path | None = None) -> None:
    """Resolve file:// prefixed system_prompt values by reading file content.

    Relative paths resolve relative to base_dir (typically the YAML file's directory).
    Absolute paths are used as-is.
    """
    nodes = data.get("nodes")
    if not isinstance(nodes, dict):
        return

    for node_name, node_data in nodes.items():
        if not isinstance(node_data, dict):
            continue
        prompt = node_data.get("system_prompt")
        if not isinstance(prompt, str) or not prompt.startswith("file://"):
            continue

        file_path_str = prompt[len("file://"):]
        file_path = Path(file_path_str)

        if not file_path.is_absolute() and base_dir is not None:
            file_path = base_dir / file_path

        try:
            node_data["system_prompt"] = file_path.read_text()
        except FileNotFoundError:
            raise ValueError(
                f"Node '{node_name}': system_prompt file not found: {file_path}"
            )
        except OSError as exc:
            raise ValueError(
                f"Node '{node_name}': cannot read system_prompt file {file_path}: {exc}"
            ) from exc
```

**Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_workflow_loader.py::TestResolveFilePrompts -v`
Expected: All 5 PASS.

**Step 3: Commit**

```bash
git add src/binex/workflow_spec/loader.py tests/unit/test_workflow_loader.py
git commit -m "feat: add _resolve_file_prompts for file:// system_prompt support"
```

---

### Task 3: Wire `_resolve_file_prompts` into `load_workflow`

**Files:**
- Modify: `src/binex/workflow_spec/loader.py`

**Step 1: Write the failing integration test**

Add to `tests/unit/test_workflow_loader.py`:

```python
class TestLoadWorkflowFilePrompt:
    """Integration: load_workflow resolves file:// system_prompt."""

    def test_load_workflow_resolves_file_prompt(self, tmp_path):
        """Full load_workflow pipeline resolves file:// prompts."""
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "researcher.md").write_text("You are a researcher.")

        workflow_yaml = tmp_path / "workflow.yaml"
        workflow_yaml.write_text(
            """
name: test-workflow
nodes:
  researcher:
    agent: llm://openai/gpt-4
    system_prompt: "file://prompts/researcher.md"
    outputs: [result]
"""
        )

        from binex.workflow_spec.loader import load_workflow

        spec = load_workflow(workflow_yaml)
        assert spec.nodes["researcher"].system_prompt == "You are a researcher."
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_workflow_loader.py::TestLoadWorkflowFilePrompt -v`
Expected: FAIL — `system_prompt` is still `"file://prompts/researcher.md"`.

**Step 3: Wire into `load_workflow` and `load_workflow_from_string`**

In `load_workflow()`, pass `base_dir` to `load_workflow_from_string`:

```python
def load_workflow(
    path: str | Path,
    *,
    user_vars: dict[str, str] | None = None,
) -> WorkflowSpec:
    """Load a workflow from a YAML or JSON file."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        fmt = "yaml"
    elif suffix == ".json":
        fmt = "json"
    else:
        raise ValueError(f"Unsupported file extension: {suffix}")

    return load_workflow_from_string(
        path.read_text(), fmt=fmt, user_vars=user_vars,
        base_dir=path.parent,
    )
```

In `load_workflow_from_string()`, add `base_dir` parameter and call `_resolve_file_prompts`:

```python
def load_workflow_from_string(
    content: str,
    *,
    fmt: str = "yaml",
    user_vars: dict[str, str] | None = None,
    base_dir: Path | None = None,
) -> WorkflowSpec:
    """Parse a workflow from a YAML or JSON string."""
    data = _parse_raw(content, fmt)
    _resolve_env_vars(data)
    if user_vars:
        _interpolate(data, user_vars)
    _resolve_file_prompts(data, base_dir=base_dir)
    try:
        spec = WorkflowSpec(**data)
    except ValidationError as exc:
        raise ValueError(f"Invalid workflow spec: {exc}") from exc
    return spec
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_workflow_loader.py -v`
Expected: All tests PASS (existing + new).

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All 1235+ tests PASS.

**Step 6: Lint**

Run: `ruff check src/binex/workflow_spec/loader.py`
Expected: No errors.

**Step 7: Commit**

```bash
git add src/binex/workflow_spec/loader.py tests/unit/test_workflow_loader.py
git commit -m "feat: wire file:// system_prompt resolution into load_workflow"
```

---

### Task 4: Update documentation

**Files:**
- Modify: `docs/cli/cost.md` (or relevant workflow docs if they exist)

**Step 1: Check for existing workflow documentation**

Run: `ls docs/`
Find any workflow or YAML reference docs.

**Step 2: Add `file://` system_prompt documentation**

Add a section documenting the `file://` prefix syntax with an example.

**Step 3: Commit**

```bash
git add docs/
git commit -m "docs: document file:// system_prompt syntax"
```
