"""Template registry and prompt handling for the start wizard."""

from __future__ import annotations

import importlib.resources
import shutil
import sys
from pathlib import Path

import click

from binex.cli.prompt_roles import get_role


def has_rich() -> bool:
    """Proxy to binex.cli.start.has_rich for test-patchability."""
    return sys.modules["binex.cli.start"].has_rich()

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

# Maps node names to prompt .md filenames in binex/prompts/
_NODE_PROMPT_FILES: dict[str, str] = {
    # Research pipeline
    "planner": "gen-research-planner.md",
    "researcher1": "gen-researcher.md",
    "researcher2": "gen-researcher.md",
    "validator": "gen-research-validator.md",
    "summarizer": "gen-research-synthesizer.md",
    # Content review pipeline
    "draft": "gen-draft-writer.md",
    "review": "gen-content-reviewer.md",
    "revise": "gen-content-reviser.md",
    "finalize": "gen-content-editor.md",
    # Data processing pipeline
    "splitter": "gen-chunk-splitter.md",
    "processor": "gen-chunk-processor.md",
    "merger": "gen-chunk-merger.md",
    # Map-reduce pipeline
    "mapper": "gen-data-processor.md",
    "reducer": "gen-data-aggregator.md",
    # Generic fallbacks
    "analyzer": "gen-data-refiner.md",
    "reviewer": "gen-content-reviewer.md",
}


def _get_prompts_dir() -> Path:
    """Resolve the bundled prompts directory (src/binex/prompts/)."""
    ref = importlib.resources.files("binex") / "prompts"
    return Path(str(ref))


def _copy_prompts_to_project(
    project_dir: Path,
    needed_files: set[str],
) -> None:
    """Copy needed prompt .md files into project_dir/prompts/."""
    src_dir = _get_prompts_dir()
    dst_dir = project_dir / "prompts"
    dst_dir.mkdir(exist_ok=True)
    for filename in sorted(needed_files):
        src = src_dir / filename
        if src.exists():
            shutil.copy2(src, dst_dir / filename)


def _get_bundled_prompt_list() -> list[tuple[str, str]]:
    """Return list of (filename, description) for bundled prompts."""
    prompts_dir = _get_prompts_dir()
    result = []
    for md_file in sorted(prompts_dir.glob("*.md")):
        first_line = md_file.read_text().strip().split("\n")[0][:60]
        result.append((md_file.name, first_line))
    return result


def _render_variant_menu(role_name: str, variants: list) -> None:
    """Render the variant selection menu (Rich or plain)."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print(
            f"  Prompt variants for [bold]{role_name}[/bold]:"
        )
        for i, v in enumerate(variants, 1):
            line = Text()
            line.append(f"    {i}) ", style="dim")
            if v.is_default:
                line.append("\u2605 ", style="yellow")
            else:
                line.append("  ", style="dim")
            line.append(f"{v.label:12s}", style="bold")
            line.append(f" \u2014 {v.description}", style="dim")
            if v.is_default:
                line.append(" (recommended)", style="green")
            console.print(line)
        console.print()
        console.print(
            "  [dim][v N] Preview  [custom] Custom text  "
            "[edit] $EDITOR  [file] From file[/dim]"
        )
    else:
        click.echo(f"  Prompt variants for {role_name}:")
        for i, v in enumerate(variants, 1):
            star = "\u2605 " if v.is_default else "  "
            rec = " (recommended)" if v.is_default else ""
            click.echo(
                f"    {i}) {star}{v.label:12s}"
                f" \u2014 {v.description}{rec}"
            )
        click.echo()
        click.echo(
            "  [v N] Preview  [custom] Custom text  "
            "[edit] $EDITOR  [file] From file"
        )


def _handle_preview(choice: str, variants: list) -> bool:
    """Handle 'v N' preview command. Returns True if handled."""
    if not choice.lower().startswith("v "):
        return False
    try:
        preview_idx = int(choice.split()[1])
        if 1 <= preview_idx <= len(variants):
            _preview_prompt_file(variants[preview_idx - 1].filename)
    except (ValueError, IndexError):
        pass
    return True


def _handle_text_commands(choice: str, _prompt) -> str | None:
    """Handle 'custom', 'edit', 'file' commands. Returns prompt string or None."""
    cmd = choice.lower()

    if cmd == "custom":
        return _prompt("Enter system prompt text")

    if cmd == "edit":
        content = click.edit()
        if content and content.strip():
            return content.strip()
        # Editor cancelled — fall back to text
        return _prompt("Editor cancelled. Enter prompt text")

    if cmd == "file":
        path = _prompt("Enter path to prompt file")
        if not path.startswith("file://"):
            path = f"file://{path}"
        return path

    return None


def _select_prompt_variant(
    *, role_name: str, input_fn=None,
) -> str:
    """Pick a prompt variant for a role. Returns system_prompt string.

    For known roles: shows role-specific variants.
    For unknown roles: falls back to full bundled prompt list.
    """
    _prompt = input_fn or (lambda p: click.prompt(p))
    role = get_role(role_name)

    if role is None:
        # Fallback to generic prompt picker
        return _select_prompt(node_id=role_name, input_fn=_prompt)

    variants = role.variants

    while True:
        _render_variant_menu(role_name, variants)

        choice = _prompt("Choose").strip()

        if _handle_preview(choice, variants):
            continue

        result = _handle_text_commands(choice, _prompt)
        if result is not None:
            return result

        # Numeric selection
        try:
            idx = int(choice)
            if 1 <= idx <= len(variants):
                return f"file://prompts/{variants[idx - 1].filename}"
        except ValueError:
            pass

        # Default: pick the default variant
        return f"file://prompts/{role.default_variant.filename}"


def _preview_prompt_file(filename: str) -> None:
    """Display prompt file content."""
    prompts_dir = _get_prompts_dir()
    path = prompts_dir / filename
    if not path.exists():
        click.echo(f"  (File not found: {filename})")
        return
    content = path.read_text()
    if has_rich():
        from binex.cli.ui import get_console, make_panel

        console = get_console(stderr=True)
        console.print(make_panel(content, title=filename))
    else:
        click.echo(f"\n--- {filename} ---")
        click.echo(content)
        click.echo("--- end ---\n")


def _render_prompt_menu(
    bundled: list[tuple[str, str]],
    recommended_idx: int | None,
) -> None:
    """Render the bundled-prompt selection menu (Rich or plain)."""
    custom_text_n = len(bundled) + 1
    file_path_n = len(bundled) + 2

    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print("  System prompt:")
        for i, (filename, desc) in enumerate(bundled, 1):
            line = Text()
            line.append(f"    {i}) ", style="dim")
            line.append(filename, style="cyan")
            if i - 1 == recommended_idx:
                line.append(" (recommended)", style="green")
            line.append(f" \u2014 {desc}", style="dim")
            console.print(line)
        line = Text()
        line.append(f"    {custom_text_n}) ", style="dim")
        line.append("Write custom text", style="bold")
        console.print(line)
        line = Text()
        line.append(f"    {file_path_n}) ", style="dim")
        line.append("Provide file path", style="bold")
        console.print(line)
    else:
        click.echo("  System prompt:")
        for i, (filename, desc) in enumerate(bundled, 1):
            tag = " (recommended)" if i - 1 == recommended_idx else ""
            click.echo(f"    {i}) {filename}{tag} \u2014 {desc}")
        click.echo(f"    {custom_text_n}) Write custom text")
        click.echo(f"    {file_path_n}) Provide file path")


def _select_prompt(*, node_id: str, input_fn=None) -> str:
    """Interactive prompt picker. Returns system_prompt string.

    Options: bundled prompts (file:// ref), custom text, file path.
    """
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))
    bundled = _get_bundled_prompt_list()

    # Find recommended prompt
    recommended_idx = None
    for i, (filename, _desc) in enumerate(bundled):
        stem = filename.removesuffix(".md")
        if stem == node_id or node_id in stem or stem in node_id:
            recommended_idx = i
            break

    _render_prompt_menu(bundled, recommended_idx)

    choice = _prompt("Choose prompt")

    # Guard 1: numeric index
    try:
        choice_int = int(choice)
    except ValueError:
        choice_int = None

    if choice_int is not None:
        if choice_int <= len(bundled):
            return f"file://prompts/{bundled[choice_int - 1][0]}"
        if choice_int == len(bundled) + 1:
            return _prompt("Enter system prompt text")
        # file path option (or any higher number)
        path = _prompt("Enter path to prompt file")
        if not path.startswith("file://"):
            path = f"file://{path}"
        return path

    # Guard 2: filename match
    matched = [
        f for f, _ in bundled
        if f == choice or f.removesuffix(".md") == choice
    ]
    if matched:
        return f"file://prompts/{matched[0]}"

    # Guard 3: treat as custom text
    return choice
