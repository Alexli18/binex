# Bisect Intuitive UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite bisect CLI output to be intuitive — verdict card + pipeline tree + inline diffs, replacing the old flat sections/table format.

**Architecture:** Add helper functions for formatting (verdict, pipeline tree, latency, content preview, change description) in `cli/bisect.py`. Rewrite `_print_plain()` and `_print_rich()` to use them. Add `--diff` flag. Update explore.py `_action_bisect()`. Update tests for new output format.

**Tech Stack:** Python 3.11+, click (CLI), rich (colored output), existing BisectReport dataclass (unchanged)

---

### Task 1: Add helper functions

**Files:**
- Modify: `src/binex/cli/bisect.py`
- Test: `tests/unit/test_qa_bisect_report.py`

**Step 1: Write failing tests for helpers**

Add to `tests/unit/test_qa_bisect_report.py`:

```python
from binex.cli.bisect import (
    _content_preview,
    _describe_change,
    _format_latency,
    _node_word,
)


class TestBisectHelpers:

    def test_content_preview_short(self):
        assert _content_preview("hello") == "hello"

    def test_content_preview_truncates(self):
        text = "x" * 200
        result = _content_preview(text, limit=100)
        assert len(result) == 101  # 100 + ellipsis
        assert result.endswith("\u2026")

    def test_content_preview_first_line_only(self):
        text = "first line\nsecond line\nthird"
        result = _content_preview(text, limit=100)
        assert "\n" not in result
        assert result == "first line"

    def test_content_preview_none(self):
        assert _content_preview(None) == ""

    def test_describe_change_completely(self):
        assert _describe_change(0.1) == "completely changed"

    def test_describe_change_partially(self):
        assert _describe_change(0.5) == "partially changed"

    def test_describe_change_slightly(self):
        assert _describe_change(0.85) == "slightly changed"

    def test_describe_change_none(self):
        assert _describe_change(None) == "changed"

    def test_format_latency_ms(self):
        assert _format_latency(500) == "500ms"

    def test_format_latency_seconds(self):
        assert _format_latency(30000) == "30.0s"

    def test_format_latency_zero(self):
        assert _format_latency(0) == "skipped"

    def test_format_latency_none(self):
        assert _format_latency(None) == "-"

    def test_node_word_match(self):
        assert _node_word("match") == "ok"

    def test_node_word_content_diff(self):
        assert _node_word("content_diff") == "changed"

    def test_node_word_status_diff_failed(self):
        assert _node_word("status_diff", "failed") == "failed"

    def test_node_word_status_diff_cancelled(self):
        assert _node_word("status_diff", "cancelled") == "cancelled"

    def test_node_word_missing(self):
        assert _node_word("missing_in_good") == "new"
        assert _node_word("missing_in_bad") == "missing"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_qa_bisect_report.py::TestBisectHelpers -v`
Expected: FAIL with ImportError

**Step 3: Implement helpers**

Add to `src/binex/cli/bisect.py` after the `_get_stores()` function (before `@click.command`):

```python
# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _content_preview(text: str | None, limit: int = 100) -> str:
    """First line of text, truncated to limit chars."""
    if not text:
        return ""
    first_line = text.split("\n", 1)[0]
    if len(first_line) <= limit:
        return first_line
    return first_line[:limit] + "\u2026"


def _describe_change(similarity: float | None) -> str:
    """Human-readable description of content change."""
    if similarity is None:
        return "changed"
    if similarity < 0.3:
        return "completely changed"
    if similarity < 0.7:
        return "partially changed"
    return "slightly changed"


def _format_latency(ms: int | None) -> str:
    """Format latency for display."""
    if ms is None:
        return "-"
    if ms == 0:
        return "skipped"
    if ms >= 10000:
        return f"{ms / 1000:.1f}s"
    return f"{ms}ms"


_NODE_ICONS = {
    "match": "\u2713",
    "content_diff": "\u26a0",
    "status_diff": "\u2717",
    "missing_in_good": "?",
    "missing_in_bad": "?",
}

_NODE_WORDS: dict[str, str | dict[str, str]] = {
    "match": "ok",
    "content_diff": "changed",
    "status_diff": {
        "failed": "failed",
        "cancelled": "cancelled",
        "_default": "differs",
    },
    "missing_in_good": "new",
    "missing_in_bad": "missing",
}


def _node_icon(status: str) -> str:
    """Get icon for node status."""
    return _NODE_ICONS.get(status, "?")


def _node_word(status: str, bad_status: str | None = None) -> str:
    """Get human-readable word for node status."""
    word = _NODE_WORDS.get(status, "unknown")
    if isinstance(word, dict):
        return word.get(bad_status or "", word["_default"])
    return word
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_qa_bisect_report.py::TestBisectHelpers -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/binex/cli/bisect.py tests/unit/test_qa_bisect_report.py
git commit -m "feat(bisect): add formatting helpers for intuitive UX"
```

---

### Task 2: Add --diff flag to CLI

**Files:**
- Modify: `src/binex/cli/bisect.py:18-60` (click command definition)

**Step 1: Write failing test for --diff flag**

Add to `TestCLIBisectReport` in `tests/unit/test_qa_bisect_report.py`:

```python
    def test_diff_flag_shows_full_diff(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_content_diff())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli,
                ["bisect", "good", "bad", "--no-rich", "--diff"],
            )
        assert result.exit_code == 0
        out = result.output
        # Full diff should have unified diff markers
        assert "---" in out
        assert "+++" in out
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_qa_bisect_report.py::TestCLIBisectReport::test_diff_flag_shows_full_diff -v`
Expected: FAIL (no such option)

**Step 3: Add --diff flag**

In `src/binex/cli/bisect.py`, add `--diff` option to `bisect_cmd` and pass `show_diff` to print functions:

```python
@click.command("bisect")
@click.argument("good_run_id")
@click.argument("bad_run_id")
@click.option(
    "--threshold", type=float, default=0.9,
    help="Content similarity threshold (0.0-1.0)",
)
@click.option(
    "--json-output", "--json", "json_out",
    is_flag=True, help="Output as JSON",
)
@click.option(
    "--rich/--no-rich", "rich_out",
    default=None, help="Rich output (auto-detected)",
)
@click.option(
    "--diff", "show_diff",
    is_flag=True, help="Show full unified diffs instead of preview",
)
def bisect_cmd(
    good_run_id: str,
    bad_run_id: str,
    threshold: float,
    json_out: bool,
    rich_out: bool | None,
    show_diff: bool,
) -> None:
    """Find the first node where two runs diverge."""
    if rich_out is None:
        rich_out = has_rich()
    try:
        report = asyncio.run(
            _run_bisect(good_run_id, bad_run_id, threshold),
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from binex.trace.bisect import bisect_report_to_dict

    result = bisect_report_to_dict(report)

    if json_out:
        click.echo(json.dumps(result, default=str, indent=2))
    elif rich_out:
        _print_rich(report, show_diff)
    else:
        _print_plain(report, show_diff)
```

Update `_print_plain` and `_print_rich` signatures to accept `show_diff: bool = False` (actual rewrite in next tasks — for now just add the parameter and ignore it so the flag test can pass):

```python
def _print_plain(report, show_diff: bool = False) -> None:
    # ... existing body unchanged for now ...

def _print_rich(report, show_diff: bool = False) -> None:
    # ... existing body unchanged for now ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_qa_bisect_report.py::TestCLIBisectReport::test_diff_flag_shows_full_diff -v`
Expected: PASS (the content diff lines are already in the output from previous implementation)

**Step 5: Commit**

```bash
git add src/binex/cli/bisect.py tests/unit/test_qa_bisect_report.py
git commit -m "feat(bisect): add --diff flag for full unified diffs"
```

---

### Task 3: Rewrite _print_plain() — new intuitive format

**Files:**
- Modify: `src/binex/cli/bisect.py:82-148` (the entire `_print_plain` function)
- Test: `tests/unit/test_qa_bisect_report.py`

**Step 1: Write failing tests for new plain output format**

Replace `test_plain_output_shows_all_sections` and `test_identical_runs_plain` in `TestCLIBisectReport`, and add new tests:

```python
    def test_plain_status_divergence(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_divergent())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli,
                ["bisect", "good", "bad", "--no-rich"],
            )
        assert result.exit_code == 0
        out = result.output
        # Header
        assert "good" in out and "bad" in out
        assert "wf" in out
        # Verdict
        assert "failed" in out
        assert "timeout" in out
        # Pipeline tree
        assert "\u2713" in out or "ok" in out  # match icon or word
        assert "\u2717" in out or "failed" in out
        assert "\u2190 root cause" in out or "root cause" in out
        # Footer
        assert "1 ok" in out
        # Error nested under node
        assert "timed out" in out

    def test_plain_identical(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_identical())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli,
                ["bisect", "good", "bad", "--no-rich"],
            )
        assert result.exit_code == 0
        out = result.output
        assert "No differences" in out or "identical" in out
        assert "2 ok" in out

    def test_plain_content_divergence_preview(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_content_diff())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli,
                ["bisect", "good", "bad", "--no-rich"],
            )
        assert result.exit_code == 0
        out = result.output
        assert "changed" in out
        assert 'good:' in out
        assert 'bad:' in out
        assert "SEO" in out

    def test_plain_content_diff_flag(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_content_diff())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli,
                ["bisect", "good", "bad", "--no-rich", "--diff"],
            )
        assert result.exit_code == 0
        out = result.output
        assert "---" in out
        assert "+++" in out
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_qa_bisect_report.py::TestCLIBisectReport -v`
Expected: Some FAIL (new assertions don't match old format)

**Step 3: Rewrite `_print_plain`**

Replace the entire `_print_plain` function in `src/binex/cli/bisect.py`:

```python
def _print_plain(report, show_diff: bool = False) -> None:
    """Print intuitive plain text bisect output."""
    # Header
    click.echo(f"Bisect: {report.workflow_name}")
    click.echo(f"good {report.good_run_id}  vs  bad {report.bad_run_id}")
    click.echo()

    dp = report.divergence_point
    downstream_set = set(report.downstream_impact)

    # Verdict
    if dp is None:
        click.echo(
            "\u2713 No differences found "
            "\u2014 runs are identical."
        )
    elif dp.divergence_type == "status":
        pattern = ""
        if report.error_context:
            pattern = f" ({report.error_context.pattern})"
        click.echo(
            f"\u2717 Node \"{dp.node_id}\" "
            f"{dp.bad_status}{pattern}"
        )
        if report.downstream_impact:
            n = len(report.downstream_impact)
            word = "node" if n == 1 else "nodes"
            click.echo(
                f"  Caused {n} downstream {word} "
                f"to cancel."
            )
    else:
        desc = _describe_change(dp.similarity)
        click.echo(
            f"\u26a0 Node \"{dp.node_id}\" "
            f"output {desc}"
        )
        # Content preview in verdict for content divergence
        div_nc = next(
            (nc for nc in report.node_map
             if nc.node_id == dp.node_id), None,
        )
        if div_nc and div_nc.content_diff:
            _print_verdict_preview(report, dp.node_id)

    click.echo()

    # Pipeline
    click.echo("Pipeline")
    total = len(report.node_map)
    for i, nc in enumerate(report.node_map):
        is_last = i == total - 1
        connector = "\u2514\u2500\u2500" if is_last else "\u251c\u2500\u2500"
        cont = " " if is_last else "\u2502"

        icon = _node_icon(nc.status)
        word = _node_word(nc.status, nc.bad_status)
        lat_g = _format_latency(nc.latency_good_ms)
        lat_b = _format_latency(nc.latency_bad_ms)

        # Marker
        marker = ""
        if dp and nc.node_id == dp.node_id:
            marker = "  \u2190 root cause"
        elif nc.node_id in downstream_set:
            marker = "  \u2190 affected"

        click.echo(
            f"{connector} {nc.node_id:<12} "
            f"{icon} {word:<10} "
            f"{lat_g} \u2192 {lat_b}"
            f"{marker}"
        )

        # Nested details under this node
        _print_node_details(
            nc, report, cont, show_diff,
        )

    # Footer
    click.echo()
    _print_footer(report)


def _print_verdict_preview(report, node_id: str) -> None:
    """Print good/bad content preview in verdict block."""
    from binex.trace.bisect import _get_content

    # We don't have art_store here, so use content_diff
    # to extract good/bad preview is not direct.
    # Instead, we skip — the pipeline shows it.
    pass


def _print_node_details(
    nc, report, cont: str, show_diff: bool,
) -> None:
    """Print nested details under a pipeline node."""
    # Error message for failed nodes
    if (
        report.error_context
        and report.error_context.node_id == nc.node_id
    ):
        click.echo(
            f"{cont}   \u2514\u2500\u2500 "
            f"{report.error_context.error_message}"
        )

    # Content diff or preview for changed nodes
    if nc.content_diff and nc.status == "content_diff":
        if show_diff:
            for line in nc.content_diff:
                click.echo(f"{cont}   {line}")
        else:
            # Extract good/bad preview from diff
            good_lines, bad_lines = _extract_preview(
                nc.content_diff,
            )
            if good_lines:
                preview = _content_preview(
                    "\n".join(good_lines), 100,
                )
                click.echo(
                    f"{cont}   \u251c\u2500\u2500 "
                    f'good: "{preview}"'
                )
            if bad_lines:
                preview = _content_preview(
                    "\n".join(bad_lines), 100,
                )
                click.echo(
                    f"{cont}   \u2514\u2500\u2500 "
                    f'bad:  "{preview}"'
                )


def _extract_preview(
    diff_lines: list[str],
) -> tuple[list[str], list[str]]:
    """Extract removed/added lines from unified diff."""
    good: list[str] = []
    bad: list[str] = []
    for line in diff_lines:
        if line.startswith("-") and not line.startswith("---"):
            good.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            bad.append(line[1:])
    return good, bad


def _print_footer(report) -> None:
    """Print summary footer line."""
    counts: dict[str, int] = {}
    for nc in report.node_map:
        word = _node_word(nc.status, nc.bad_status)
        counts[word] = counts.get(word, 0) + 1
    parts = [f"{v} {k}" for k, v in counts.items()]
    click.echo(" \u00b7 ".join(parts))
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_qa_bisect_report.py::TestCLIBisectReport -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: all pass

**Step 6: Commit**

```bash
git add src/binex/cli/bisect.py tests/unit/test_qa_bisect_report.py
git commit -m "feat(bisect): rewrite plain output — verdict + pipeline tree"
```

---

### Task 4: Rewrite _print_rich() — colored intuitive format

**Files:**
- Modify: `src/binex/cli/bisect.py:155-283` (the entire `_print_rich` function)

**Step 1: Write failing test for rich output**

Add to `TestCLIBisectReport`:

```python
    def test_rich_output_runs(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_divergent())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli,
                ["bisect", "good", "bad", "--rich"],
            )
        assert result.exit_code == 0
        assert len(result.output) > 0
```

**Step 2: Rewrite `_print_rich`**

Replace the entire `_print_rich` function:

```python
def _print_rich(report, show_diff: bool = False) -> None:
    """Print rich formatted bisect output."""
    from binex.cli.ui import get_console, make_panel

    console = get_console()

    dp = report.divergence_point
    downstream_set = set(report.downstream_impact)

    # Header
    console.print(
        f"[bold]Bisect:[/bold] {report.workflow_name}"
    )
    console.print(
        f"[cyan]good[/cyan] {report.good_run_id}  vs  "
        f"[cyan]bad[/cyan] {report.bad_run_id}"
    )
    console.print()

    # Verdict panel
    if dp is None:
        console.print(make_panel(
            "[green]\u2713 No differences found "
            "\u2014 runs are identical.[/green]",
            title="Verdict",
        ))
    elif dp.divergence_type == "status":
        pattern = ""
        if report.error_context:
            pattern = f" ({report.error_context.pattern})"
        lines = (
            f"[red bold]\u2717 Node \"{dp.node_id}\" "
            f"{dp.bad_status}{pattern}[/red bold]"
        )
        if report.downstream_impact:
            n = len(report.downstream_impact)
            word = "node" if n == 1 else "nodes"
            lines += (
                f"\n  Caused {n} downstream "
                f"{word} to cancel."
            )
        console.print(make_panel(lines, title="Verdict"))
    else:
        desc = _describe_change(dp.similarity)
        lines = (
            f"[yellow bold]\u26a0 Node \"{dp.node_id}\" "
            f"output {desc}[/yellow bold]"
        )
        console.print(make_panel(lines, title="Verdict"))

    console.print()

    # Pipeline
    _RICH_COLORS = {
        "match": "green",
        "content_diff": "yellow",
        "status_diff": "red",
        "missing_in_good": "cyan",
        "missing_in_bad": "magenta",
    }

    console.print("[bold]Pipeline[/bold]")
    total = len(report.node_map)
    for i, nc in enumerate(report.node_map):
        is_last = i == total - 1
        connector = "\u2514\u2500\u2500" if is_last else "\u251c\u2500\u2500"
        cont = " " if is_last else "\u2502"

        icon = _node_icon(nc.status)
        word = _node_word(nc.status, nc.bad_status)
        color = _RICH_COLORS.get(nc.status, "dim")
        lat_g = _format_latency(nc.latency_good_ms)
        lat_b = _format_latency(nc.latency_bad_ms)

        marker = ""
        if dp and nc.node_id == dp.node_id:
            marker = "  [red bold]\u2190 root cause[/red bold]"
        elif nc.node_id in downstream_set:
            marker = "  [dim]\u2190 affected[/dim]"

        console.print(
            f"{connector} [bold]{nc.node_id:<12}[/bold] "
            f"[{color}]{icon} {word:<10}[/{color}] "
            f"{lat_g} \u2192 {lat_b}"
            f"{marker}"
        )

        # Error nested
        if (
            report.error_context
            and report.error_context.node_id == nc.node_id
        ):
            console.print(
                f"{cont}   \u2514\u2500\u2500 "
                f"[red]{report.error_context.error_message}"
                f"[/red]"
            )

        # Content diff/preview
        if nc.content_diff and nc.status == "content_diff":
            if show_diff:
                for line in nc.content_diff:
                    if (
                        line.startswith("+")
                        and not line.startswith("+++")
                    ):
                        console.print(
                            f"{cont}   [green]{line}[/green]"
                        )
                    elif (
                        line.startswith("-")
                        and not line.startswith("---")
                    ):
                        console.print(
                            f"{cont}   [red]{line}[/red]"
                        )
                    elif line.startswith("@@"):
                        console.print(
                            f"{cont}   [cyan]{line}[/cyan]"
                        )
                    else:
                        console.print(f"{cont}   {line}")
            else:
                good_lines, bad_lines = _extract_preview(
                    nc.content_diff,
                )
                if good_lines:
                    preview = _content_preview(
                        "\n".join(good_lines), 100,
                    )
                    console.print(
                        f'{cont}   \u251c\u2500\u2500 '
                        f'[green]good: "{preview}"[/green]'
                    )
                if bad_lines:
                    preview = _content_preview(
                        "\n".join(bad_lines), 100,
                    )
                    console.print(
                        f'{cont}   \u2514\u2500\u2500 '
                        f'[red]bad:  "{preview}"[/red]'
                    )

    # Footer
    console.print()
    counts: dict[str, int] = {}
    for nc in report.node_map:
        word = _node_word(nc.status, nc.bad_status)
        counts[word] = counts.get(word, 0) + 1
    parts = []
    color_map = {
        "ok": "green", "changed": "yellow",
        "failed": "red", "cancelled": "dim",
        "new": "cyan", "missing": "magenta",
    }
    for k, v in counts.items():
        c = color_map.get(k, "")
        parts.append(f"[{c}]{v} {k}[/{c}]")
    console.print(" \u00b7 ".join(parts))
```

**Step 3: Run tests**

Run: `pytest tests/unit/test_qa_bisect_report.py::TestCLIBisectReport -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/binex/cli/bisect.py tests/unit/test_qa_bisect_report.py
git commit -m "feat(bisect): rewrite rich output — colored verdict + pipeline tree"
```

---

### Task 5: Update explore.py _action_bisect()

**Files:**
- Modify: `src/binex/cli/explore.py:880-1043` (the `_action_bisect` function)

**Step 1: Rewrite `_action_bisect`**

Replace the entire function. Reuse helpers from `cli/bisect.py`:

```python
async def _action_bisect(exec_store, art_store, run_id: str, run) -> None:
    """Find divergence point between current run (bad) and another run (good)."""
    click.echo("  Current run = bad run. Select the good run:")
    good_id = await _pick_other_run(exec_store, run_id, run.workflow_name)
    if not good_id:
        click.echo("  Bisect cancelled.")
        return

    from binex.trace.bisect import bisect_report as _bisect_report

    try:
        report = await _bisect_report(
            exec_store, art_store, good_id, run_id,
        )
    except ValueError as e:
        click.echo(f"  Error: {e}")
        return

    if has_rich():
        from binex.cli.bisect import _print_rich
        _print_rich(report)
    else:
        from binex.cli.bisect import _print_plain
        _print_plain(report)
```

This replaces ~160 lines of duplicated formatting code with a 2-line delegation to the rewritten functions.

**Step 2: Run existing tests**

Run: `pytest tests/unit/test_qa_bisect_report.py -v && pytest tests/unit/test_qa_advanced_debug.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/binex/cli/explore.py
git commit -m "refactor(explore): delegate bisect output to cli/bisect.py"
```

---

### Task 6: Clean up old tests, run full suite

**Files:**
- Modify: `tests/unit/test_qa_bisect_report.py`

**Step 1: Remove old tests that assert the old format**

Delete `test_plain_output_shows_all_sections` and `test_identical_runs_plain` (replaced by Task 3 tests).

**Step 2: Run lint**

Run: `ruff check src/binex/cli/bisect.py src/binex/cli/explore.py tests/unit/test_qa_bisect_report.py`
Expected: All checks passed

**Step 3: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: all 1639+ tests pass

**Step 4: Commit**

```bash
git add tests/unit/test_qa_bisect_report.py
git commit -m "test(bisect): update tests for intuitive UX format"
```

---

### Task 7: Update design doc

**Files:**
- Modify: `docs/plans/2026-03-12-bisect-intuitive-ux-design.md`

**Step 1: Mark design as implemented**

Add `**Status**: Implemented` to the top of the design doc.

**Step 2: Commit**

```bash
git add docs/plans/2026-03-12-bisect-intuitive-ux-design.md
git commit -m "docs: mark bisect intuitive UX design as implemented"
```
