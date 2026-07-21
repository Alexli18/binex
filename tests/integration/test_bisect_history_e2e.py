"""End-to-end history bisect: pinpoint the commit that broke a workflow (#72).

Uses a real git repo and the `local://echo` agent (no network). Across commits
only the node's assertion changes — the realistic "someone edited the workflow
and broke it" scenario. `local://echo` deterministically outputs
``{'msg': 'no input'}`` for a root node, so the assertion decides pass/fail.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from binex.bisect_history import bisect_history, list_commits_between, make_git_probe

_GOOD_WF = """\
name: bisect-demo
nodes:
  n1:
    agent: "local://echo"
    outputs: [result]
    assertions:
      - contains: "no input"
"""

_BAD_WF = """\
name: bisect-demo
nodes:
  n1:
    agent: "local://echo"
    outputs: [result]
    assertions:
      - contains: "ZZZ_WILL_NOT_MATCH"
"""


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _commit(repo: Path, msg: str) -> str:
    _git(["add", "."], repo)
    _git(["commit", "-m", msg], repo)
    return _git(["rev-parse", "HEAD"], repo)


@pytest.fixture
def broken_history(tmp_path: Path) -> tuple[Path, list[str]]:
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(["init"], repo)
    _git(["config", "user.email", "t@t.co"], repo)
    _git(["config", "user.name", "t"], repo)

    (repo / "flow.yaml").write_text(_GOOD_WF)
    (repo / "README.md").write_text("v0")
    c0 = _commit(repo, "good workflow")            # PASS

    (repo / "README.md").write_text("v1")
    c1 = _commit(repo, "unrelated change")         # still PASS

    (repo / "flow.yaml").write_text(_BAD_WF)       # <-- the culprit
    c2 = _commit(repo, "break the assertion")      # FAIL

    (repo / "README.md").write_text("v3")
    c3 = _commit(repo, "another unrelated change")  # still FAIL (tip = bad)

    return repo, [c0, c1, c2, c3]


@pytest.mark.asyncio
async def test_history_bisect_finds_culprit(
    broken_history, tmp_path, monkeypatch,
) -> None:
    repo, (c0, c1, c2, c3) = broken_history
    monkeypatch.setenv("BINEX_STORE_PATH", str(tmp_path / "store"))

    commits = list_commits_between(c0, c3, str(repo))
    assert commits == [c1, c2, c3]

    probe = make_git_probe(str(repo), "flow.yaml")
    result = await bisect_history(commits, probe)

    assert result.first_bad == c2
    assert result.indeterminate is False


@pytest.mark.asyncio
async def test_probe_skips_commit_without_workflow(
    broken_history, tmp_path, monkeypatch,
) -> None:
    repo, (c0, c1, c2, c3) = broken_history
    monkeypatch.setenv("BINEX_STORE_PATH", str(tmp_path / "store2"))

    # A workflow path that never exists in history → every probe skips.
    probe = make_git_probe(str(repo), "nonexistent/flow.yaml")
    verdict, detail = await probe(c1)
    assert verdict == "skip"
    assert "absent" in detail
