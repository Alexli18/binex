# Team Roles Design

**Date:** 2026-03-18
**Status:** Approved
**Scope:** Define roles, responsibilities, communication protocol, and skills for the Binex agent team

---

## Problem

The current team operates without formal role definitions. Agents overlap in responsibilities (designer vs frontend-dev), have unclear boundaries (meta-agent with dual roles), and lack a standard communication protocol. This leads to duplicated work, confused agents, and unpredictable behavior.

## Goals

1. Each agent has ONE clear responsibility
2. Each agent knows exactly who to talk to and when
3. Team lead stays in control of all decisions
4. Skills are auto-loaded so agents work at full capability from the start

---

## Team Composition

10 agents + team-lead (Claude Code in the main session).

| Agent | Single Responsibility |
|-------|----------------------|
| product-manager | Translates user vision into tasks for the team |
| architect | System design, API contracts, technical consistency |
| designer | UX ownership + writes UI code (Tailwind, components) |
| frontend-dev | React logic, state management, API integration |
| backend-dev | Python backend (FastAPI, CLI, models) |
| qa-tester | Tests, regression detection, bug reporting |
| docs-maintainer | Documentation (README, CLAUDE.md, docs/) |
| devops | CI/CD, GitHub Actions, releases, branch hygiene |
| meta-agent | Smart context compaction (context health manager) |
| crew-advisor | Team composition advisor (suggests who to spawn/shutdown) |

---

## Role File Structure

Each role is defined in `docs/team/<agent-name>.md` with the following sections:

```
## Роль
One sentence — who this is and why they exist

## Зона ответственности
What they do, which files/areas they own

## Не делает (границы)
What they MUST NOT do — to prevent territory overlap

## Взаимодействие
Who assigns tasks, who they report to, who they collaborate with

## Протокол завершения
What they send and to whom after completing a task

## Skills
Skills to load via Skill tool at the start of each session

## Промпт
The exact text passed to the agent when spawned
```

---

## Skills per Agent

| Agent | Skills |
|-------|--------|
| frontend-dev | `frontend-design`, `react-flow-implementation` |
| designer | `ui-ux-pro-max`, `frontend-design` |
| qa-tester | `qa-expert`, `qa-testing-methodology`, `testing-ai-agents` |
| backend-dev | `fastapi-expert`, `async-python-patterns` |
| architect | `binex-a2a-development` |
| docs-maintainer | `opensource-readme-generator` |
| devops | — (standard tools: bash, gh CLI) |
| product-manager | — (reasoning-based role) |
| meta-agent | — (communication-based role) |
| crew-advisor | — (communication-based role) |

---

## Communication Protocol

### After every task completion, each agent sends TWO messages:

```
1. agent → meta-agent:
   "Закончил: [task description]
    Context: ok / warning / critical"

2. agent → team-lead:
   "Закончил: [task description]. Idle."
```

### Meta-agent reacts to context signals:

```
Context: ok       → meta-agent does nothing
Context: warning  → meta-agent crafts smart brief, triggers compact
Context: critical → meta-agent urgently triggers compact
```

### Smart compact flow:

```
agent → meta-agent: "context:warning. Working on: X. Done: Y. Remaining: Z"
meta-agent → agent: "Before compact remember: [brief summary of critical state]"
agent: runs /compact with preserved context
agent: continues work
```

### Crew-advisor flow (triggered on idle signal):

```
agent → team-lead: "Закончил: X. Idle."
team-lead → crew-advisor: "Agent X idle. TaskList: [current tasks]"
crew-advisor → team-lead: "Task Y needs a security-expert (not in team)"
                       or "Team composition ok, assign X to task Z"
team-lead: makes final decision (spawn / reassign / shutdown)
```

---

## Designer vs Frontend-dev Boundary

This is the most critical boundary to maintain:

| Question | Owner |
|----------|-------|
| "Why does this look this way?" | designer |
| "How does this work technically?" | frontend-dev |
| UX decisions, spacing, typography | designer |
| React state, hooks, API calls | frontend-dev |
| Tailwind classes, component visuals | designer |
| React Flow nodes, complex logic | frontend-dev |

Designer writes UI code. Frontend-dev writes logic code. Neither crosses this line.

---

## Meta-agent Design

**Single responsibility:** Smart Context Manager

**Triggers:** Only reacts to `context:warning` or `context:critical` signals from agents.

**Does NOT:**
- Monitor agents continuously
- Make lifecycle decisions (spawn/shutdown)
- Track task progress
- Advise on team composition (that's crew-advisor)

---

## Crew-advisor Design

**Single responsibility:** Team Composition Advisor

**Triggers:** Only when team-lead explicitly asks (after receiving an idle signal from an agent).

**Does NOT:**
- Spawn or shutdown agents itself
- Make decisions — only advises
- Monitor agents continuously
- Write any code or files

---

## Deliverables

- [ ] `docs/team/team-lead.md`
- [ ] `docs/team/product-manager.md`
- [ ] `docs/team/architect.md`
- [ ] `docs/team/designer.md`
- [ ] `docs/team/frontend-dev.md`
- [ ] `docs/team/backend-dev.md`
- [ ] `docs/team/qa-tester.md`
- [ ] `docs/team/docs-maintainer.md`
- [ ] `docs/team/devops.md`
- [ ] `docs/team/meta-agent.md`
- [ ] `docs/team/crew-advisor.md`
- [ ] `docs/team/README.md`
- [ ] Update `start_day` skill to reference role files and load skills
