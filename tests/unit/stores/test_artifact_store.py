"""Tests for artifact store backends (InMemory + Filesystem)."""

from __future__ import annotations

import os
import tempfile

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.stores.backends.memory import InMemoryArtifactStore


@pytest.fixture
def art_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


def _make_artifact(id: str, run_id: str = "run_01", produced_by: str = "node1",
                   derived_from: list[str] | None = None) -> Artifact:
    return Artifact(
        id=id,
        run_id=run_id,
        type="test",
        content={"data": id},
        lineage=Lineage(produced_by=produced_by, derived_from=derived_from or []),
    )


class TestInMemoryArtifactStore:
    @pytest.mark.asyncio
    async def test_store_and_get(self, art_store: InMemoryArtifactStore) -> None:
        art = _make_artifact("art_01")
        await art_store.store(art)
        result = await art_store.get("art_01")
        assert result is not None
        assert result.id == "art_01"
        assert result.content == {"data": "art_01"}

    @pytest.mark.asyncio
    async def test_get_missing(self, art_store: InMemoryArtifactStore) -> None:
        result = await art_store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_run(self, art_store: InMemoryArtifactStore) -> None:
        await art_store.store(_make_artifact("a1", run_id="r1"))
        await art_store.store(_make_artifact("a2", run_id="r1"))
        await art_store.store(_make_artifact("a3", run_id="r2"))
        results = await art_store.list_by_run("r1")
        assert len(results) == 2
        ids = {a.id for a in results}
        assert ids == {"a1", "a2"}

    @pytest.mark.asyncio
    async def test_get_lineage(self, art_store: InMemoryArtifactStore) -> None:
        a1 = _make_artifact("a1")
        a2 = _make_artifact("a2", derived_from=["a1"])
        a3 = _make_artifact("a3", derived_from=["a2"])
        await art_store.store(a1)
        await art_store.store(a2)
        await art_store.store(a3)
        lineage = await art_store.get_lineage("a3")
        ids = {a.id for a in lineage}
        assert "a2" in ids
        assert "a1" in ids


class TestFilesystemArtifactStore:
    @pytest.mark.asyncio
    async def test_store_and_get(self) -> None:
        from binex.stores.backends.filesystem import FilesystemArtifactStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            art = _make_artifact("art_fs_01")
            await store.store(art)

            # Verify file exists
            path = os.path.join(tmpdir, "run_01", "art_fs_01.json")
            assert os.path.exists(path)

            # Verify content
            result = await store.get("art_fs_01")
            assert result is not None
            assert result.id == "art_fs_01"
            assert result.content == {"data": "art_fs_01"}

    @pytest.mark.asyncio
    async def test_get_missing(self) -> None:
        from binex.stores.backends.filesystem import FilesystemArtifactStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            result = await store.get("nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_list_by_run(self) -> None:
        from binex.stores.backends.filesystem import FilesystemArtifactStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            await store.store(_make_artifact("a1", run_id="r1"))
            await store.store(_make_artifact("a2", run_id="r1"))
            await store.store(_make_artifact("a3", run_id="r2"))
            results = await store.list_by_run("r1")
            assert len(results) == 2
