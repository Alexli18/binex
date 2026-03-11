"""Shared UI design system for Binex CLI.

Single source of truth for all visual components — colours, status icons,
panels, tables, summary lines, and plain-text fallbacks.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BORDER_STYLE = "blue"
HEADER_STYLE = "bold cyan"

# Maps status string → (display_text, rich_style)
STATUS_CONFIG: dict[str, tuple[str, str]] = {
    # Run / node statuses
    "completed": ("completed", "green"),
    "failed": ("FAILED", "red bold"),
    "running": ("running", "yellow"),
    "timed_out": ("timed out", "yellow"),
    "skipped": ("skipped", "dim"),
    "over_budget": ("over budget", "yellow"),
    # Doctor / health statuses
    "ok": ("ok", "green"),
    "missing": ("missing", "red"),
    "error": ("error", "red"),
    "degraded": ("degraded", "yellow"),
    "unreachable": ("unreachable", "red"),
    "timeout": ("timeout", "yellow"),
    "not_initialized": ("not init", "dim"),
}

# Plain-text icon mapping (status → icon character)
_PLAIN_ICONS: dict[str, str] = {
    "completed": "✓",
    "ok": "✓",
    "failed": "✗",
    "error": "✗",
    "missing": "✗",
    "unreachable": "✗",
    "running": "!",
    "timed_out": "!",
    "over_budget": "!",
    "degraded": "!",
    "timeout": "!",
    "skipped": "○",
    "not_initialized": "·",
}


# ---------------------------------------------------------------------------
# Rich status helpers
# ---------------------------------------------------------------------------

def status_icon(status: str) -> str:
    """Return a Rich-markup coloured bullet for *status*."""
    _, style = STATUS_CONFIG.get(status, (status, "dim"))
    return f"[{style}]●[/{style}]"


def status_text(status: str) -> Text:
    """Return a styled :class:`~rich.text.Text` object for *status*."""
    display, style = STATUS_CONFIG.get(status, (status, "dim"))
    return Text(display, style=style)


# ---------------------------------------------------------------------------
# Summary / header builders
# ---------------------------------------------------------------------------

def make_summary(
    *,
    completed: int = 0,
    failed: int = 0,
    time: float | None = None,
    cost: float | None = None,
) -> Text:
    """Build a one-line summary like ``✓ 4 completed · ✗ 1 failed · 19.94s · $0.01``."""
    parts: list[Text] = []

    if completed:
        t = Text("✓ ", style="green")
        t.append(f"{completed} completed", style="green")
        parts.append(t)

    if failed:
        t = Text("✗ ", style="red")
        t.append(f"{failed} failed", style="red")
        parts.append(t)

    if time is not None:
        parts.append(Text(f"{time:.2f}s", style="dim"))

    if cost is not None:
        parts.append(Text(f"${cost:.2f}", style="cyan"))

    separator = Text(" · ", style="dim")
    result = Text()
    for i, part in enumerate(parts):
        if i > 0:
            result.append(separator)
        result.append(part)
    return result


def make_header(**fields: Any) -> Text:
    """Build a header line like ``Workflow: test.yaml  ·  Run: abc123``."""
    parts: list[Text] = []
    for key, value in fields.items():
        label = key.replace("_", " ").title()
        t = Text(f"{label}: ", style=HEADER_STYLE)
        t.append(str(value))
        parts.append(t)

    separator = Text("  ·  ", style="dim")
    result = Text()
    for i, part in enumerate(parts):
        if i > 0:
            result.append(separator)
        result.append(part)
    return result


# ---------------------------------------------------------------------------
# Component factories
# ---------------------------------------------------------------------------

def make_panel(
    content: Any,
    *,
    title: str | None = None,
    subtitle: str | None = None,
) -> Panel:
    """Create a :class:`~rich.panel.Panel` with the project's standard style."""
    return Panel(
        content,
        title=title,
        subtitle=subtitle,
        border_style=BORDER_STYLE,
        padding=(1, 2),
    )


def make_table(
    *columns: tuple[str, dict[str, Any]],
    title: str | None = None,
) -> Table:
    """Create a :class:`~rich.table.Table` with standard Binex styling.

    Each *column* is ``(name, kwargs_dict)`` forwarded to
    :meth:`Table.add_column`.
    """
    from rich.box import ROUNDED

    table = Table(
        box=ROUNDED,
        border_style=BORDER_STYLE,
        header_style=HEADER_STYLE,
        title=title,
    )
    for name, kwargs in columns:
        table.add_column(name, **kwargs)
    return table


def cost_bar(value: float, max_value: float, *, width: int = 20) -> str:
    """Render a horizontal bar ``[cyan]━━━[/cyan][dim]╌╌╌[/dim]``."""
    if max_value <= 0 or value <= 0:
        return f"[dim]{'╌' * width}[/dim]"
    ratio = min(value / max_value, 1.0)
    filled = round(ratio * width)
    empty = width - filled
    return f"[cyan]{'━' * filled}[/cyan][dim]{'╌' * empty}[/dim]"


# ---------------------------------------------------------------------------
# Plain-text fallbacks
# ---------------------------------------------------------------------------

def plain_status_icon(status: str) -> str:
    """Return a plain-text icon character for *status*."""
    return _PLAIN_ICONS.get(status, "?")


def plain_summary(
    *,
    completed: int = 0,
    failed: int = 0,
    time: float | None = None,
    cost: float | None = None,
) -> str:
    """Plain-text version of :func:`make_summary`."""
    parts: list[str] = []
    if completed:
        parts.append(f"✓ {completed} completed")
    if failed:
        parts.append(f"✗ {failed} failed")
    if time is not None:
        parts.append(f"{time:.2f}s")
    if cost is not None:
        parts.append(f"${cost:.2f}")
    return " · ".join(parts)


def plain_header(**fields: Any) -> str:
    """Plain-text version of :func:`make_header`."""
    parts: list[str] = []
    for key, value in fields.items():
        label = key.replace("_", " ").title()
        parts.append(f"{label}: {value}")
    return "  ·  ".join(parts)


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------

def get_console(*, stderr: bool = False, width: int = 120) -> Console:
    """Return a :class:`~rich.console.Console` with standard settings."""
    return Console(stderr=stderr, width=width)


def render_to_string(renderable: Any, *, width: int = 120) -> str:
    """Render a rich object to a plain string via :class:`~io.StringIO`."""
    buf = StringIO()
    console = Console(file=buf, width=width, no_color=False)
    console.print(renderable)
    return buf.getvalue()
