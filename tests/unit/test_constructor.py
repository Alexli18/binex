"""Tests for DAG constructor in binex start wizard."""

from binex.cli.start_constructor import (
    _constructor_add_node,
    _constructor_delete_node,
    _constructor_edit_node,
    _constructor_loop,
)


def test_constructor_shows_graph():
    """Constructor displays DAG with node names."""
    output_lines = []

    def capture(msg="", **kw):
        output_lines.append(str(msg))

    from unittest.mock import patch

    nodes_config = {
        "A": {"agent": "llm://test/m", "outputs": ["result"]},
        "B": {"agent": "llm://test/m", "outputs": ["result"], "depends_on": ["A"]},
    }
    edges = [("A", "B")]

    inputs = iter(["done"])
    with patch("click.echo", side_effect=capture):
        with patch("binex.cli.start.has_rich", return_value=False):
            _constructor_loop(
                nodes_config, edges, input_fn=lambda _: next(inputs),
            )
    combined = "\n".join(output_lines)
    assert "A" in combined
    assert "B" in combined


def test_constructor_add_node():
    """Add action increases node count."""
    nodes_config = {
        "A": {"agent": "llm://test/m", "outputs": ["result"]},
    }
    edges = []

    # Add node: name=NewNode, role selection=1, agent type=1, provider=1, model=default
    inputs = iter([
        "NewNode",  # node name
        "1",  # select first bundled prompt
        "1",  # agent type LLM
        "1",  # provider
        "",  # default model
        "",  # depends on (none)
    ])

    from unittest.mock import patch
    with patch("binex.cli.start.has_rich", return_value=False):
        new_nodes, new_edges = _constructor_add_node(
            nodes_config, edges, input_fn=lambda p: next(inputs),
        )
    assert len(new_nodes) == 2
    assert "NewNode" in new_nodes


def test_constructor_delete_node():
    """Delete removes node and its edges."""
    nodes_config = {
        "A": {"agent": "llm://test/m", "outputs": ["result"]},
        "B": {"agent": "llm://test/m", "outputs": ["result"], "depends_on": ["A"]},
        "C": {"agent": "llm://test/m", "outputs": ["result"], "depends_on": ["B"]},
    }
    edges = [("A", "B"), ("B", "C")]

    inputs = iter(["2"])  # Delete node B (index 2)

    from unittest.mock import patch
    with patch("click.echo"):
        with patch("binex.cli.start.has_rich", return_value=False):
            new_nodes, new_edges = _constructor_delete_node(
                nodes_config, edges, input_fn=lambda _: next(inputs),
            )
    assert "B" not in new_nodes
    assert len(new_edges) == 0  # Both edges involving B removed


def test_constructor_edit_node_with_node_roles():
    """T057: Edit prompt uses node_roles mapping for role lookup."""
    from unittest.mock import patch

    nodes_config = {
        "analyzer": {"agent": "llm://test/m", "outputs": ["result"]},
    }
    edges = []
    node_roles = {"analyzer": "code-reviewer"}

    # Choose node 1, sub-action=p (prompt), pick variant=1
    inputs = iter(["1", "p", "1"])

    with patch("click.echo"):
        with patch("binex.cli.start.has_rich", return_value=False):
            result = _constructor_edit_node(
                nodes_config, edges, input_fn=lambda _: next(inputs),
                node_roles=node_roles,
            )
    assert "system_prompt" in result["analyzer"]
    # Should reference code-reviewer variant, not "analyzer"
    assert "code-reviewer" in result["analyzer"]["system_prompt"]


def test_constructor_edit_node_custom_text():
    """T060: Edit node prompt with custom text appears in config."""
    from unittest.mock import patch

    nodes_config = {
        "reviewer": {"agent": "llm://test/m", "outputs": ["result"]},
    }
    edges = []
    # Use node_roles so _select_prompt_variant gets a known role
    node_roles = {"reviewer": "code-reviewer"}

    # Choose node 1, sub=p, then "custom", then text
    inputs = iter(["1", "p", "custom", "You are a helpful writer."])

    with patch("click.echo"):
        with patch("binex.cli.start.has_rich", return_value=False):
            result = _constructor_edit_node(
                nodes_config, edges, input_fn=lambda _: next(inputs),
                node_roles=node_roles,
            )
    assert result["reviewer"]["system_prompt"] == "You are a helpful writer."


def test_constructor_edit_node_no_role_fallback():
    """T058: Unknown node name falls back to full bundled prompt list."""
    from unittest.mock import patch

    nodes_config = {
        "my-custom-node": {"agent": "llm://test/m", "outputs": ["result"]},
    }
    edges = []

    # Choose node 1, sub=p, pick first prompt from full list
    inputs = iter(["1", "p", "1"])

    with patch("click.echo"):
        with patch("binex.cli.start.has_rich", return_value=False):
            result = _constructor_edit_node(
                nodes_config, edges, input_fn=lambda _: next(inputs),
            )
    assert "system_prompt" in result["my-custom-node"]
    # Should have a file:// reference (from bundled prompts)
    assert "file://prompts/" in result["my-custom-node"]["system_prompt"]
