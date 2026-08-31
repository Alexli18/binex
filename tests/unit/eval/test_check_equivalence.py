"""The same check must mean the same thing in both eval entry points.

Binex has two places to write a check: a per-node `assertions:` block in the
workflow (enforced on every run) and a per-case `asserts:` list in an eval suite.
They were built separately and disagreed on how an artifact becomes text —
`str(dict)` versus `json.dumps` — so for a mapping artifact:

    contains: '"decision"'   passed in a suite, failed as a node assertion
    contains: "'decision'"   did the opposite

Same YAML intent, opposite verdicts. These tests pin the shared engine that
removes the difference: JSON is canonical, because it is what the user sees in
artifacts and in `--json`, and it is the form `json_path` can address.
"""

from __future__ import annotations

import pytest

from binex.eval.checks import stringify

MAPPING = {"decision": "approved", "score": 0.91}


class TestStringify:
    def test_mapping_becomes_json_not_python_repr(self):
        rendered = stringify(MAPPING)

        assert '"decision"' in rendered
        assert "'decision'" not in rendered

    def test_list_becomes_json(self):
        assert stringify(["a", "b"]) == '["a", "b"]'

    def test_string_passes_through_untouched(self):
        assert stringify("plain text") == "plain text"

    def test_none_is_empty(self):
        assert stringify(None) == ""

    def test_scalars_render_without_quotes_being_invented(self):
        assert stringify(42) == "42"
        assert stringify(True) == "true"

    def test_output_is_parseable_json_for_structured_content(self):
        """json_path asserts address this string — it has to be valid JSON."""
        import json

        assert json.loads(stringify(MAPPING)) == MAPPING


class TestCrossSystemEquivalence:
    """A check written either way sees identical text."""

    @pytest.mark.parametrize(
        "needle,expected",
        [
            ('"decision"', True),   # JSON quoting — used to work only in suites
            ("'decision'", False),  # Python quoting — used to work only in nodes
            ("approved", True),
            ("rejected", False),
        ],
    )
    def test_contains_agrees_on_a_mapping(self, needle: str, expected: bool):
        from binex.eval.checks import check_contains

        rendered = stringify(MAPPING)

        assert check_contains(rendered, needle) is expected

    def test_not_contains_is_the_negation_of_contains(self):
        from binex.eval.checks import check_contains, check_not_contains

        rendered = stringify(MAPPING)

        for needle in ('"decision"', "nope", "approved"):
            assert check_not_contains(rendered, needle) is not check_contains(
                rendered, needle
            )

    def test_regex_agrees_on_a_mapping(self):
        from binex.eval.checks import check_regex

        rendered = stringify(MAPPING)

        assert check_regex(rendered, r'"decision":\s*"approved"') is True
        assert check_regex(rendered, r"'decision'") is False
