"""Tests for DSL parser (T019-T021)."""

from __future__ import annotations

import pytest

from binex.cli.dsl_parser import PATTERNS, parse_dsl


class TestParseDSL:
    """T019: Core DSL parsing."""

    def test_parse_linear(self) -> None:
        result = parse_dsl(["A -> B -> C"])
        assert result.nodes == ["A", "B", "C"]
        assert ("A", "B") in result.edges
        assert ("B", "C") in result.edges
        assert len(result.edges) == 2
        assert result.depends_on == {"A": [], "B": ["A"], "C": ["B"]}

    def test_parse_fan_out(self) -> None:
        result = parse_dsl(["A -> B, C, D"])
        assert result.nodes == ["A", "B", "C", "D"]
        assert ("A", "B") in result.edges
        assert ("A", "C") in result.edges
        assert ("A", "D") in result.edges
        assert result.depends_on["B"] == ["A"]
        assert result.depends_on["C"] == ["A"]
        assert result.depends_on["D"] == ["A"]

    def test_parse_fan_in(self) -> None:
        result = parse_dsl(["A, B -> C"])
        assert result.nodes == ["A", "B", "C"]
        assert ("A", "C") in result.edges
        assert ("B", "C") in result.edges
        assert sorted(result.depends_on["C"]) == ["A", "B"]

    def test_parse_diamond(self) -> None:
        result = parse_dsl(["A -> B, C -> D"])
        assert result.nodes == ["A", "B", "C", "D"]
        assert ("A", "B") in result.edges
        assert ("A", "C") in result.edges
        assert ("B", "D") in result.edges
        assert ("C", "D") in result.edges
        assert result.depends_on["A"] == []
        assert result.depends_on["B"] == ["A"]
        assert result.depends_on["C"] == ["A"]
        assert sorted(result.depends_on["D"]) == ["B", "C"]

    def test_parse_multiple_dsl(self) -> None:
        result = parse_dsl(["A -> B", "B -> C"])
        assert result.nodes == ["A", "B", "C"]
        assert ("A", "B") in result.edges
        assert ("B", "C") in result.edges
        assert result.depends_on == {"A": [], "B": ["A"], "C": ["B"]}

    def test_parse_whitespace_tolerance(self) -> None:
        result = parse_dsl(["  A  ->  B ,  C  ->  D  "])
        assert result.nodes == ["A", "B", "C", "D"]

    def test_parse_single_node(self) -> None:
        result = parse_dsl(["A"])
        assert result.nodes == ["A"]
        assert result.edges == []
        assert result.depends_on == {"A": []}

    def test_parse_dedup_nodes(self) -> None:
        """Multiple DSL strings with overlapping nodes should deduplicate."""
        result = parse_dsl(["A -> B", "A -> C"])
        assert result.nodes.count("A") == 1


class TestDSLValidation:
    """T020: DSL validation."""

    def test_parse_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_dsl([])

    def test_parse_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_dsl([""])

    def test_parse_malformed_arrow_raises(self) -> None:
        with pytest.raises(ValueError, match="[Ee]mpty.*node|[Mm]alformed"):
            parse_dsl(["-> ->"])

    def test_parse_trailing_arrow_raises(self) -> None:
        with pytest.raises(ValueError, match="[Ee]mpty.*node|[Mm]alformed"):
            parse_dsl(["A ->"])

    def test_parse_leading_arrow_raises(self) -> None:
        with pytest.raises(ValueError, match="[Ee]mpty.*node|[Mm]alformed"):
            parse_dsl(["-> A"])

    def test_parse_empty_node_name_raises(self) -> None:
        with pytest.raises(ValueError, match="[Ee]mpty.*node|[Mm]alformed"):
            parse_dsl(["A -> , -> B"])


class TestPredefinedPatterns:
    """T021: Predefined patterns."""

    def test_patterns_count(self) -> None:
        assert len(PATTERNS) == 17

    def test_patterns_all_valid(self) -> None:
        for name, dsl in PATTERNS.items():
            result = parse_dsl([dsl])
            assert len(result.nodes) > 0, f"Pattern '{name}' produced no nodes"
            # Every pattern should have at least one edge (all are multi-node)
            assert len(result.edges) > 0, f"Pattern '{name}' produced no edges"

    def test_pattern_linear(self) -> None:
        result = parse_dsl([PATTERNS["linear"]])
        assert result.nodes == ["A", "B", "C"]

    def test_pattern_fan_out(self) -> None:
        result = parse_dsl([PATTERNS["fan-out"]])
        assert "planner" in result.nodes
        assert len(result.depends_on["planner"]) == 0

    def test_pattern_diamond(self) -> None:
        result = parse_dsl([PATTERNS["diamond"]])
        assert len(result.nodes) == 4
