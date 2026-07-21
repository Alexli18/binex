"""Tests for git provenance capture and its persistence (issue #72)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from binex.git_info import capture_git_meta
from binex.models.execution import RunSummary
from binex.stores import create_execution_store


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init"], repo)
    _git(["config", "user.email", "t@t.co"], repo)
    _git(["config", "user.name", "t"], repo)
    (repo / "a.txt").write_text("hello")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def test_capture_in_clean_repo(git_repo: Path) -> None:
    sha, dirty = capture_git_meta(str(git_repo))
    assert sha is not None
    assert len(sha) == 40  # full commit hash
    assert dirty is False


def test_capture_dirty_repo(git_repo: Path) -> None:
    (git_repo / "a.txt").write_text("changed")
    sha, dirty = capture_git_meta(str(git_repo))
    assert sha is not None
    assert dirty is True


def test_capture_untracked_is_dirty(git_repo: Path) -> None:
    (git_repo / "new.txt").write_text("x")
    _, dirty = capture_git_meta(str(git_repo))
    assert dirty is True


def test_capture_resolves_file_to_parent(git_repo: Path) -> None:
    sha, _ = capture_git_meta(str(git_repo / "a.txt"))
    assert sha is not None


def test_capture_outside_repo(tmp_path: Path) -> None:
    sha, dirty = capture_git_meta(str(tmp_path))
    assert sha is None
    assert dirty is False


def test_capture_nonexistent_path_falls_back_to_cwd() -> None:
    # Should not raise; returns whatever CWD resolves to (repo or None).
    sha, dirty = capture_git_meta("/no/such/path/xyz")
    assert isinstance(dirty, bool)
    assert sha is None or isinstance(sha, str)


@pytest.mark.asyncio
async def test_sqlite_round_trips_git_fields(tmp_path: Path) -> None:
    store = create_execution_store(backend="sqlite", db_path=str(tmp_path / "e.db"))
    summary = RunSummary(
        run_id="run_git1", workflow_name="wf", status="completed",
        total_nodes=1, git_sha="a" * 40, git_dirty=True,
    )
    await store.create_run(summary)
    got = await store.get_run("run_git1")
    assert got is not None
    assert got.git_sha == "a" * 40
    assert got.git_dirty is True

    # update path preserves the fields too
    got.status = "failed"
    await store.update_run(got)
    again = await store.get_run("run_git1")
    assert again.git_sha == "a" * 40
    assert again.git_dirty is True
    await store.close()


@pytest.mark.asyncio
async def test_sqlite_defaults_when_absent(tmp_path: Path) -> None:
    store = create_execution_store(backend="sqlite", db_path=str(tmp_path / "e2.db"))
    summary = RunSummary(
        run_id="run_git2", workflow_name="wf", status="completed", total_nodes=1,
    )
    await store.create_run(summary)
    got = await store.get_run("run_git2")
    assert got.git_sha is None
    assert got.git_dirty is False
    await store.close()
