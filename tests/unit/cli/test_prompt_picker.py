"""Tests for prompt variant picker in binex start wizard."""

from unittest.mock import patch

from binex.cli.start_templates import _select_prompt_variant


def test_shows_variants_for_role():
    """Known role should return a file:// reference to a matching prompt."""
    inputs = iter(["1"])  # Select first variant
    result = _select_prompt_variant(
        role_name="code-reviewer", input_fn=lambda _: next(inputs),
    )
    assert "file://prompts/" in result
    assert "code-reviewer" in result


def test_default_variant_marked():
    """Output should mark the default variant with a star or 'recommended'."""
    output_lines = []

    def capture_echo(msg="", **kw):
        output_lines.append(str(msg))

    inputs = iter(["1"])
    with patch("click.echo", side_effect=capture_echo):
        with patch("binex.cli.start.has_rich", return_value=False):
            _select_prompt_variant(
                role_name="code-reviewer", input_fn=lambda _: next(inputs),
            )
    combined = "\n".join(output_lines)
    assert "★" in combined or "recommended" in combined.lower()


def test_preview_before_select():
    """'v 1' should preview a variant, then selecting '1' returns file ref."""
    inputs = iter(["v 1", "1"])
    result = _select_prompt_variant(
        role_name="code-reviewer", input_fn=lambda _: next(inputs),
    )
    assert "file://prompts/" in result


def test_fallback_for_unknown_role():
    """Unknown role should show full bundled prompt list."""
    inputs = iter(["1"])
    result = _select_prompt_variant(
        role_name="nonexistent-role-xyz", input_fn=lambda _: next(inputs),
    )
    assert "file://prompts/" in result


def test_custom_text_option():
    """'custom' followed by text returns inline text."""
    inputs = iter(["custom", "You are a helpful assistant."])
    result = _select_prompt_variant(
        role_name="code-reviewer", input_fn=lambda _: next(inputs),
    )
    assert result == "You are a helpful assistant."


def test_editor_option():
    """'edit' opens click.edit(), returns edited text."""
    inputs = iter(["edit"])
    with patch("click.edit", return_value="Edited prompt content"):
        result = _select_prompt_variant(
            role_name="code-reviewer", input_fn=lambda _: next(inputs),
        )
    assert result == "Edited prompt content"


def test_editor_cancelled():
    """Editor returning None falls back to text prompt."""
    inputs = iter(["edit", "Fallback text"])
    with patch("click.edit", return_value=None):
        result = _select_prompt_variant(
            role_name="code-reviewer", input_fn=lambda _: next(inputs),
        )
    assert result == "Fallback text"
