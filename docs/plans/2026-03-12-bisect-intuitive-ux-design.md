# Bisect Intuitive UX Design

**Date**: 2026-03-12
**Branch**: 009-advanced-debugging
**Status**: Implemented

## Goal

Make `binex bisect` output intuitive. Answer three questions instantly: where broke, why, what was affected.

## Current Problem

- Technical terminology: "divergence", "status_diff", "downstream impact"
- No visual flow — flat table
- No narrative — user must piece together the story
- Similarity percentages meaningless to users

## New Output Format

### Verdict Card (top)

Status divergence:
```
╭─ Verdict ──────────────────────────────────────╮
│                                                │
│  ✗ Node "generate" failed (timeout)            │
│    Caused 1 downstream node to cancel.         │
│                                                │
╰────────────────────────────────────────────────╯
```

Content divergence:
```
╭─ Verdict ──────────────────────────────────────╮
│                                                │
│  ⚠ Node "generate" output completely changed   │
│    good: "The article covers SEO basics…"      │
│    bad:  "Error: API returned empty response"   │
│                                                │
╰────────────────────────────────────────────────╯
```

No divergence: `✓ No differences found — runs are identical.`

Change description from similarity:
- < 0.3 → "completely changed"
- < 0.7 → "partially changed"
- < threshold → "slightly changed"

### Pipeline Tree (middle)

```
Pipeline
├── A  research     ✓ ok        100ms → 110ms
├── B  generate     ✗ failed    200ms → 30.0s    ← root cause
│   └── Connection timed out after 30s
└── C  publish      - cancelled 150ms → skipped  ← affected
```

Status mapping:

| Status | Icon | Word | Color |
|--------|------|------|-------|
| match | ✓ | ok | green |
| content_diff | ⚠ | changed | yellow |
| status_diff (failed) | ✗ | failed | red |
| status_diff (cancelled) | - | cancelled | gray |
| missing_in_good | ? | new | cyan |
| missing_in_bad | ? | missing | magenta |

- `← root cause` on divergence point
- `← affected` on downstream impact nodes
- Error message nested via `└──` under failed node
- Content preview nested via `├──`/`└──` (good:/bad:) under changed node
- Latency as `200ms → 30.0s` (arrow, not two columns)
- `skipped` instead of `0ms`

### Content Diffs in Pipeline

Preview mode (default): first ~100 chars of content
```
├── B  generate     ⚠ changed  200ms → 210ms    ← root cause
│   ├── good: "The article covers SEO basics including keyword research…"
│   └── bad:  "Error: API returned empty response"
```

Full diff mode (`--diff` flag):
```
├── B  generate     ⚠ changed  200ms → 210ms    ← root cause
│   --- good
│   +++ bad
│   @@ -1,2 +1 @@
│   -The article covers SEO basics
│   -including keyword research and backlinks
│   +Error: API returned empty response
```

### Footer

```
1 ok · 1 failed · 1 cancelled
```

## Output Modes

- **Plain** (--no-rich): Unicode tree, no colors
- **Rich** (default): Same layout, colored (✓ green, ✗ red, ⚠ yellow, - gray)
- **JSON** (--json): Unchanged machine-readable format
- **--diff**: Full unified diffs instead of preview (combinable with plain/rich)

## Implementation

### New flag
- `--diff` on `bisect_cmd` — show full unified diffs in pipeline

### New helpers
- `_format_verdict(report, art_store)` — build verdict text
- `_format_pipeline(report, show_diff)` — build tree view
- `_content_preview(text, limit=100)` — truncate with `…`
- `_describe_change(similarity)` — "completely/partially/slightly changed"
- `_format_latency(ms)` — `200ms`, `30.0s`, `skipped`

### Rewritten
- `_print_plain(report, show_diff)` — new format
- `_print_rich(report, show_diff)` — new format with colors
- `_action_bisect()` in explore.py — same new format

### Unchanged
- `bisect_report()`, `BisectReport`, `NodeComparison`, `DivergencePoint`
- `bisect_report_to_dict()` — JSON output
- `find_divergence()` — legacy API

### Tests
- Update CLI output assertions in `test_qa_bisect_report.py`
- Add `--diff` flag tests
- Add unit tests for helpers
