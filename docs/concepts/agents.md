# Agents

## What is an Agent?

```yaml
nodes:
  summarizer:
    agent: "llm://gpt-4o"
    system_prompt: summarize
    inputs:
      data: "${user.input}"
    outputs: [summary]

  validator:
    agent: "local://my_module"
    system_prompt: validate
    inputs:
      data: "${summarizer.summary}"
    outputs: [validated]

  reviewer:
    agent: "a2a://http://review-service:8000"
    system_prompt: review
    inputs:
      data: "${validator.validated}"
    outputs: [report]
```

An agent is a unit of work in a Binex workflow. Each agent is identified by a URI prefix that determines how it executes. Binex supports five agent types:

| Prefix | Adapter | Description |
|---|---|---|
| `local://` | `LocalPythonAdapter` | In-process async Python callable. Fastest option for custom logic that runs locally. |
| `llm://` | `LLMAdapter` | Direct LLM call routed through litellm. The path after `llm://` specifies the model name (e.g., `gpt-4o`, `claude-3-opus`). |
| `a2a://` | `A2AAgentAdapter` | Remote HTTP agent following the A2A contract: `POST /execute` for task execution, `GET /health` for availability checks. |
| `human://input` | `HumanInputAdapter` | Prompts a human for free-text input via the terminal. The node's `system_prompt` is displayed as the prompt message. Returns an artifact of type `human_input`. |
| `human://approve` | `HumanApprovalAdapter` | Pauses execution and prompts a human to approve (`y`) or reject (`n`). Returns an artifact of type `decision` with content `"approved"` or `"rejected"`. Use with `when` conditionals to branch the workflow. |

## How It Works

When the runtime encounters a node, it reads the `agent` field, extracts the prefix, and dispatches to the corresponding adapter. The adapter receives the node's resolved inputs as artifacts and returns output artifacts. Optional per-node configuration (temperature, api_base, api_key, max_tokens) is passed through the `config` field and forwarded to the adapter.

## Human-in-the-Loop

The `human://` agents enable interactive workflows where human judgment is part of the pipeline.

**Free-text input** — use `human://input` to collect user input at any point:

```yaml
user_input:
  agent: "human://input"
  system_prompt: "What topic would you like content about?"
  inputs: {}
  outputs: [query]
```

**Approval gate** — use `human://approve` with `when` conditionals to branch:

```yaml
review:
  agent: "human://approve"
  system_prompt: "Review and approve the draft"
  inputs:
    draft: "${writer.content}"
  outputs: [decision]
  depends_on: [writer]

publish:
  agent: "local://echo"
  inputs:
    final: "${writer.content}"
  outputs: [result]
  depends_on: [review]
  when: "${review.decision} == approved"
```

See the [draft-review-approve](https://github.com/your-repo/blob/main/examples/draft-review-approve.yaml) example for a complete workflow combining both human agent types.

## Example

A local agent needs only a Python async function:

```python
async def echo(task_id: str, skill: str, artifacts: list) -> list:
    return artifacts  # pass-through
```

Register it as `local://echo` and reference it in any workflow node.

## Related Concepts

- [Workflows](workflows.md) -- agents are organized into DAG-based workflows
- [Artifacts](artifacts.md) -- agents consume and produce artifacts
- [Execution](execution.md) -- each agent invocation creates an execution record
