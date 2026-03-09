# binex start

## Synopsis

```
binex start [OPTIONS]
```

## Description

Interactive wizard that guides you through creating a complete agent workflow. Asks questions step-by-step — choose a pipeline pattern, select an LLM provider, configure API keys — and generates a ready-to-run `workflow.yaml`.

The wizard uses DSL patterns from `binex scaffold` and the provider registry to produce valid workflow files without manual YAML editing.

## Workflow

1. **Choose a pipeline pattern** — select from 9 built-in patterns (simple, diamond, fan-out, fan-in, map-reduce, etc.) or enter a custom DSL expression
2. **Select an LLM provider** — pick from 8 supported providers (OpenAI, Anthropic, Gemini, Ollama, Groq, Mistral, DeepSeek, Together)
3. **Configure the model** — choose a specific model from the provider's catalog
4. **Set API key** — enter or confirm the API key (reads from environment if available)
5. **Name your workflow** — give it a descriptive name
6. **Generate** — creates `workflow.yaml` in the current directory

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--output` / `-o` | `Path` | `workflow.yaml` | Output file path |

## Example

```bash
# Launch the interactive wizard
binex start

# Then run the generated workflow
binex run workflow.yaml --var topic="quantum computing"
```

## Available Patterns

| Pattern | DSL | Description |
|---|---|---|
| simple | `A -> B` | Linear two-node pipeline |
| chain | `A -> B -> C` | Three-node chain |
| diamond | `A -> B, C -> D` | Diamond dependency |
| fan-out | `A -> B, C, D` | One-to-many parallel |
| fan-in | `A, B, C -> D` | Many-to-one aggregation |
| fan-out-fan-in | `A -> B, C, D -> E` | Parallel with aggregation |
| map-reduce | `A -> B, C -> D` | MapReduce pattern |
| pipeline-5 | `A -> B -> C -> D -> E` | Five-stage pipeline |
| review | `A -> B -> C -> D` | Draft-review-approve chain |

## Supported Providers

| Provider | Prefix | Example Models |
|---|---|---|
| OpenAI | `openai/` | gpt-4, gpt-4o, gpt-3.5-turbo |
| Anthropic | `anthropic/` | claude-sonnet-4-20250514, claude-haiku-4-5-20251001 |
| Google Gemini | `gemini/` | gemini-pro, gemini-1.5-pro |
| Ollama | `ollama/` | llama3, mistral, codellama |
| Groq | `groq/` | llama3-70b, mixtral-8x7b |
| Mistral | `mistral/` | mistral-large, mistral-medium |
| DeepSeek | `deepseek/` | deepseek-chat, deepseek-coder |
| Together | `together_ai/` | llama3-70b, mixtral-8x7b |

## See Also

- [binex run](run.md) — execute the generated workflow
- [binex scaffold](scaffold.md) — generate workflows from DSL without the wizard
- [binex explore](explore.md) — browse results after running
