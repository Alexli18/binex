Output demo-eval.gif

Set Shell "bash"
Set FontSize 14
Set Width 1200
Set Height 600
Set Theme "Dracula"
Set Padding 16
Set TypingSpeed 60ms

# ── Setup ──────────────────────────────────────────────────────────────────

Type "pip install binex --quiet" Enter
Sleep 3s

Type "clear" Enter
Sleep 500ms

# ── First run — no baseline yet ────────────────────────────────────────────

Type "# First run — no baseline yet" Enter
Sleep 800ms

Type "binex eval run examples/eval/research-eval.yaml" Enter
Sleep 3s

# ── Bless the baseline ─────────────────────────────────────────────────────

Sleep 1s
Type "# Bless current outputs as the baseline" Enter
Sleep 800ms

Type "binex eval bless examples/eval/research-eval.yaml" Enter
Sleep 2s

# ── Re-run — everything should pass ───────────────────────────────────────

Sleep 1s
Type "# Re-run — all cases should be green" Enter
Sleep 800ms

Type "binex eval run examples/eval/research-eval.yaml" Enter
Sleep 3s

# ── CI mode ───────────────────────────────────────────────────────────────

Sleep 1s
Type "# CI mode: --format github --strict-baseline" Enter
Sleep 800ms

Type "binex eval run examples/eval/research-eval.yaml --format github --strict-baseline" Enter
Sleep 3s

# ── Done ──────────────────────────────────────────────────────────────────

Sleep 2s
