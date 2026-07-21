"""Workspace — a shared, git-snapshotted filesystem for multi-agent runs (#75).

Many workflows are agents collaborating on an *accumulating body of files* (a
codebase, a document set) rather than passing small JSON artifacts. A run can
declare a workspace; it lives at ``.binex/workspaces/<run_id>/`` and **is itself
a git repository**. After each node completes, an automatic commit tagged with
the node id gives, for free: per-node file diffs, file-level lineage, rollback,
and restore points for replay/resume.

Path access is **jailed** to the workspace root — no traversal, no absolute
paths, symlink escapes collapsed by ``resolve()``. This is security-critical in
combination with ``shell_command`` (#58).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

DEFAULT_BASE_DIR = ".binex/workspaces"
_MAX_FILE_BYTES = 10 * 1024 * 1024
_GIT_TIMEOUT_S = 30


class WorkspaceError(Exception):
    """Invalid workspace path (traversal/escape) or a git/seed failure."""


@dataclass
class WorkspaceConfig:
    """Workflow-level workspace declaration."""

    source: Literal["empty", "copy", "git"] = "empty"
    path: str | None = None  # local dir to copy, or git URL to clone
    ref: str | None = None   # git ref/branch/sha for source=git

    @classmethod
    def from_obj(cls, obj: object) -> WorkspaceConfig | None:
        if obj is None:
            return None
        if isinstance(obj, WorkspaceConfig):
            return obj
        if isinstance(obj, str):
            return cls(source="copy", path=obj) if obj else cls()
        if isinstance(obj, dict):
            return cls(
                source=obj.get("source", "empty"),
                path=obj.get("path"),
                ref=obj.get("ref"),
            )
        raise WorkspaceError(f"invalid workspace config: {obj!r}")


def _git(args: list[str], cwd: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=_GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkspaceError(f"git {' '.join(args)} failed: {exc}") from exc
    if result.returncode != 0:
        raise WorkspaceError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


@dataclass
class Workspace:
    """A per-run git-backed working directory with jailed file access."""

    run_id: str
    root: Path
    commits: dict[str, str] = field(default_factory=dict)  # node_id -> commit sha

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def create(
        cls, run_id: str, config: WorkspaceConfig,
        base_dir: str = DEFAULT_BASE_DIR,
    ) -> Workspace:
        """Materialize the workspace: seed it, then ``git init`` + baseline commit."""
        root = Path(base_dir) / run_id
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        ws = cls(run_id=run_id, root=root)
        ws._seed(config)
        ws._init_git()
        return ws

    def _seed(self, config: WorkspaceConfig) -> None:
        if config.source == "empty":
            return
        if config.source == "copy":
            if not config.path or not Path(config.path).is_dir():
                raise WorkspaceError(
                    f"workspace copy source not found: {config.path}"
                )
            shutil.copytree(config.path, self.root, dirs_exist_ok=True)
        elif config.source == "git":
            if not config.path:
                raise WorkspaceError("workspace source=git requires a path (URL)")
            _git(["clone", config.path, str(self.root)], cwd=".")
            if config.ref:
                _git(["checkout", config.ref], cwd=str(self.root))
        else:
            raise WorkspaceError(f"unknown workspace source: {config.source}")

    def _init_git(self) -> None:
        # A cloned repo already has git; re-init is a no-op that also works for
        # empty/copy sources. Configure identity so commits never fail on CI.
        if not (self.root / ".git").exists():
            _git(["init"], cwd=str(self.root))
        _git(["config", "user.email", "binex@localhost"], cwd=str(self.root))
        _git(["config", "user.name", "binex"], cwd=str(self.root))
        _git(["add", "-A"], cwd=str(self.root))
        # Baseline commit (allow-empty so an empty workspace still has HEAD).
        _git(["commit", "--allow-empty", "-m", "workspace: baseline"],
             cwd=str(self.root))

    # -- snapshots ---------------------------------------------------------

    def snapshot(self, node_id: str) -> str | None:
        """Commit the workspace state after ``node_id``. Returns the sha, or None
        if the node changed nothing.
        """
        _git(["add", "-A"], cwd=str(self.root))
        status = _git(["status", "--porcelain"], cwd=str(self.root))
        if not status:
            # No change — point this node at the current HEAD for restore lookup.
            sha = _git(["rev-parse", "HEAD"], cwd=str(self.root))
            self.commits[node_id] = sha
            return None
        _git(["commit", "-m", f"node: {node_id}"], cwd=str(self.root))
        sha = _git(["rev-parse", "HEAD"], cwd=str(self.root))
        self.commits[node_id] = sha
        return sha

    def diff(self, from_sha: str, to_sha: str = "HEAD") -> str:
        """Unified diff of file changes between two snapshots."""
        return _git(["diff", from_sha, to_sha], cwd=str(self.root))

    def files_changed(self, node_id: str) -> list[str]:
        """Paths changed by ``node_id`` (that node's commit vs its parent)."""
        sha = self.commits.get(node_id)
        if sha is None:
            return []
        out = _git(
            ["show", "--name-only", "--pretty=format:", sha], cwd=str(self.root),
        )
        return [line for line in out.splitlines() if line]

    def restore(self, node_id: str) -> None:
        """Reset the working tree to the state as of ``node_id`` (for replay/resume)."""
        sha = self.commits.get(node_id)
        if sha is None:
            raise WorkspaceError(f"no snapshot for node '{node_id}'")
        _git(["reset", "--hard", sha], cwd=str(self.root))
        _git(["clean", "-fd"], cwd=str(self.root))

    # -- jailed file access -----------------------------------------------

    def resolve(self, rel: str) -> Path:
        """Resolve ``rel`` inside the workspace, or raise WorkspaceError on escape.

        Rejects absolute paths and any target that resolves outside the root
        (``..`` and symlinks are collapsed by ``resolve()`` first).
        """
        if os.path.isabs(rel):
            raise WorkspaceError("absolute paths are not allowed")
        root = self.root.resolve()
        target = (root / rel).resolve()
        if target != root and root not in target.parents:
            raise WorkspaceError(f"path escapes the workspace: {rel!r}")
        return target

    def read_file(self, path: str) -> str:
        return self.resolve(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> int:
        if len(content.encode()) > _MAX_FILE_BYTES:
            raise WorkspaceError("content exceeds the 10MB file limit")
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return len(content)

    def list_files(self, subdir: str = ".") -> list[str]:
        base = self.resolve(subdir)
        if not base.exists():
            return []
        root = self.root.resolve()
        return sorted(
            str(p.relative_to(root)) for p in base.rglob("*")
            if p.is_file() and ".git" not in p.parts
        )

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def list_node_changes(
    run_id: str, base_dir: str = DEFAULT_BASE_DIR,
) -> dict[str, list[str]] | None:
    """Reconstruct per-node file changes from a finished run's workspace (#75 UI).

    The in-memory node→commit map is gone after the run, so read it back from the
    workspace repo: each ``node: <id>`` commit's changed files vs its parent.
    Returns ``None`` when the run has no workspace.
    """
    root = Path(base_dir) / run_id
    if not (root / ".git").exists():
        return None
    out = _git(["log", "--reverse", "--pretty=format:%H%x09%s"], cwd=str(root))
    changes: dict[str, list[str]] = {}
    for line in out.splitlines():
        sha, _, subject = line.partition("\t")
        if not subject.startswith("node: "):
            continue
        node_id = subject[len("node: "):]
        files = _git(
            ["show", "--name-only", "--pretty=format:", sha], cwd=str(root),
        )
        changes[node_id] = [f for f in files.splitlines() if f]
    return changes


__all__ = [
    "DEFAULT_BASE_DIR",
    "Workspace",
    "WorkspaceConfig",
    "WorkspaceError",
    "list_node_changes",
]
