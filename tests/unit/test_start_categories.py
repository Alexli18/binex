"""Tests for category navigation in binex start wizard."""

from unittest.mock import patch

from click.testing import CliRunner

from binex.cli.start import start_cmd


def test_start_shows_categories():
    """Invoking start should display category names like General and Development."""
    runner = CliRunner()
    result = runner.invoke(start_cmd, input="q\n")
    assert "General" in result.output or "general" in result.output.lower()
    assert "Development" in result.output or "development" in result.output.lower()


def test_start_category_then_template():
    """Selecting a category should show its templates."""
    runner = CliRunner()
    # Select category 2 (Development), then q to go back, then q to quit
    result = runner.invoke(start_cmd, input="2\nq\nq\n")
    output = result.output
    assert "Code Review" in output or "code-review" in output.lower()


def test_start_back_from_templates():
    """Pressing 'b' from template list returns to categories."""
    runner = CliRunner()
    result = runner.invoke(start_cmd, input="2\nb\nq\n")
    output = result.output
    first = output.find("General")
    if first == -1:
        first = output.lower().find("general")
    second = output.find("General", first + 1)
    if second == -1:
        second = output.lower().find("general", first + 1)
    assert second > first, "Categories should be shown again after back"


def test_start_constructor_shortcut():
    """Pressing 'c' should enter constructor mode."""
    runner = CliRunner()
    with patch("binex.cli.start._step_custom_template", side_effect=SystemExit(0)):
        result = runner.invoke(start_cmd, input="c\n")
    output = result.output.lower()
    assert "constructor" in output or "dsl" in output or "topology" in output
