"""Tests for binary artifacts: blobs, envelopes, LLM routing, GC (#76)."""

from __future__ import annotations

from pathlib import Path

import pytest

from binex.adapters.llm import LLMAdapter
from binex.artifacts.binary import (
    binary_descriptor,
    blob_dir,
    is_binary_artifact,
    load_blob,
    make_binary_artifact,
    store_blob,
    to_data_uri,
)
from binex.models.task import TaskNode

_PNG = b"\x89PNG\r\n\x1a\n" + b"pixels" * 20


@pytest.fixture(autouse=True)
def _store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BINEX_STORE_PATH", str(tmp_path / ".binex"))
    return tmp_path


def _make(mime: str = "image/png", data: bytes = _PNG, node: str = "gen"):
    return make_binary_artifact("run1", node, data, mime)


# -- envelope & blob -------------------------------------------------------

def test_make_binary_artifact_envelope() -> None:
    art = _make()
    assert is_binary_artifact(art)
    env = art.content
    assert env["kind"] == "binary"
    assert env["mime"] == "image/png"
    assert env["size"] == len(_PNG)
    assert len(env["sha256"]) == 64
    assert Path(env["path"]).exists()


def test_content_addressed_dedup() -> None:
    a = _make(node="n1")
    b = _make(node="n2")  # identical bytes
    assert a.content["sha256"] == b.content["sha256"]
    assert len(list(blob_dir().iterdir())) == 1  # stored once


def test_different_bytes_distinct_blobs() -> None:
    _make(data=b"aaaa")
    _make(data=b"bbbb")
    assert len(list(blob_dir().iterdir())) == 2


def test_load_roundtrip() -> None:
    art = _make()
    assert load_blob(art.content) == _PNG


def test_size_limit() -> None:
    with pytest.raises(ValueError, match="exceeds limit"):
        store_blob(b"x" * 11, max_bytes=10)


def test_json_artifact_is_not_binary() -> None:
    from binex.models.artifact import Artifact, Lineage
    art = Artifact(id="a", run_id="r", type="result", content={"x": 1},
                   lineage=Lineage(produced_by="n"))
    assert not is_binary_artifact(art)


def test_descriptor_and_data_uri() -> None:
    art = _make()
    d = binary_descriptor(art.content, "gen")
    assert "image/png" in d and "gen" in d
    assert to_data_uri(art.content).startswith("data:image/png;base64,")


# -- LLM routing -----------------------------------------------------------

def _task() -> TaskNode:
    return TaskNode(id="t", run_id="r", node_id="n", agent="llm://x",
                    inputs={}, config={})


def test_vision_model_gets_multimodal() -> None:
    adapter = LLMAdapter(model="gpt-4o")
    content = adapter._build_user_content(_task(), [_make()])
    assert isinstance(content, list)
    assert any(p.get("type") == "image_url" for p in content)


def test_non_vision_model_gets_descriptor() -> None:
    adapter = LLMAdapter(model="gpt-3.5-turbo")
    content = adapter._build_user_content(_task(), [_make()])
    assert isinstance(content, str)
    assert "binary artifact" in content


def test_audio_binary_is_descriptor_even_for_vision() -> None:
    adapter = LLMAdapter(model="gpt-4o")
    content = adapter._build_user_content(_task(), [_make(mime="audio/wav")])
    # Non-image binary → descriptor only, no image parts.
    assert isinstance(content, str)
    assert "audio/wav" in content


def test_json_and_binary_mixed_inputs() -> None:
    from binex.models.artifact import Artifact, Lineage
    adapter = LLMAdapter(model="gpt-4o")
    json_art = Artifact(id="j", run_id="r", type="result", content="hello world",
                        lineage=Lineage(produced_by="planner"))
    content = adapter._build_user_content(_task(), [json_art, _make()])
    assert isinstance(content, list)
    text = content[0]["text"]
    assert "hello world" in text  # json input preserved as text


# -- blob GC ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_clean_blobs_gc(tmp_path: Path) -> None:
    import os

    from binex.artifacts.binary import store_blob
    from binex.cli.clean import _clean_blobs
    from binex.models.execution import RunSummary
    from binex.stores import create_artifact_store, create_execution_store
    sp = os.environ["BINEX_STORE_PATH"]
    exec_store = create_execution_store(backend="sqlite", db_path=sp + "/e.db")
    art_store = create_artifact_store(backend="filesystem", base_path=sp + "/artifacts")

    # One referenced blob (via a stored run artifact) and one orphan.
    referenced = make_binary_artifact("run_ref", "gen", _PNG, "image/png")
    await exec_store.create_run(RunSummary(
        run_id="run_ref", workflow_name="w", status="completed", total_nodes=1,
    ))
    await art_store.store(referenced)
    store_blob(b"orphan-bytes")  # not attached to any run
    await exec_store.close()

    assert len(list(blob_dir().iterdir())) == 2

    # Patch clean's store getter to our stores.
    import binex.cli.clean as clean_mod
    clean_mod._get_stores = lambda: (
        create_execution_store(backend="sqlite", db_path=sp + "/e.db"),
        create_artifact_store(backend="filesystem", base_path=sp + "/artifacts"),
    )
    await _clean_blobs(dry_run=False)

    remaining = {p.name for p in blob_dir().iterdir()}
    assert referenced.content["sha256"] in remaining
    assert len(remaining) == 1  # orphan collected
