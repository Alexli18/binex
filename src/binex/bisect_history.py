"""History bisect — find the commit that broke pipeline quality (issue #72).

Binary-search a commit range, re-running a workflow at each probe commit and
judging pass/fail with an objective criterion (eval assertions / baseline diff,
#60). Probes run in an isolated ``git worktree`` so the user's working tree and
HEAD are never touched.

The binary-search core takes an injected async ``probe`` callable, so it is
fully unit-testable without git or a real workflow.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Verdict = Literal["good", "bad", "skip"]
ProbeFn = Callable[[str], Awaitable[tuple[Verdict, str]]]

_GIT_TIMEOUT_S = 30


class BisectError(Exception):
    """Setup problem: not a repo, unknown ref, bad range, dirty tree."""


@dataclass
class ProbeOutcome:
    commit: str
    verdict: Verdict
    detail: str


@dataclass
class HistoryBisectResult:
    first_bad: str | None
    probes: list[ProbeOutcome] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    indeterminate: bool = False

    @property
    def tested(self) -> int:
        return len(self.probes)


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: str) -> str:
    """Run git, returning stdout. Raises BisectError on failure."""
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BisectError(f"git {' '.join(args)} failed: {exc}") from exc
    if result.returncode != 0:
        raise BisectError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def resolve_ref(ref: str, cwd: str) -> str:
    """Resolve a ref/sha to a full commit hash."""
    return _git(["rev-parse", "--verify", f"{ref}^{{commit}}"], cwd)


def is_clean_worktree(cwd: str) -> bool:
    return _git(["status", "--porcelain"], cwd) == ""


def list_commits_between(good: str, bad: str, cwd: str) -> list[str]:
    """Commits after ``good`` up to and including ``bad``, oldest first.

    Uses ``--ancestry-path`` so only commits on the good→bad line are returned.
    Raises BisectError if ``good`` is not an ancestor of ``bad``.
    """
    out = _git(
        ["rev-list", "--ancestry-path", "--reverse", f"{good}..{bad}"], cwd,
    )
    commits = [line for line in out.splitlines() if line]
    if not commits:
        raise BisectError(
            f"no commits between {good[:12]} and {bad[:12]} "
            "(is good an ancestor of bad?)"
        )
    return commits


@contextlib.contextmanager
def worktree_at(repo_root: str, commit: str) -> Iterator[Path]:
    """Yield a temp dir containing a detached checkout of ``commit``.

    Cleaned up (and the git worktree admin entry pruned) on exit, even on error.
    """
    tmp = tempfile.mkdtemp(prefix="binex-bisect-")
    added = False
    try:
        _git(["worktree", "add", "--detach", "--force", tmp, commit], repo_root)
        added = True
        yield Path(tmp)
    finally:
        if added:
            with contextlib.suppress(BisectError):
                _git(["worktree", "remove", "--force", tmp], repo_root)
        shutil.rmtree(tmp, ignore_errors=True)
        with contextlib.suppress(BisectError):
            _git(["worktree", "prune"], repo_root)


# ---------------------------------------------------------------------------
# binary search
# ---------------------------------------------------------------------------

async def _first_testable(
    commits: list[str],
    lo: int,
    hi: int,
    mid: int,
    probe: ProbeFn,
    result: HistoryBisectResult,
    seen: dict[int, Verdict],
) -> tuple[int, Verdict] | None:
    """Probe outward from ``mid`` within [lo, hi] until a non-skip verdict.

    Returns (index, verdict) or None if every commit in the window skipped.
    Records outcomes into ``result``/``seen`` as it goes.
    """
    order = _outward_order(lo, hi, mid)
    for idx in order:
        if idx in seen:
            verdict = seen[idx]
        else:
            verdict, detail = await probe(commits[idx])
            seen[idx] = verdict
            result.probes.append(ProbeOutcome(commits[idx], verdict, detail))
            if verdict == "skip":
                result.skipped.append(commits[idx])
        if verdict != "skip":
            return idx, verdict
    return None


def _outward_order(lo: int, hi: int, mid: int) -> list[int]:
    """Indices in [lo, hi], starting at mid and spiralling outward."""
    order = [mid]
    for step in range(1, hi - lo + 1):
        if mid + step <= hi:
            order.append(mid + step)
        if mid - step >= lo:
            order.append(mid - step)
    return order


async def bisect_history(
    commits: list[str],
    probe: ProbeFn,
) -> HistoryBisectResult:
    """Find the oldest commit in ``commits`` (oldest→newest) that probes ``bad``.

    Assumes monotonicity (once bad, stays bad). ``commits`` should already
    exclude the known-good ref and include the known-bad tip. Skipped commits
    are stepped over; if a whole search window skips, the result is marked
    indeterminate.
    """
    result = HistoryBisectResult(first_bad=None)
    seen: dict[int, Verdict] = {}
    lo, hi = 0, len(commits) - 1
    answer: int | None = None

    while lo <= hi:
        mid = (lo + hi) // 2
        found = await _first_testable(commits, lo, hi, mid, probe, result, seen)
        if found is None:
            result.indeterminate = True
            break
        idx, verdict = found
        if verdict == "bad":
            answer = idx
            hi = idx - 1
        else:  # good
            lo = idx + 1

    if answer is not None:
        result.first_bad = commits[answer]
    return result


# ---------------------------------------------------------------------------
# git-backed probe (workflow eval at a commit)
# ---------------------------------------------------------------------------

def make_git_probe(
    repo_root: str,
    workflow_rel: str,
    *,
    user_vars: dict[str, str] | None = None,
    baseline: str | None = None,
    thresholds: Any = None,
    on_probe: Callable[[str, Verdict, str], None] | None = None,
) -> ProbeFn:
    """Build a ProbeFn that checks out each commit in a worktree and evals it.

    A commit whose workflow file is missing, or that errors during setup, is
    reported ``skip`` (cannot evaluate) rather than falsely blamed.
    """
    from binex.eval.golden import EvalError, run_eval

    async def _probe(commit: str) -> tuple[Verdict, str]:
        try:
            with worktree_at(repo_root, commit) as wt:
                wf_path = wt / workflow_rel
                if not wf_path.exists():
                    verdict: Verdict = "skip"
                    detail = f"workflow '{workflow_rel}' absent at this commit"
                else:
                    try:
                        report = await run_eval(
                            str(wf_path), user_vars=user_vars,
                            baseline=baseline, thresholds=thresholds,
                        )
                        verdict = "good" if report.passed else "bad"
                        detail = _probe_detail(report)
                    except EvalError as exc:
                        verdict, detail = "skip", f"cannot evaluate: {exc}"
        except BisectError as exc:
            verdict, detail = "skip", f"worktree error: {exc}"
        if on_probe is not None:
            on_probe(commit, verdict, detail)
        return verdict, detail

    return _probe


def _probe_detail(report: Any) -> str:
    if report.passed:
        return "eval passed"
    reasons = list(report.divergences)
    reasons += [f"{nid}: {err}" for nid, err in report.node_errors]
    return "; ".join(reasons) or f"run {report.run_status}"


__all__ = [
    "BisectError",
    "HistoryBisectResult",
    "ProbeFn",
    "ProbeOutcome",
    "Verdict",
    "bisect_history",
    "is_clean_worktree",
    "list_commits_between",
    "make_git_probe",
    "resolve_ref",
    "worktree_at",
]
