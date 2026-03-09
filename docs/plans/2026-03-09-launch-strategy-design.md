# Binex Launch Strategy

**Date:** 2026-03-09
**Goal:** Get 3-5 real users with feedback in 3 months
**Time budget:** 1-2 hours/week

## Positioning

**Headline:** Debuggable runtime for AI agent pipelines

**Hook:** Other frameworks help you launch agents. Binex helps you understand why they broke.

**Unique value:** trace, replay, diff, debug — no other multi-agent framework focuses on debuggability.

**Landscape:**

| Tool | Focus | Binex difference |
|------|-------|-----------------|
| CrewAI | Role-based agents | YAML-first, debuggability |
| LangGraph | State graphs, LangChain ecosystem | Provider-agnostic, replay/diff |
| AutoGen | Conversational agents | DAG pipelines, artifact lineage |
| Prefect/Airflow | Data pipeline DAGs | AI agent-native, not data ETL |

## Target Audience

**Primary:** Developers already building multi-agent systems, struggling with debugging. Using LiteLLM, CrewAI, LangGraph, or custom code.

**Secondary:** Developers starting with AI agents, looking for a simple YAML-first entry point.

## Launch Plan

### Week 1: Launch Wave

| Channel | Post | Language |
|---------|------|----------|
| Reddit r/Python | "Show r/Python: Binex — debuggable runtime for AI agent pipelines" | EN |
| Reddit r/LocalLLaMA | "Built a tool to trace and diff multi-agent workflows (works with Ollama)" | EN |
| Hacker News | "Show HN: Binex — trace, replay and diff AI agent pipelines" | EN |
| Habr | "Как я сделал дебаггер для мультиагентных пайплайнов" | RU |

### Weeks 2-12: Content Drip (1-2 hrs/week)

1. **Useful comments** — find posts where people complain about debugging agents, answer with approach, mention Binex at the end
2. **Ecosystem presence** — PRs to awesome-lists, issues/discussions in LiteLLM repo
3. **Micro-content** — short post every 2 weeks: concrete use case, not advertisement

### Always:

- Respond to issues within 24 hours
- README and docs are the main funnel — keep them polished

## Success Metrics

### 1 month:
- 10-20 stars
- 1-2 issues from strangers
- Binex in 2-3 awesome-lists

### 3 months:
- 3-5 people tried and gave feedback
- Understanding of what people need
- Decision: continue or pivot

### How to measure:
- GitHub stars/forks/clones (GitHub Insights)
- Issues and discussions from strangers
- PyPI downloads

## First Steps (checklist)

1. Create Reddit account, subscribe to r/Python, r/LocalLLaMA, r/MachineLearning
2. Write launch post for Reddit
3. Submit "Show HN" on Hacker News
4. Write article on Habr
5. Find 3-5 awesome-lists and submit PRs
6. Enable GitHub Discussions in the repository
