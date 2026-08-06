# Binex vs. LangGraph, CrewAI & AutoGen

> Looking for observability and orchestration tools instead? See
> [Binex vs. LangSmith, Langfuse, n8n & Langflow](comparisons.md).

"Why Binex over LangGraph / CrewAI / AutoGen?" — the honest answer is that they
solve *different* problems. The other three are frameworks for **building** agent
systems. Binex is a **debuggable runtime** for them: its whole reason for
existing is that once an agent workflow runs, you can see exactly what happened
and iterate without guessing.

So the table below isn't "Binex wins" — it's "here's where each tool's weight
sits." Use Binex when observability, local iteration, and reproducibility are
the pain; reach for the others when their agent abstractions are what you need
(and consider [observer mode](features/observer-mode.md) to get Binex's
debugging *on top of* an existing CrewAI project without migrating).

## At a glance

| Capability | Binex | LangGraph | CrewAI | AutoGen |
|---|:---:|:---:|:---:|:---:|
| Local-first, no cloud required | ✅ | ✅ *(runtime)* | ✅ | ✅ |
| Built-in trace / replay / diff / bisect | ✅ | ⚠️ *(via LangSmith, hosted)* | ❌ | ❌ |
| Per-node / per-call cost tracking | ✅ | ⚠️ *(LangSmith)* | ⚠️ *(usage only)* | ⚠️ |
| Visual editor **and** CLI | ✅ | ⚠️ *(LangGraph Studio)* | ❌ | ⚠️ *(AutoGen Studio)* |
| YAML-declared workflows | ✅ | ❌ *(Python graph)* | ⚠️ *(YAML for crews)* | ❌ *(Python)* |
| Model-agnostic | ✅ *(LiteLLM, 100+)* | ✅ *(LangChain)* | ✅ *(LiteLLM)* | ✅ |
| Regression safety net (eval assertions + golden-run diff) | ✅ | ❌ | ❌ | ❌ |
| Debug an existing run **without migrating** | ✅ *([observer](features/observer-mode.md))* | ❌ | ❌ | ❌ |
| Rich agent-orchestration abstractions | ⚠️ *(patterns)* | ✅ | ✅ *(roles/tasks)* | ✅ *(conversations)* |
| Large ecosystem / integrations | ⚠️ | ✅ | ⚠️ | ✅ |

✅ first-class · ⚠️ partial / add-on / hosted · ❌ not a focus

## Where each one shines

- **LangGraph** — the most flexible way to express **stateful, cyclic** agent
  graphs in Python, with a deep LangChain ecosystem. Its observability
  (LangSmith) is excellent but hosted and separate; tracing/eval largely live in
  that paid, cloud product.
- **CrewAI** — the fastest way to stand up a **role-based crew** ("researcher →
  writer → editor"). Great ergonomics; the trade-off is that a crew runs as one
  opaque unit, and per-agent cost/trace is hard to see. Binex's
  [observer mode](features/observer-mode.md) exists precisely for CrewAI users.
- **AutoGen** — strong for **conversational, multi-agent** problem solving and
  research, backed by Microsoft, with AutoGen Studio for a no-code UI.
- **Binex** — not competing to *author* the smartest agent. It competes on
  everything *after* "run": trace, per-node/per-call cost, `diff`/`bisect`
  between runs, single-node/single-call [replay](cli/replay.md), eval
  [assertions](features/eval.md) as a pre-merge safety net, a git-snapshotted
  [workspace](features/workspace.md), and a local Web UI — all local, no account.

## The honest summary

- Building a novel agent architecture from scratch, or already deep in the
  LangChain ecosystem → **LangGraph**.
- Shipping a role-based crew fast → **CrewAI** (and point `observe()` at it for
  visibility).
- Conversational multi-agent research in the Microsoft stack → **AutoGen**.
- You have workflows that *run* and you're tired of "why did today's run behave
  differently?" — you want trace, cost, diff, bisect, replay, and regression
  gates, locally and privately → **Binex**.

They also compose: keep your CrewAI/LangGraph logic and use Binex to observe,
diff, and replay it.
