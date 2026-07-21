# Observer mode (prototype)

> **Status:** validation-gate prototype for #73. It proves the LiteLLM hook and
> the per-call cost breakdown. Per-agent/task attribution and the single-call
> replay UI (#74) build on top once the approach is validated.

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

Interception is at the **LiteLLM** layer, not CrewAI callbacks. CrewAI uses
LiteLLM internally, and LiteLLM supports custom callbacks per call. Hooking there
captures:

- the **full raw request** (messages, model, params) and response — which is
  what makes stateless single-call replay possible (#74);
- **exact token/cost accounting** straight from the source;
- resilience to CrewAI API churn (we don't depend on their callback surface).

Every captured call becomes an execution record + cost record + response
artifact under one run, marked **`observed`** and shown as `[observed]` in
`binex debug`. Because it's a normal run in the store, `binex diff` between two
observed runs works out of the box.

## Safety — we are a guest in someone else's process

`observe()` **must never crash the user's run**. Every internal error — callback
install, capture, or the final flush to the store — is swallowed into a log
warning. A missing usage field falls back to token-based pricing (approximate).

## Honest limitations

- **No partial-continuation replay.** Control flow lives in CrewAI's runtime
  (task selection, tool execution, memory). Full re-run + diff: yes. Single-call
  replay: yes (#74). "Resume from step 5 with a new answer": no.
- **Bisect works *between* two observed runs, not inside one.**
- Cost falls back to litellm token pricing when a step's usage is missing
  (flagged as approximate).

## Scope

v1 targets any LiteLLM-backed run (CrewAI is the headline audience). Deferred:
per-agent/per-task attribution via CrewAI `step_callback`/`task_callback`, the
single-call **Replay** button (#74), and a synthesized DAG view.
