"""Pipeline lockfile + drift detection (issue #69)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from binex.cli.freeze import freeze_cmd
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.workflow_spec.freeze import (
    check_drift,
    compute_lock,
    is_pinned,
    unpinnable_models,
)


def _spec(prompt_a="do", model_a="llm://gpt-4o") -> WorkflowSpec:
    return WorkflowSpec(name="w", nodes={
        "a": NodeSpec(agent=model_a, system_prompt=prompt_a, outputs=["r"]),
        "b": NodeSpec(agent="llm://gpt-4o-2024-11-20", system_prompt="x",
                      outputs=["r"], depends_on=["a"]),
    })


# ── pinning honesty ──────────────────────────────────────────────────────

def test_is_pinned():
    assert is_pinned("gpt-4o-2024-11-20") is True
    assert is_pinned("openai/gpt-4o-2024-11-20") is True
    assert is_pinned("ollama/llama3@sha256:abc") is True
    assert is_pinned("gpt-4o") is False
    assert is_pinned("claude-sonnet-4-5") is False
    assert is_pinned(None) is False


def test_lock_marks_aliases_unpinnable():
    lock = compute_lock(_spec())
    assert lock["nodes"]["a"]["pinned"] is False   # gpt-4o alias
    assert lock["nodes"]["b"]["pinned"] is True    # dated snapshot
    assert unpinnable_models(lock) == ["a"]


# ── drift detection ──────────────────────────────────────────────────────

def test_no_drift_for_identical_spec():
    spec = _spec()
    assert check_drift(spec, compute_lock(spec)) == []


def test_prompt_drift_detected():
    lock = compute_lock(_spec(prompt_a="do"))
    drift = check_drift(_spec(prompt_a="CHANGED"), lock)
    assert drift == ["node 'a': prompt changed"]


def test_model_drift_detected():
    lock = compute_lock(_spec(model_a="llm://gpt-4o"))
    drift = check_drift(_spec(model_a="llm://gpt-4o-mini"), lock)
    assert any("model changed" in d for d in drift)


def test_added_and_removed_nodes():
    lock = compute_lock(_spec())
    smaller = WorkflowSpec(name="w", nodes={
        "a": NodeSpec(agent="llm://gpt-4o", system_prompt="do", outputs=["r"]),
        "c": NodeSpec(agent="llm://gpt-4o", system_prompt="new", outputs=["r"]),
    })
    drift = check_drift(smaller, lock)
    assert "node 'b' was removed since the lock" in drift
    assert "node 'c' was added since the lock" in drift


# ── CLI ──────────────────────────────────────────────────────────────────

def _write_wf(tmp_path: Path) -> str:
    wf = {
        "name": "w",
        "nodes": {
            "a": {"agent": "llm://gpt-4o", "system_prompt": "do", "outputs": ["r"]},
        },
    }
    p = tmp_path / "wf.yaml"
    p.write_text(yaml.dump(wf))
    return str(p)


def test_cli_freeze_writes_lock(tmp_path):
    wf = _write_wf(tmp_path)
    lock = tmp_path / "binex.lock"
    result = CliRunner().invoke(freeze_cmd, [wf, "-o", str(lock)])
    assert result.exit_code == 0
    assert lock.exists()
    data = json.loads(lock.read_text())
    assert "a" in data["nodes"]
    # unpinnable note surfaced
    assert "unpinnable" in result.output


def test_cli_freeze_check_detects_drift(tmp_path):
    wf = _write_wf(tmp_path)
    lock = tmp_path / "binex.lock"
    CliRunner().invoke(freeze_cmd, [wf, "-o", str(lock)])

    # edit the workflow
    edited = {
        "name": "w",
        "nodes": {
            "a": {"agent": "llm://gpt-4o", "system_prompt": "DIFFERENT", "outputs": ["r"]},
        },
    }
    Path(wf).write_text(yaml.dump(edited))

    result = CliRunner().invoke(freeze_cmd, [wf, "-o", str(lock), "--check"])
    assert result.exit_code == 1
    assert "Drift detected" in result.output
    assert "prompt changed" in result.output
