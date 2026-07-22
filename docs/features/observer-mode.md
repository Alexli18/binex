# Observer mode

> **Status:** the product's front door. A user with a working CrewAI pipeline
> gets value without rewriting anything into workflow YAML — `pip install`, two
> lines, and their untouched code shows up in the trace with per-task, per-call
> costs. YAML orchestration is the optional second act.

The `crewai://` adapter asks you to move your Crew *inside* a Binex workflow —
and even then the Crew runs as one opaque node: five agents work inside, the
trace sees a single box. Observer mode instead watches an **existing** run in
place. No migration, two lines in your own code:

```python
from binex import observe

with observe("my-crew-run"):
    crew.kickoff()
```

Then open `binex debug my-crew-run` (or `binex ui`) and you get the run's LLM
calls, per-call costs, and response artifacts — on your untouched code. Opaque
spend is one of the most common CrewAI complaints; a local, private cost
breakdown is the hook.

## Try it without a Crew

To see observer mode work without wiring up a real CrewAI project, run the
built-in demo — it simulates a small multi-agent flow whose calls use LiteLLM
`mock_response` (no API key, no network), so it exercises the *real* capture path
offline:

```bash
binex observe-demo
# Captured 4 LLM call(s) into observed run 'obs_...' (≈$0.0005)
binex debug obs_...     # trace + per-call breakdown, marked [observed]
```

## How it works

Two interception points, each doing one job:

**Capture — at the LiteLLM layer.** CrewAI uses LiteLLM internally. Observer mode
wraps `litellm.completion`/`acompletion` for the duration of the block, capturing
every call's:

- **full raw request** (messages, model, params) and response — which is what
  makes stateless single-call replay possible (#74);
- **exact token/cost accounting** straight from the source.

> We wrap the function rather than register a `litellm.callbacks` logger on
> purpose: CrewAI reassigns `litellm.callbacks` to its own handler on each call,
> so a callback-based observer would be silently dropped after the first call.
> Wrapping the function survives that.

**Attribution — via CrewAI.** To know *which task/agent* made each call, observer
mode wraps `crewai.Agent.execute_task`. While a task runs, a context variable
holds the current `(task, agent)`; the LiteLLM capture reads it and tags the call.
On flush, calls are grouped into a **parent task node** (`crewai://<role>`) with
each call a **child record** underneath — so `binex trace` shows tasks with their
agent's calls nested, exactly like orchestrated subtasks.

Every captured call becomes an execution record + cost record + request/response
artifacts under one run, marked **`observed`** and shown as `[observed]` in
`binex debug`.

### Task & agent attribution and `binex diff`

Task node ids are **name-based** (derived from the CrewAI task's name, or its
description) — the "pseudo-spec" synthesized from what we observe. That is what
lets `binex diff` between two observed runs of the same crew line up task-by-task
out of the box, even though an observed run has no `WorkflowSpec`. Match by name,
not by call position.

## Supported CrewAI versions

| Component | Tested | Notes |
|-----------|--------|-------|
| CrewAI | **0.86.x** (CI-pinned) | Attribution hooks `Agent.execute_task`, whose `(self, task, context, tools)` signature is stable across the 0.7x–0.8x line. |

The CI matrix in `.github/workflows/ci.yml` (`observe-crewai` job) pins the exact
version(s) the newcomer-path integration test runs against; keep this table in
sync with it. **Version drift degrades gracefully:** if CrewAI is absent, or the
patch target has moved, capture still works — you get the flat per-call trace
without task/agent grouping, plus a logged warning, never a crash.

## Safety — we are a guest in someone else's process

`observe()` **must never crash the user's run**. Every internal error — wrapping
LiteLLM, patching CrewAI for attribution, capturing a call, or the final flush to
the store — is swallowed into a log warning. A missing usage field falls back to
token-based pricing (approximate). The store **auto-initializes** if `.binex`
doesn't exist yet, so a first-time user needs zero configuration.

This is covered by a crash-safety test: a failure injected into the capture path
leaves `crew.kickoff()` completing normally, with only a warning logged.

## Single-call replay (#74)

Because each captured call carries its *complete* request (messages, model), any
one call can be **replayed statelessly** — the framework's memory and context are
already baked into the captured messages, so nothing needs reconstructing:

```bash
binex replay <run-id> --call call_002 --model claude-sonnet-4-20250514
binex replay <run-id> --call call_002 --prompt-file better_prompt.txt
```

It re-sends the call (optionally swapping the model or replacing the user prompt)
and shows the original vs. new response side by side — the dominant iteration
loop ("this agent answered badly → try another prompt/model on the same input"),
without touching your code. Deliberately bounded:

- **Stops at tool use** — if the replayed model requests a tool call, its name
  and arguments are shown but **not executed** (tool implementations live in your
  environment).
- **No downstream continuation** — the result is a comparison artifact, not fed
  back into the observed pipeline.
- **Experimentation spend** — the replay's cost is recorded (`source: replay`)
  but **excluded from the run's cost total**.

Verify it offline with `--mock-response` (no API key), e.g. after
`binex observe-demo`:

```bash
binex replay <obs-run> --call call_000 --model gpt-4o \
    --mock-response "a different plan"
```

## Honest limitations

- **No partial-continuation replay.** Control flow lives in CrewAI's runtime
  (task selection, tool execution, memory). Full re-run + diff: yes. Single-call
  replay: yes (#74). "Resume from step 5 with a new answer": no.
- **Bisect works *between* two observed runs, not inside one.**
- Cost falls back to litellm token pricing when a step's usage is missing
  (flagged as approximate).

## Scope

v1 targets **CrewAI** (the headline audience and strongest pain), with per-task /
per-agent attribution, per-call costs and payloads, single-call replay (#74), and
`binex diff` between observed runs. Plain LiteLLM-backed runs are still captured —
just without task grouping (a flat per-call trace).

Out of scope for v1 (by design): LangChain/AutoGen observers, importer/migration
tooling, and partial-continuation replay ("resume from step 5").
