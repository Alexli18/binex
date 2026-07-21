"""Capture git provenance for a run (issue #72).

Recording the commit a workflow ran at is the cheap half of history bisect: it
lets ``binex bisect history`` (and plain forensics) map runs to commits. Best
effort — a missing git, a non-repo directory, or any error yields
``(None, False)`` rather than failing the run.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_TIMEOUT_S = 5


def _run_git(args: list[str], cwd: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def capture_git_meta(path: str | None = None) -> tuple[str | None, bool]:
    """Return ``(sha, dirty)`` for the repo containing ``path`` (or CWD).

    ``sha`` is the full HEAD commit hash, or ``None`` outside a git repo / on any
    error. ``dirty`` is ``True`` when the working tree has uncommitted changes.
    """
    cwd = str(_resolve_dir(path))
    sha = _run_git(["rev-parse", "HEAD"], cwd)
    if sha is None:
        return None, False
    status = _run_git(["status", "--porcelain"], cwd)
    dirty = bool(status)  # non-empty porcelain output = uncommitted changes
    return sha, dirty


def _resolve_dir(path: str | None) -> Path:
    """Directory to run git in: the file's parent, the dir itself, or CWD."""
    if not path:
        return Path.cwd()
    p = Path(path)
    if p.is_file():
        return p.parent
    if p.is_dir():
        return p
    return Path.cwd()


__all__ = ["capture_git_meta"]
