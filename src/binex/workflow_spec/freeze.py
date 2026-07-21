"""Pipeline lockfile and drift detection (issue #69).

`binex freeze` writes a `binex.lock` — a package-lock.json for a pipeline: for
every node, the resolved model, prompt hash, parameters, tool set, and a
combined node hash. `binex run --frozen` and `binex freeze --check` then report
what drifted since the lock was written.

Honesty of the lock: `gpt-4o` is a pointer — the provider swaps weights under it.
The lock marks such aliases `pinned: false`; dated snapshots (`gpt-4o-2024-11-20`)
are `pinned: true`. It never pretends more determinism than exists.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from binex.models.workflow import NodeSpec, WorkflowSpec

LOCK_VERSION = 1

# A model string that carries a dated / digest-style suffix is considered
# pinnable; bare aliases are not (the provider can change them underneath you).
_PINNED_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{8}|@sha256:|:[0-9a-f]{12,}")


def _hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _model_of(node: NodeSpec) -> str | None:
    return node.agent.removeprefix("llm://") if node.agent.startswith("llm://") else None


def is_pinned(model: str | None) -> bool:
    """True if the model string identifies a fixed snapshot, not a moving alias."""
    return bool(model and _PINNED_RE.search(model))


def _node_lock(node: NodeSpec) -> dict[str, Any]:
    model = _model_of(node)
    entry: dict[str, Any] = {
        "agent": node.agent,
        "prompt_hash": _hash(node.system_prompt),
        "params_hash": _hash(node.config),
        "tools_hash": _hash(sorted(str(t) for t in node.tools)),
        "depends_on": sorted(node.depends_on),
    }
    if model is not None:
        entry["model"] = model
        entry["pinned"] = is_pinned(model)
    entry["node_hash"] = _hash(entry)
    return entry


def compute_lock(spec: WorkflowSpec) -> dict[str, Any]:
    """Build a lockfile dict for a workflow."""
    return {
        "version": LOCK_VERSION,
        "workflow": spec.name,
        "nodes": {nid: _node_lock(node) for nid, node in spec.nodes.items()},
    }


def check_drift(spec: WorkflowSpec, lock: dict[str, Any]) -> list[str]:
    """Return human-readable drift descriptions between a spec and a lock."""
    drift: list[str] = []
    locked_nodes: dict[str, Any] = lock.get("nodes", {})
    current = {nid: _node_lock(node) for nid, node in spec.nodes.items()}

    for nid in sorted(set(locked_nodes) - set(current)):
        drift.append(f"node '{nid}' was removed since the lock")
    for nid in sorted(set(current) - set(locked_nodes)):
        drift.append(f"node '{nid}' was added since the lock")

    for nid in sorted(set(current) & set(locked_nodes)):
        cur, was = current[nid], locked_nodes[nid]
        if cur["node_hash"] == was.get("node_hash"):
            continue
        for field, label in (
            ("prompt_hash", "prompt"), ("params_hash", "parameters"),
            ("tools_hash", "tools"), ("model", "model"),
            ("depends_on", "dependencies"),
        ):
            if cur.get(field) != was.get(field):
                drift.append(f"node '{nid}': {label} changed")
    return drift


def unpinnable_models(lock: dict[str, Any]) -> list[str]:
    """Nodes whose model is an alias that can drift under the lock."""
    return [
        nid for nid, e in lock.get("nodes", {}).items()
        if "model" in e and not e.get("pinned")
    ]
