"""Content-addressed cache keys for node execution.

A node's cached result is reusable only when everything that determines its
output is unchanged: the agent, the resolved prompt, the model parameters, the
tool set, and the content of its input artifacts. ``compute_cache_key`` hashes
exactly that, so editing a downstream prompt never invalidates upstream nodes.
See issue #68.
"""

from __future__ import annotations

import hashlib
import json

from binex.models.artifact import Artifact
from binex.models.task import TaskNode

# Bump when the cache-key composition or execution semantics change, to
# invalidate every existing entry.
CACHE_VERSION = 1

# Config keys that don't change a node's output and must not bust the cache
# (rotating an API key shouldn't force a full re-run).
_IGNORED_CONFIG = {"api_key"}


def _artifact_fingerprint(artifact: Artifact) -> str:
    payload = json.dumps(
        {"type": artifact.type, "content": artifact.content},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_cache_key(
    task: TaskNode,
    input_artifacts: list[Artifact],
    *,
    version: int = CACHE_VERSION,
) -> str:
    """Deterministic hash over everything that determines a node's output."""
    material = {
        "version": version,
        "agent": task.agent,
        "system_prompt": task.system_prompt,
        "inputs": task.inputs,
        "config": {
            k: v for k, v in task.config.items() if k not in _IGNORED_CONFIG
        },
        "tools": task.tools,
        "input_artifacts": [_artifact_fingerprint(a) for a in input_artifacts],
    }
    blob = json.dumps(material, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()
