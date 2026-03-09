"""Tests for store factory functions and CLI helper utilities."""

from __future__ import annotations

import tempfile
from unittest.mock import patch

import pytest

from binex.stores import create_artifact_store, create_execution_store
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore


# --- create_artifact_store ---


def test_create_artifact_store_memory():
    store = create_artifact_store("memory")
    assert isinstance(store, InMemoryArtifactStore)


def test_create_artifact_store_filesystem():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = create_artifact_store("filesystem", base_path=tmpdir)
        assert isinstance(store, FilesystemArtifactStore)


def test_create_artifact_store_filesystem_default_path():
    store = create_artifact_store("filesystem")
    assert isinstance(store, FilesystemArtifactStore)


def test_create_artifact_store_filesystem_custom_path():
    store = create_artifact_store("filesystem", base_path="/custom")
    assert isinstance(store, FilesystemArtifactStore)


def test_create_artifact_store_unknown_raises():
    with pytest.raises(ValueError, match="Unknown artifact store backend: unknown"):
        create_artifact_store("unknown")


# --- create_execution_store ---


def test_create_execution_store_memory():
    store = create_execution_store("memory")
    assert isinstance(store, InMemoryExecutionStore)


def test_create_execution_store_sqlite():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = f"{tmpdir}/test.db"
        store = create_execution_store("sqlite", db_path=db_path)
        assert isinstance(store, SqliteExecutionStore)


def test_create_execution_store_sqlite_default_path():
    store = create_execution_store("sqlite")
    assert isinstance(store, SqliteExecutionStore)


def test_create_execution_store_sqlite_custom_path():
    store = create_execution_store("sqlite", db_path="/custom.db")
    assert isinstance(store, SqliteExecutionStore)


def test_create_execution_store_unknown_raises():
    with pytest.raises(ValueError, match="Unknown execution store backend: unknown"):
        create_execution_store("unknown")


# --- get_stores ---


def test_get_stores_returns_correct_types():
    from binex.cli import get_stores

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("binex.cli.Settings") as mock_settings_cls:
            mock_settings = mock_settings_cls.return_value
            mock_settings.db_path = f"{tmpdir}/binex.db"
            mock_settings.artifacts_dir = f"{tmpdir}/artifacts"

            exec_store, art_store = get_stores()

            assert isinstance(exec_store, SqliteExecutionStore)
            assert isinstance(art_store, FilesystemArtifactStore)


# --- run_async ---


def test_run_async_executes_coroutine():
    from binex.cli import run_async

    async def add(a: int, b: int) -> int:
        return a + b

    result = run_async(add, 3, 7)
    assert result == 10


def test_run_async_no_args():
    from binex.cli import run_async

    async def greeting() -> str:
        return "hello"

    result = run_async(greeting)
    assert result == "hello"
