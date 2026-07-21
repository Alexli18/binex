# Debugging & Observability guide

Binex's reason for existing is what happens *after* a workflow runs. This guide
walks the full toolkit end-to-end — which tool to reach for, the CLI command,
and where it lives in the Web UI (`binex ui`). Every one of these is local and
private; nothing leaves your machine.

## Which tool, when

| You want to… | Reach for | CLI |
|---|---|---|
| See what each node did, and why one failed | **Debug** | `binex debug <run>` |
| See the run as a timeline, spot slow/anomalous nodes | **Trace** | `binex trace <run>` |
| Get a root-cause hypothesis for a failure | **Diagnose** | `binex diagnose <run>` |
| Compare two runs node-by-node | **Diff** | `binex diff <a> <b>` |
| Tell *meaningful* output changes from rewording | **Semantic diff** | `binex diff <a> <b> --semantic` |
| Find which node — or which commit — broke quality | **Bisect** | `binex bisect …` |
| Gate against regressions before merge | **Eval** | `binex eval <workflow>` |
| See where the money went | **Cost** | `binex cost show <run>` |
| Try a different model/prompt on the same input | **Replay** | `binex replay …` |
| Debug an existing CrewAI run without migrating it | **Observer** | `observe()` + `binex ui` |

## 1. Debug a failed run

Start here. `binex debug <run-id>` (or `binex debug latest`) prints each node's
status, agent, prompt, output, timing, error, and — for runs with a
[workspace](../features/workspace.md) — the files it changed. In the Web UI, the
**Debug** tab gives the same per-node view, with inline previews for
[binary artifacts](../features/binary-artifacts.md) (images, audio, PDFs).

```bash
binex debug latest --errors      # only the failed/timed-out nodes
binex debug <run-id> --json      # machine-readable
```

## 2. Trace the timeline

`binex trace <run-id>` shows the run as a Gantt-style timeline — when each node
started, how long it took, and which nodes ran in parallel. The Web UI **Trace**
tab flags **anomalies** (nodes far slower than their peers) so a stall is obvious
at a glance.

## 3. Diagnose the root cause

`binex diagnose <run-id>` looks past the *first* error to the *root* one — the
node whose failure cascaded — and summarizes the failure pattern, so you fix the
cause, not a symptom.

## 4. Compare two runs

`binex diff <run-a> <run-b>` compares two runs node-by-node: status changes,
latency/cost deltas, and content differences. Textual diffs are noisy for LLM
output, so `--semantic` asks a cheap model **narrow questions** (did the
structure change? the facts? only the wording?) and flags *meaningful* changes
while collapsing cosmetic rewording — at temperature 0, with a confidence per
verdict, and it's strictly opt-in with the cost shown before it runs. See
[semantic diff](../cli/diff.md#semantic-diff-semantic).

## 5. Bisect a regression

Two granularities:

- **Across nodes** — `binex bisect <good-run> <bad-run>` finds the first node
  where two runs diverge.
- **Across git history** — `binex bisect history -w <workflow> --good <ref>
  --bad <ref>` binary-searches your commits, re-running the workflow at each and
  judging pass/fail with an eval criterion, to pinpoint the commit that broke
  quality (each probe runs in an isolated git worktree; see
  [bisect](../cli/bisect.md)).

## 6. Prevent regressions (eval)

Turn diff/bisect from post-mortem into a **pre-merge safety net**. Declare
block-on [assertions](../features/eval.md) on nodes (contains / lacks / regex /
cost & latency ceilings / an LLM-as-judge rubric), then `binex eval <workflow>`
exits non-zero on any failure; `--baseline <run-id>` also diffs against a golden
run. Drop it into CI on PRs that touch prompts or workflow YAML.

## 7. Track costs

`binex cost show <run-id>` breaks spend down per node; the Web UI **Cost
Dashboard** aggregates across runs, by model and over time. `binex cost simulate`
estimates what a run *would* cost on a different model — with zero LLM calls —
from its stored token counts.

## 8. Replay with changes

The dominant iteration loop is "this node answered badly → try another
prompt/model on the same input." `binex replay <run> --from <node> --agent
<node>=llm://…` re-runs from a node with swaps. For an
[observed](../features/observer-mode.md) run, `binex replay <run> --call
<call-id> --model X` replays a **single captured call** and shows the original
vs. new response side by side (cost tracked separately as experimentation).

## 9. Observe an existing run (no migration)

If your workflow lives in CrewAI (or any LiteLLM-backed code), you don't have to
port it. Wrap it:

```python
from binex import observe

with observe("my-crew-run"):
    crew.kickoff()
```

Then open `binex ui` (or `binex debug my-crew-run`) for the trace, per-call cost
breakdown, and response artifacts — on untouched code. Every tool above then
works on that observed run. Try it offline first with `binex observe-demo`. See
[observer mode](../features/observer-mode.md).

## Put it together

A typical loop: a run misbehaves → **debug** to see the failing node → **trace**
if it was slow → **diagnose** for the root cause → **diff** (or **bisect**) an
old good run against it → **replay** a fix on the offending node → add an **eval
assertion** so it can't regress again → watch **cost** the whole time.
