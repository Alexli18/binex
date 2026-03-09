"""Extended tests for FilesystemArtifactStore — covers uncovered paths.

Targets lines 40-41 (rglob scan), 48 (list_by_run empty), 56-70 (get_lineage BFS).
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.stores.backends.filesystem import FilesystemArtifactStore


def _make_artifact(
    id: str,
    run_id: str = "run_01",
    produced_by: str = "node1",
    derived_from: list[str] | None = None,
) -> Artifact:
    return Artifact(
        id=id,
        run_id=run_id,
        type="test",
        content={"data": id},
        lineage=Lineage(produced_by=produced_by, derived_from=derived_from or []),
    )


def _write_artifact_to_disk(base_path: str, artifact: Artifact) -> None:
    """Write an artifact JSON file directly to disk, bypassing store.store()."""
    run_dir = os.path.join(base_path, artifact.run_id)
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.join(run_dir, f"{artifact.id}.json")
    data = artifact.model_dump(mode="json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


class TestGetRglobScan:
    """Cover lines 40-41: rglob scan when index is empty but file exists on disk."""

    @pytest.mark.asyncio
    async def test_get_finds_artifact_via_rglob(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            art = _make_artifact("rglob_art")
            _write_artifact_to_disk(tmpdir, art)

            # Fresh store instance — internal index is empty
            store = FilesystemArtifactStore(base_path=tmpdir)
            result = await store.get("rglob_art")

            assert result is not None
            assert result.id == "rglob_art"
            assert result.content == {"data": "rglob_art"}

    @pytest.mark.asyncio
    async def test_get_returns_none_when_base_path_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = os.path.join(tmpdir, "does_not_exist")
            store = FilesystemArtifactStore(base_path=nonexistent)
            result = await store.get("anything")
            assert result is None


class TestListByRun:
    """Cover line 48: list_by_run returns [] for nonexistent run."""

    @pytest.mark.asyncio
    async def test_list_by_run_nonexistent_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            result = await store.list_by_run("no_such_run")
            assert result == []

    @pytest.mark.asyncio
    async def test_list_by_run_multiple_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            await store.store(_make_artifact("x1", run_id="r1"))
            await store.store(_make_artifact("x2", run_id="r1"))
            await store.store(_make_artifact("x3", run_id="r1"))
            # Different run — should not appear
            await store.store(_make_artifact("y1", run_id="r2"))

            results = await store.list_by_run("r1")
            assert len(results) == 3
            ids = {a.id for a in results}
            assert ids == {"x1", "x2", "x3"}


class TestGetLineage:
    """Cover lines 56-70: get_lineage BFS traversal."""

    @pytest.mark.asyncio
    async def test_full_bfs_chain(self) -> None:
        """a3 -> a2 -> a1: lineage of a3 should return [a2, a1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            await store.store(_make_artifact("a1"))
            await store.store(_make_artifact("a2", derived_from=["a1"]))
            await store.store(_make_artifact("a3", derived_from=["a2"]))

            lineage = await store.get_lineage("a3")
            ids = {a.id for a in lineage}
            assert ids == {"a2", "a1"}
            # The starting artifact itself should NOT be in the result
            assert all(a.id != "a3" for a in lineage)

    @pytest.mark.asyncio
    async def test_circular_references(self) -> None:
        """a1 derives from a2, a2 derives from a1 — should not loop forever."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            await store.store(_make_artifact("a1", derived_from=["a2"]))
            await store.store(_make_artifact("a2", derived_from=["a1"]))

            lineage = await store.get_lineage("a1")
            ids = {a.id for a in lineage}
            # a2 is an ancestor of a1; a1 itself is excluded
            assert ids == {"a2"}

    @pytest.mark.asyncio
    async def test_missing_ancestor(self) -> None:
        """a2 derives from a_missing (not stored) — lineage stops gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            await store.store(_make_artifact("a1"))
            await store.store(
                _make_artifact("a2", derived_from=["a1", "a_missing"])
            )

            lineage = await store.get_lineage("a2")
            ids = {a.id for a in lineage}
            # Only a1 is reachable; a_missing is silently skipped
            assert ids == {"a1"}

    @pytest.mark.asyncio
    async def test_empty_derived_from(self) -> None:
        """Artifact with no ancestors — lineage is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            await store.store(_make_artifact("solo"))

            lineage = await store.get_lineage("solo")
            assert lineage == []
