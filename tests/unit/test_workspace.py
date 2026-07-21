"""Unit tests for the git-backed workspace, jailing, tools, and RW lock (#75)."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from binex.runtime.rwlock import AsyncRWLock
from binex.runtime.workspace import Workspace, WorkspaceConfig, WorkspaceError
from binex.runtime.workspace_tools import make_workspace_tools


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace.create("run_t", WorkspaceConfig(), base_dir=str(tmp_path))


# -- config ---------------------------------------------------------------

def test_config_from_obj_variants() -> None:
    assert WorkspaceConfig.from_obj(None) is None
    assert WorkspaceConfig.from_obj("some/dir").source == "copy"
    c = WorkspaceConfig.from_obj({"source": "git", "path": "u", "ref": "main"})
    assert c.source == "git" and c.ref == "main"


# -- lifecycle & snapshots ------------------------------------------------

def test_create_is_a_git_repo_with_baseline(ws: Workspace) -> None:
    assert (ws.root / ".git").is_dir()
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=ws.root, capture_output=True, text=True,
    ).stdout
    assert "workspace: baseline" in log


def test_snapshot_per_node_and_files_changed(ws: Workspace) -> None:
    ws.write_file("src/a.py", "x")
    sha = ws.snapshot("coder")
    assert sha is not None
    assert ws.files_changed("coder") == ["src/a.py"]

    ws.write_file("assets/b.txt", "y")
    ws.snapshot("designer")
    assert ws.files_changed("designer") == ["assets/b.txt"]


def test_snapshot_no_change_returns_none(ws: Workspace) -> None:
    ws.write_file("a.txt", "1")
    ws.snapshot("n1")
    assert ws.snapshot("n2") is None  # nothing changed since n1
    assert ws.commits["n2"] == ws.commits["n1"]  # points at same HEAD


def test_restore_resets_working_tree(ws: Workspace) -> None:
    ws.write_file("keep.txt", "1")
    ws.snapshot("first")
    ws.write_file("later.txt", "2")
    ws.snapshot("second")
    assert "later.txt" in ws.list_files()
    ws.restore("first")
    assert "later.txt" not in ws.list_files()
    assert "keep.txt" in ws.list_files()


def test_seed_copy(tmp_path: Path) -> None:
    src = tmp_path / "seed"
    src.mkdir()
    (src / "given.txt").write_text("hi")
    ws = Workspace.create(
        "run_c", WorkspaceConfig(source="copy", path=str(src)),
        base_dir=str(tmp_path / "wsroot"),
    )
    assert "given.txt" in ws.list_files()


def test_seed_copy_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="not found"):
        Workspace.create(
            "run_c", WorkspaceConfig(source="copy", path=str(tmp_path / "nope")),
            base_dir=str(tmp_path / "wsroot"),
        )


# -- jailing (security-critical) ------------------------------------------

@pytest.mark.parametrize("bad", [
    "../escape", "../../etc/passwd", "src/../../x", "/etc/passwd", "/abs",
])
def test_jailing_blocks_escape(ws: Workspace, bad: str) -> None:
    with pytest.raises(WorkspaceError):
        ws.resolve(bad)


def test_jailing_symlink_escape(ws: Workspace, tmp_path: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("SECRET")
    (ws.root / "link").symlink_to(outside)
    with pytest.raises(WorkspaceError):
        ws.resolve("link")


def test_write_over_size_limit(ws: Workspace) -> None:
    with pytest.raises(WorkspaceError, match="10MB"):
        ws.write_file("big.bin", "x" * (10 * 1024 * 1024 + 1))


def test_list_files_excludes_git(ws: Workspace) -> None:
    ws.write_file("a.txt", "1")
    files = ws.list_files()
    assert "a.txt" in files
    assert not any(".git" in f for f in files)


# -- workspace tools ------------------------------------------------------

def test_workspace_tools_read_write_list(ws: Workspace) -> None:
    tools = {t.name: t for t in make_workspace_tools(ws)}
    assert set(tools) == {"read_file", "write_file", "list_files"}

    assert "Written" in tools["write_file"].callable(path="d/x.txt", content="hi")
    assert tools["read_file"].callable(path="d/x.txt") == "hi"
    assert "d/x.txt" in tools["list_files"].callable()


def test_workspace_tools_reject_escape(ws: Workspace) -> None:
    tools = {t.name: t for t in make_workspace_tools(ws)}
    out = tools["write_file"].callable(path="../evil.txt", content="x")
    assert out.startswith("Error")
    assert tools["read_file"].callable(path="../../etc/passwd").startswith("Error")


def test_workspace_tools_missing_file(ws: Workspace) -> None:
    tools = {t.name: t for t in make_workspace_tools(ws)}
    assert "not found" in tools["read_file"].callable(path="nope.txt")


# -- RW lock --------------------------------------------------------------

@pytest.mark.asyncio
async def test_rwlock_writers_are_exclusive() -> None:
    lock = AsyncRWLock()
    order: list[str] = []

    async def writer(tag: str) -> None:
        async with lock.write():
            order.append(f"{tag}-start")
            await asyncio.sleep(0.02)
            order.append(f"{tag}-end")

    await asyncio.gather(writer("a"), writer("b"))
    # No interleaving: each writer's start/end are adjacent.
    assert order in (
        ["a-start", "a-end", "b-start", "b-end"],
        ["b-start", "b-end", "a-start", "a-end"],
    )


def test_validate_workspace_access_requires_declaration() -> None:
    from binex.models.workflow import NodeSpec, WorkflowSpec
    from binex.workflow_spec.validator import validate_workflow

    spec = WorkflowSpec(name="t", nodes={
        "n": NodeSpec(id="n", agent="llm://x", outputs=["o"], workspace="write"),
    })
    errors = validate_workflow(spec)
    assert any("requires the workflow to declare" in e for e in errors)

    spec_ok = WorkflowSpec(name="t", workspace={"source": "empty"}, nodes={
        "n": NodeSpec(id="n", agent="llm://x", outputs=["o"], workspace="write"),
    })
    assert not any("workspace" in e for e in validate_workflow(spec_ok))


def test_clean_workspaces_command(tmp_path, monkeypatch) -> None:
    from click.testing import CliRunner

    from binex.cli.clean import clean_group

    monkeypatch.chdir(tmp_path)
    base = tmp_path / ".binex" / "workspaces"
    base.mkdir(parents=True)
    (base / "run_a").mkdir()
    (base / "run_b").mkdir()

    runner = CliRunner()
    dry = runner.invoke(clean_group, ["workspaces", "--dry-run"])
    assert "2 workspace" in dry.output
    assert (base / "run_a").exists()  # dry-run deletes nothing

    real = runner.invoke(clean_group, ["workspaces"])
    assert "Deleted 2 workspaces" in real.output
    assert not (base / "run_a").exists()


@pytest.mark.asyncio
async def test_rwlock_readers_share() -> None:
    lock = AsyncRWLock()
    active = 0
    peak = 0

    async def reader() -> None:
        nonlocal active, peak
        async with lock.read():
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1

    await asyncio.gather(*[reader() for _ in range(3)])
    assert peak == 3  # all three read concurrently
