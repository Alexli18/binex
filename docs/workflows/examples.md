# Workflow Examples

Line-by-line walkthrough of the bundled example workflows.

---

## Simple Pipeline

A two-node pipeline where a producer feeds into a consumer.

```yaml
name: simple-pipeline                # (1)
description: "Simple 2-node pipeline with local adapters"  # (2)
nodes:                                # (3)
  producer:                           # (4)
    agent: "local://echo"             # (5)
    system_prompt: produce              # (6)
    inputs:                           # (7)
      data: "${user.input}"           # (8)
    outputs: [result]                 # (9)
  consumer:                           # (10)
    agent: "local://echo"             # (11)
    system_prompt: consume              # (12)
    inputs:
      data: "${producer.result}"      # (13)
    outputs: [final]                  # (14)
    depends_on: [producer]            # (15)
defaults:                             # (16)
  deadline_ms: 30000                  # (17)
  retry_policy:                       # (18)
    max_retries: 1                    # (19)
    backoff: exponential              # (20)
```

1-2. **name/description** — workflow identifier and optional summary.
3-4. **nodes** — map of node IDs to definitions; dict key becomes the node ID.
5-6. **agent/system_prompt** — `local://echo` selects the adapter; `produce` is the system prompt.
7-8. **inputs** — `${user.input}` resolved at load time from `--var input="..."`.
9. **outputs** — declares this node produces an artifact called `result`.
10-12. **consumer** — second node, same agent, different system prompt.
13. **`${producer.result}`** — runtime reference to producer's output artifact.
14-15. **depends\_on** — consumer waits for producer before executing.
16-20. **defaults** — fallback `deadline_ms` (30s) and `retry_policy` (1 retry, exponential backoff) for all nodes.

**Run it:**

```bash
binex run examples/simple.yaml --var input="hello world"
```

---

## Research Pipeline

A five-node DAG with parallel branches and per-node overrides.

```yaml
name: research-pipeline              # (1)
description: "Multi-agent research pipeline with 5 nodes"  # (2)
nodes:
  planner:                            # (3)
    agent: "local://planner"          # (4)
    system_prompt: planning.research    # (5)
    inputs:
      query: "${user.query}"          # (6)
    outputs: [execution_plan]         # (7)
  researcher_1:                       # (8)
    agent: "local://researcher"
    system_prompt: research.search
    inputs:
      plan: "${planner.execution_plan}"  # (9)
      source: arxiv                   # (10)
    outputs: [search_results]
    depends_on: [planner]             # (11)
  researcher_2:                       # (12)
    agent: "local://researcher"
    system_prompt: research.search
    inputs:
      plan: "${planner.execution_plan}"
      source: google_scholar          # (13)
    outputs: [search_results]
    depends_on: [planner]             # (14)
  validator:                          # (15)
    agent: "local://validator"
    system_prompt: analysis.validate
    inputs:
      results_1: "${researcher_1.search_results}"  # (16)
      results_2: "${researcher_2.search_results}"  # (17)
    outputs: [validated_results]
    depends_on: [researcher_1, researcher_2]       # (18)
    retry_policy:                     # (19)
      max_retries: 2                  # (20)
      backoff: exponential
  summarizer:                         # (21)
    agent: "local://summarizer"
    system_prompt: analysis.summarize
    inputs:
      validated: "${validator.validated_results}"
    outputs: [summary_report]         # (22)
    depends_on: [validator]
    deadline_ms: 60000                # (23)
defaults:
  deadline_ms: 120000                 # (24)
  retry_policy:
    max_retries: 1
    backoff: exponential
```

1-2. **name/description** — workflow identifier and summary.
3-7. **planner** — entry node (no dependencies). `${user.query}` from `--var`. Emits `execution_plan`.
8-11. **researcher\_1** — depends on planner, consumes `execution_plan`. `source: arxiv` is a literal input.
12-14. **researcher\_2** — parallel branch, same agent, different `source`. Both researchers run concurrently.
15-18. **validator** — fan-in node, `depends_on: [researcher_1, researcher_2]`. Merges both outputs.
19-20. **retry\_policy** — node-level override: 2 retries instead of default 1.
21-23. **summarizer** — terminal node. `deadline_ms: 60000` overrides the default 120s.
24. **defaults** — fallback settings for nodes without overrides.

**Run it:**

```bash
binex run examples/research.yaml --var query="LLM agent architectures"
```

### DAG Shape

```
planner
  ├── researcher_1 ──┐
  └── researcher_2 ──┤
                     validator
                       └── summarizer
```

Nodes at the same depth with no mutual dependency (researcher\_1, researcher\_2) execute in parallel automatically.

---

## Draft → Review → Approve (Human-in-the-Loop)

A content pipeline where AI drafts, reviews, and revises, then a human makes the final approval decision.

```yaml
name: draft-review-approve                    # (1)
description: "Content pipeline with AI revision and human approval gate"

nodes:
  user_input:                                  # (2)
    agent: "human://input"
    system_prompt: "What topic would you like content about?"
    inputs: {}
    outputs: [query]

  draft:                                       # (3)
    agent: "llm://ollama/gemma3:4b"
    system_prompt: "Write a detailed first draft on the given topic."
    inputs:
      topic: "${user_input.query}"
    outputs: [content]
    depends_on: [user_input]

  review:                                      # (4)
    agent: "llm://ollama/gemma3:4b"
    system_prompt: "Review this draft critically. List strengths, weaknesses, and recommendations."
    inputs:
      draft: "${draft.content}"
    outputs: [feedback]
    depends_on: [draft]

  revise:                                      # (5)
    agent: "llm://ollama/gemma3:4b"
    system_prompt: "Revise the draft incorporating the editor's feedback."
    inputs:
      original_draft: "${draft.content}"
      editor_feedback: "${review.feedback}"
    outputs: [revised_content]
    depends_on: [review]

  human_review:                                # (6)
    agent: "human://approve"
    system_prompt: "Review the revised content and approve or reject"
    inputs:
      revised: "${revise.revised_content}"
    outputs: [decision]
    depends_on: [revise]

  output:                                      # (7)
    agent: "local://echo"
    inputs:
      final: "${revise.revised_content}"
    outputs: [result]
    depends_on: [human_review]
    when: "${human_review.decision} == approved"

  discard:                                     # (8)
    agent: "local://echo"
    inputs: {}
    outputs: [notice]
    depends_on: [human_review]
    when: "${human_review.decision} == rejected"
```

1. **name** — workflow identifier.
2. **user\_input** — `human://input` prompts the user for a topic via the terminal.
3. **draft** — LLM generates the initial content based on user input.
4. **review** — LLM acts as editor, providing critical feedback.
5. **revise** — LLM rewrites the draft incorporating feedback. Note: receives both original draft and feedback as separate inputs.
6. **human\_review** — `human://approve` pauses execution and shows the revised content. The user decides `y` (approved) or `n` (rejected).
7. **output** — `when` conditional: only runs if the human approved. Passes the revised content through.
8. **discard** — `when` conditional: only runs if the human rejected.

### DAG Shape

```
user_input
  └── draft
        └── review
              └── revise
                    └── human_review
                          ├── output   (when approved)
                          └── discard  (when rejected)
```

**Key patterns demonstrated:**

- **`human://input`** — collecting user input at workflow start
- **`human://approve`** — approval gate before final output
- **`when` conditionals** — branching based on human decision
- **Multi-input node** — `revise` receives both original draft and feedback

**Run it:**

```bash
binex run examples/draft-review-approve.yaml
```
