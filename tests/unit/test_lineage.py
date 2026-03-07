"""Tests for artifact lineage traversal (T036)."""

from __future__ import annotations

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.stores.backends.memory import InMemoryArtifactStore
from binex.trace.lineage import build_lineage_tree, format_lineage_tree


@pytest.fixture
def artifact_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


@pytest.fixture
async def populated_artifact_store(
    artifact_store: InMemoryArtifactStore,
) -> InMemoryArtifactStore:
    artifacts = [
        Artifact(
            id="art_query",
            run_id="run_001",
            type="query",
            content={"text": "AI safety"},
            lineage=Lineage(produced_by="input", derived_from=[]),
        ),
        Artifact(
            id="art_plan",
            run_id="run_001",
            type="execution_plan",
            content={"steps": ["search", "validate"]},
            lineage=Lineage(produced_by="planner", derived_from=["art_query"]),
        ),
        Artifact(
            id="art_research_1",
            run_id="run_001",
            type="search_results",
            content={"results": ["paper1"]},
            lineage=Lineage(produced_by="researcher_1", derived_from=["art_plan"]),
        ),
        Artifact(
            id="art_research_2",
            run_id="run_001",
            type="search_results",
            content={"results": ["paper2"]},
            lineage=Lineage(produced_by="researcher_2", derived_from=["art_plan"]),
        ),
        Artifact(
            id="art_validated",
            run_id="run_001",
            type="validated_results",
            content={"validated": True},
            lineage=Lineage(
                produced_by="validator",
                derived_from=["art_research_1", "art_research_2"],
            ),
        ),
    ]
    for art in artifacts:
        await artifact_store.store(art)
    return artifact_store


@pytest.mark.asyncio
async def test_build_lineage_tree_returns_tree_structure(
    populated_artifact_store: InMemoryArtifactStore,
) -> None:
    tree = await build_lineage_tree(populated_artifact_store, "art_validated")
    assert tree is not None
    assert tree["artifact_id"] == "art_validated"
    assert tree["produced_by"] == "validator"
    assert len(tree["parents"]) == 2


@pytest.mark.asyncio
async def test_build_lineage_tree_walks_full_chain(
    populated_artifact_store: InMemoryArtifactStore,
) -> None:
    tree = await build_lineage_tree(populated_artifact_store, "art_validated")
    # art_validated -> [art_research_1, art_research_2] -> art_plan -> art_query
    parent_ids = {p["artifact_id"] for p in tree["parents"]}
    assert parent_ids == {"art_research_1", "art_research_2"}

    # Each research artifact should have art_plan as parent
    for parent in tree["parents"]:
        assert len(parent["parents"]) == 1
        assert parent["parents"][0]["artifact_id"] == "art_plan"
        # art_plan should have art_query as parent
        assert parent["parents"][0]["parents"][0]["artifact_id"] == "art_query"


@pytest.mark.asyncio
async def test_build_lineage_tree_leaf_has_no_parents(
    populated_artifact_store: InMemoryArtifactStore,
) -> None:
    tree = await build_lineage_tree(populated_artifact_store, "art_query")
    assert tree["artifact_id"] == "art_query"
    assert tree["parents"] == []


@pytest.mark.asyncio
async def test_build_lineage_tree_nonexistent_artifact(
    populated_artifact_store: InMemoryArtifactStore,
) -> None:
    tree = await build_lineage_tree(populated_artifact_store, "nonexistent")
    assert tree is None


@pytest.mark.asyncio
async def test_format_lineage_tree_renders_tree_view(
    populated_artifact_store: InMemoryArtifactStore,
) -> None:
    tree = await build_lineage_tree(populated_artifact_store, "art_validated")
    output = format_lineage_tree(tree)
    assert isinstance(output, str)
    assert "art_validated" in output
    assert "art_plan" in output
    assert "art_query" in output


@pytest.mark.asyncio
async def test_format_lineage_tree_shows_produced_by(
    populated_artifact_store: InMemoryArtifactStore,
) -> None:
    tree = await build_lineage_tree(populated_artifact_store, "art_validated")
    output = format_lineage_tree(tree)
    assert "validator" in output
    assert "planner" in output


@pytest.mark.asyncio
async def test_format_lineage_tree_uses_indentation(
    populated_artifact_store: InMemoryArtifactStore,
) -> None:
    tree = await build_lineage_tree(populated_artifact_store, "art_plan")
    output = format_lineage_tree(tree)
    lines = output.strip().split("\n")
    # Root should not be indented, children should be
    assert len(lines) >= 2
    # At least one child line should have indentation or tree characters
    child_lines = [l for l in lines[1:] if l.strip()]
    assert any("art_query" in l for l in child_lines)
