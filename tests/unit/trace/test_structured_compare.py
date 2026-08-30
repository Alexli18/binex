"""Structured artifact content must be compared by field, not as `str(dict)`.

`SequenceMatcher.ratio()` measures how many *characters* moved, which is close to
orthogonal to "did the meaning change" — and on structured output it is actively
anti-correlated. Measured on the previous code path:

    JSON, same meaning, reordered keys   0.636  -> flagged as divergence
    JSON, "approved" -> "rejected"       0.915  -> passed as a match
    JSON, is_safe True -> False          0.948  -> passed as a match

Artifact.content is usually a dict already, so the structure is available and
throwing it away is what causes both error classes. These tests pin the
field-wise comparison that replaces it.
"""

from __future__ import annotations

import pytest

from binex.trace._compare import compare_contents, content_similarity


class TestStructuralEquality:
    def test_reordered_keys_are_identical(self):
        """The bug: same mapping, different literal order, was scored 0.636."""
        a = {"revenue": 12, "costs": 3, "verdict": "ok"}
        b = {"verdict": "ok", "costs": 3, "revenue": 12}

        similarity, changes = compare_contents(a, b)

        assert similarity == 1.0
        assert changes == []

    def test_identical_nested_structures(self):
        a = {"totals": {"q1": 10, "q2": 20}, "tags": ["x", "y"]}
        b = {"totals": {"q1": 10, "q2": 20}, "tags": ["x", "y"]}

        similarity, changes = compare_contents(a, b)

        assert similarity == 1.0
        assert changes == []


class TestFieldChanges:
    def test_single_changed_value_is_reported(self):
        """The other bug: a flipped verdict was scored 0.915 and passed."""
        a = {"decision": "approved", "reason": "all checks passed"}
        b = {"decision": "rejected", "reason": "all checks passed"}

        similarity, changes = compare_contents(a, b)

        assert similarity == 0.5  # 1 of 2 leaves unchanged
        assert len(changes) == 1
        change = changes[0]
        assert change.path == "decision"
        assert change.before == "approved"
        assert change.after == "rejected"
        assert change.kind == "changed"

    def test_boolean_flip_is_reported(self):
        a = {"is_safe": True, "score": 0.91, "notes": "no policy violations"}
        b = {"is_safe": False, "score": 0.91, "notes": "no policy violations"}

        similarity, changes = compare_contents(a, b)

        assert similarity == pytest.approx(2 / 3)
        assert [c.path for c in changes] == ["is_safe"]

    def test_added_key(self):
        similarity, changes = compare_contents({"a": 1}, {"a": 1, "b": 2})

        assert similarity == 0.5
        assert len(changes) == 1
        assert changes[0].path == "b"
        assert changes[0].kind == "added"
        assert changes[0].after == 2

    def test_removed_key(self):
        similarity, changes = compare_contents({"a": 1, "b": 2}, {"a": 1})

        assert len(changes) == 1
        assert changes[0].path == "b"
        assert changes[0].kind == "removed"
        assert changes[0].before == 2

    def test_nested_path_is_dotted(self):
        a = {"totals": {"q1": 10, "q2": 20}}
        b = {"totals": {"q1": 10, "q2": 99}}

        _, changes = compare_contents(a, b)

        assert [c.path for c in changes] == ["totals.q2"]

    def test_list_path_uses_index(self):
        a = {"items": [{"name": "alpha"}, {"name": "beta"}]}
        b = {"items": [{"name": "alpha"}, {"name": "GAMMA"}]}

        _, changes = compare_contents(a, b)

        assert [c.path for c in changes] == ["items[1].name"]

    def test_changes_are_ordered_by_path(self):
        a = {"z": 1, "a": 1, "m": 1}
        b = {"z": 2, "a": 2, "m": 2}

        _, changes = compare_contents(a, b)

        assert [c.path for c in changes] == ["a", "m", "z"]


class TestTextFallback:
    def test_plain_strings_use_sequence_matcher(self):
        """Prose is item (2)'s problem — this change must not touch it."""
        a = "The report is ready. Revenue grew 12% this quarter."
        b = "The report is done. Revenue increased 12% over the quarter."

        similarity, changes = compare_contents(a, b)

        assert changes is None
        assert similarity == pytest.approx(content_similarity(a, b))

    def test_mixed_structured_and_text_falls_back(self):
        similarity, changes = compare_contents({"a": 1}, "not a mapping")

        assert changes is None
        assert 0.0 <= similarity <= 1.0

    def test_both_none_is_identical(self):
        similarity, changes = compare_contents(None, None)

        assert similarity == 1.0
        assert changes is None

    def test_empty_structures_are_identical(self):
        similarity, changes = compare_contents({}, {})

        assert similarity == 1.0
        assert changes == []


class TestRenderedChange:
    def test_change_renders_before_and_after(self):
        _, changes = compare_contents(
            {"decision": "approved"}, {"decision": "rejected"},
        )

        rendered = changes[0].render()

        assert "decision" in rendered
        assert "approved" in rendered
        assert "rejected" in rendered
