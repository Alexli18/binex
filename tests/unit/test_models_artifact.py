"""Tests for Artifact, ArtifactRef, and Lineage models."""

from datetime import UTC, datetime

from binex.models.artifact import Artifact, ArtifactRef, Lineage


class TestLineage:
    def test_create(self) -> None:
        lineage = Lineage(produced_by="planner")
        assert lineage.produced_by == "planner"
        assert lineage.derived_from == []

    def test_with_derived_from(self) -> None:
        lineage = Lineage(produced_by="validator", derived_from=["art1", "art2"])
        assert lineage.derived_from == ["art1", "art2"]


class TestArtifact:
    def test_create_minimal(self) -> None:
        a = Artifact(
            id="art_01",
            run_id="run_01",
            type="execution_plan",
            lineage=Lineage(produced_by="planner"),
        )
        assert a.id == "art_01"
        assert a.status == "complete"
        assert a.content is None
        assert isinstance(a.created_at, datetime)

    def test_create_full(self) -> None:
        a = Artifact(
            id="art_02",
            run_id="run_01",
            type="search_results",
            content={"results": [1, 2, 3]},
            status="partial",
            lineage=Lineage(produced_by="researcher", derived_from=["art_01"]),
        )
        assert a.status == "partial"
        assert a.content == {"results": [1, 2, 3]}
        assert a.lineage.derived_from == ["art_01"]

    def test_created_at_is_utc(self) -> None:
        a = Artifact(
            id="a", run_id="r", type="t", lineage=Lineage(produced_by="p")
        )
        assert a.created_at.tzinfo == UTC


class TestArtifactRef:
    def test_create(self) -> None:
        ref = ArtifactRef(artifact_id="art_01", type="execution_plan")
        assert ref.artifact_id == "art_01"
        assert ref.type == "execution_plan"
