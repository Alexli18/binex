"""The MCP replay_node tool must report workflow drift distinctly.

An agent driving Binex over MCP cannot see a warning on stderr — it only sees
the tool's return value. So a stale cached upstream has to come back as its own
error code, with the escape hatch reachable as a parameter.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from binex.mcp_server import tools as mcp_tools
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.models.workflow import WorkflowSpec
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

WORKFLOW_YAML = """\
name: drift-test
nodes:
  builder:
    agent: "local://echo"
    system_prompt: build
    outputs: [draft]
  reviewer:
    agent: "local://echo"
    system_prompt: review
    outputs: [review]
    depends_on: [builder]
"""

EDITED_WORKFLOW_YAML = WORKFLOW_YAML.replace(
    "system_prompt: build", "system_prompt: build, but rewritten",
)


async def _seed(tmp_path: Path):
    """Run recorded against WORKFLOW_YAML; the file on disk has since changed."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    workflow_file = tmp_path / "drift-test.yaml"
    workflow_file.write_text(EDITED_WORKFLOW_YAML)

    spec = WorkflowSpec(**yaml.safe_load(WORKFLOW_YAML))
    workflow_hash = await exec_store.store_workflow_snapshot(
        yaml.dump(spec.model_dump(exclude={"source_path"}), sort_keys=True),
        version=spec.version,
    )
    await exec_store.create_run(RunSummary(
        run_id="run-orig", workflow_name="drift-test", status="completed",
        total_nodes=2, completed_nodes=2,
        workflow_path=str(workflow_file), workflow_hash=workflow_hash,
    ))
    await art_store.store(Artifact(
        id="art-draft", run_id="run-orig", type="draft", content="v1",
        lineage=Lineage(produced_by="builder"),
    ))
    await exec_store.record(ExecutionRecord(
        id="rec-builder", run_id="run-orig", task_id="builder",
        agent_id="local://echo", status=TaskStatus.COMPLETED,
        output_artifact_refs=["art-draft"], latency_ms=5, trace_id="trace-orig",
    ))
    return exec_store, art_store


@pytest.mark.asyncio
async def test_drifted_upstream_returns_workflow_drift_code(tmp_path):
    exec_store, art_store = await _seed(tmp_path)

    result = await mcp_tools.replay_node(
        exec_store, art_store, run_id="run-orig", node_id="reviewer",
    )

    assert result["code"] == "workflow_drift"
    assert "builder" in result["error"]


@pytest.mark.asyncio
async def test_allow_drift_parameter_replays_anyway(tmp_path):
    exec_store, art_store = await _seed(tmp_path)

    result = await mcp_tools.replay_node(
        exec_store, art_store, run_id="run-orig", node_id="reviewer",
        allow_drift=True,
    )

    assert "error" not in result
