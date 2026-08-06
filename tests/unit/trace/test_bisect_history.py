"""Unit tests for history-bisect search core and git helpers (issue #72)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from binex.bisect_history import (
    BisectError,
    Verdict,
    bisect_history,
    is_clean_worktree,
    list_commits_between,
    resolve_ref,
    worktree_at,
)


def _make_probe(bad_from: int):
    """Monotonic probe: commit index >= bad_from is 'bad', else 'good'.

    The probe receives the commit *string* (we encode index as 'c<idx>').
    """
    async def probe(commit: str) -> tuple[Verdict, str]:
        idx = int(commit[1:])
        return ("bad", "broke") if idx >= bad_from else ("good", "ok")
    return probe


@pytest.mark.asyncio
async def test_finds_first_bad_middle() -> None:
    commits = [f"c{i}" for i in range(1, 8)]  # c1..c7
    result = await bisect_history(commits, _make_probe(bad_from=4))
    assert result.first_bad == "c4"
    assert result.indeterminate is False
    # binary search should not probe all 7
    assert result.tested < len(commits)


@pytest.mark.asyncio
async def test_first_commit_is_bad() -> None:
    commits = [f"c{i}" for i in range(1, 6)]
    result = await bisect_history(commits, _make_probe(bad_from=1))
    assert result.first_bad == "c1"


@pytest.mark.asyncio
async def test_only_tip_is_bad() -> None:
    commits = [f"c{i}" for i in range(1, 6)]  # c1..c5
    result = await bisect_history(commits, _make_probe(bad_from=5))
    assert result.first_bad == "c5"


@pytest.mark.asyncio
async def test_all_good_no_bad_found() -> None:
    commits = [f"c{i}" for i in range(1, 6)]
    result = await bisect_history(commits, _make_probe(bad_from=99))
    assert result.first_bad is None
    assert result.indeterminate is False


@pytest.mark.asyncio
async def test_single_commit_bad() -> None:
    result = await bisect_history(["c1"], _make_probe(bad_from=1))
    assert result.first_bad == "c1"


@pytest.mark.asyncio
async def test_skip_steps_over() -> None:
    # c3 is unevaluable (skip); the real regression is at c4.
    async def probe(commit: str) -> tuple[Verdict, str]:
        idx = int(commit[1:])
        if idx == 3:
            return "skip", "workflow absent"
        return ("bad", "broke") if idx >= 4 else ("good", "ok")

    commits = [f"c{i}" for i in range(1, 8)]
    result = await bisect_history(commits, probe)
    assert result.first_bad == "c4"
    assert "c3" in result.skipped


@pytest.mark.asyncio
async def test_all_skip_is_indeterminate() -> None:
    async def probe(commit: str) -> tuple[Verdict, str]:
        return "skip", "nope"

    result = await bisect_history([f"c{i}" for i in range(1, 5)], probe)
    assert result.indeterminate is True
    assert result.first_bad is None


# --- git helpers against a real tiny repo ---------------------------------

def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo_with_commits(tmp_path: Path) -> tuple[Path, list[str]]:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(["init"], repo)
    _git(["config", "user.email", "t@t.co"], repo)
    _git(["config", "user.name", "t"], repo)
    shas = []
    for i in range(4):
        (repo / "f.txt").write_text(f"v{i}")
        _git(["add", "."], repo)
        _git(["commit", "-m", f"c{i}"], repo)
        shas.append(_git(["rev-parse", "HEAD"], repo))
    return repo, shas


def test_list_commits_between(repo_with_commits) -> None:
    repo, shas = repo_with_commits
    # between c0 and c3 → [c1, c2, c3], oldest first
    commits = list_commits_between(shas[0], shas[3], str(repo))
    assert commits == [shas[1], shas[2], shas[3]]


def test_list_commits_between_unrelated_raises(repo_with_commits) -> None:
    repo, shas = repo_with_commits
    # good == bad → no commits between → error
    with pytest.raises(BisectError):
        list_commits_between(shas[3], shas[3], str(repo))


def test_resolve_ref(repo_with_commits) -> None:
    repo, shas = repo_with_commits
    assert resolve_ref("HEAD", str(repo)) == shas[3]
    assert resolve_ref(shas[1][:8], str(repo)) == shas[1]


def test_resolve_ref_unknown_raises(repo_with_commits) -> None:
    repo, _ = repo_with_commits
    with pytest.raises(BisectError):
        resolve_ref("no_such_ref", str(repo))


def test_is_clean_worktree(repo_with_commits) -> None:
    repo, _ = repo_with_commits
    assert is_clean_worktree(str(repo)) is True
    (repo / "dirty.txt").write_text("x")
    assert is_clean_worktree(str(repo)) is False


def test_worktree_at_checks_out_commit(repo_with_commits) -> None:
    repo, shas = repo_with_commits
    with worktree_at(str(repo), shas[0]) as wt:
        assert (wt / "f.txt").read_text() == "v0"  # old content, not HEAD's v3
    # working tree of the main repo is untouched
    assert (repo / "f.txt").read_text() == "v3"
