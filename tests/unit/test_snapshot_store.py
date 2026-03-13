"""Tests for workflow snapshot storage in SQLite."""

import pytest

from binex.stores.backends.sqlite import SqliteExecutionStore


@pytest.mark.asyncio
async def test_store_workflow_snapshot(tmp_path):
    """store_workflow_snapshot saves content and returns hash."""
    db_path = str(tmp_path / "test.db")
    store = SqliteExecutionStore(db_path)
    await store.initialize()
    try:
        yaml_content = "name: test\nnodes: {}"
        hash1 = await store.store_workflow_snapshot(yaml_content, version=1)
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_snapshot_deduplication(tmp_path):
    """Same content should return same hash, no duplicate rows."""
    db_path = str(tmp_path / "test.db")
    store = SqliteExecutionStore(db_path)
    await store.initialize()
    try:
        content = "name: test\nnodes: {}"
        hash1 = await store.store_workflow_snapshot(content, version=1)
        hash2 = await store.store_workflow_snapshot(content, version=1)
        assert hash1 == hash2
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_get_workflow_snapshot(tmp_path):
    """get_workflow_snapshot returns stored content by hash."""
    db_path = str(tmp_path / "test.db")
    store = SqliteExecutionStore(db_path)
    await store.initialize()
    try:
        content = "name: test\nnodes: {}"
        h = await store.store_workflow_snapshot(content, version=1)
        result = await store.get_workflow_snapshot(h)
        assert result is not None
        assert result["content"] == content
        assert result["version"] == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_get_workflow_snapshot_not_found(tmp_path):
    db_path = str(tmp_path / "test.db")
    store = SqliteExecutionStore(db_path)
    await store.initialize()
    try:
        result = await store.get_workflow_snapshot("nonexistent")
        assert result is None
    finally:
        await store.close()
