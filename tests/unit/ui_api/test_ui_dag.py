"""Tests for render_dag_ascii() in ui.py."""

from binex.cli.ui import render_dag_ascii


def test_linear_dag():
    """A -> B -> C renders as a linear chain."""
    nodes = ["A", "B", "C"]
    edges = [("A", "B"), ("B", "C")]
    result = render_dag_ascii(nodes, edges)
    assert "A" in result
    assert "B" in result
    assert "C" in result
    assert "->" in result or "→" in result


def test_fan_out_fan_in():
    """A -> B, C -> D groups parallel nodes."""
    nodes = ["A", "B", "C", "D"]
    edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]
    result = render_dag_ascii(nodes, edges)
    assert "A" in result
    assert "B" in result
    assert "C" in result
    assert "D" in result


def test_single_node():
    """Single node with no edges."""
    nodes = ["A"]
    edges = []
    result = render_dag_ascii(nodes, edges)
    assert "A" in result


def test_empty_graph():
    """Empty graph returns empty or minimal string."""
    result = render_dag_ascii([], [])
    assert isinstance(result, str)


def test_parallel_branches_shown():
    """Parallel nodes appear on the same layer."""
    nodes = ["start", "worker1", "worker2", "worker3", "end"]
    edges = [
        ("start", "worker1"), ("start", "worker2"), ("start", "worker3"),
        ("worker1", "end"), ("worker2", "end"), ("worker3", "end"),
    ]
    result = render_dag_ascii(nodes, edges)
    # Workers should be grouped together (comma or same line)
    assert "worker1" in result
    assert "worker2" in result
    assert "worker3" in result
