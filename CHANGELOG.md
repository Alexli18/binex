# Changelog

## Unreleased

## v0.8.0

*2026-08-31 — four months of work: the debugging toolkit gets its regression half.*

Binex could already tell you what a run did. This release is about telling you what **changed** — and stopping a change from reaching main. Eval suites and `binex freeze` turn diff/bisect from post-mortem tools into a merge gate; observer mode debugs a run that never used Binex; workspace, binary artifacts and dynamic `foreach` widen what a workflow can be; resume, node caching, fallback chains and auto-repair make a long run survivable.

### Upgrade notes

- **`binex replay` can now exit 2.** If a node whose cached output the replay would reuse changed in the workflow file since the original run, the replay is refused rather than silently mixing old outputs with a new workflow. Pass `--allow-drift` to keep the old behaviour, or replay from an earlier step. (#131)
- **Eval `min_similarity` is measured differently for structured output.** It is now the fraction of unchanged leaf fields rather than a character ratio, so thresholds tuned earlier will shift — reordered keys go from 0.63 to 1.0, one changed field of ten from 0.99 to 0.9. Review suite thresholds and re-bless baselines; `docs/eval.md` has the measured table. Text output is unaffected. (#132)
- **`shell_command` now runs only an allowlist** of executables. If a workflow relied on it running arbitrary binaries, set `BINEX_SHELL_ALLOW="..."` or `BINEX_SHELL_ALLOW_ALL=1`. (#58)
- **`fetch_url` / `http_request` reject private addresses.** For local use, set `BINEX_ALLOW_PRIVATE_URLS=1`. (#59)
- **`binex bisect` is a command group** (`runs` + `history`). The bare `binex bisect <good> <bad>` form is unchanged. (#72)

### Documentation

- **Framework comparison** — a `docs/comparison.md` (and a short table in the README) covering Binex vs. LangGraph / CrewAI / AutoGen, honest about where each tool's weight sits: the others build agents, Binex debugs them. (#28)
- **Debugging & Observability guide** — a single `docs/guides/debugging.md` that walks the whole toolkit end-to-end (debug → trace → diagnose → diff/semantic → bisect → eval → cost → replay → observer), with a "which tool, when" table, so new users see the full power available. (#30)
- **Conscious Testing Boundaries** — `docs/contributing/testing.md` now states, per module, where coverage stops on purpose and why (interactive TUI paths, provider-facing branches, browser-only rendering), so a low percentage reads as a documented decision rather than an oversight. (#124)
- **Fresh-eyes documentation pass** — corrected stale test/coverage counts, clarified navigation, and added the pages that features had shipped without. (#128)
- **Eval, MCP and import guides** — `docs/eval.md`, `docs/mcp-server.md`, `docs/import.md` and `docs/dev/otel-mapping.md` for the capabilities landing in #121, plus `docs/comparisons.md`. (#121)

### Security

- **Scaffolded agent binds to loopback (#61)** — `binex scaffold agent` generated a `server.py` that ran `uvicorn.run(app, host="0.0.0.0", ...)`, exposing the new agent to the whole local network with no auth. The generated server now defaults to `127.0.0.1` and takes a `--host` flag (mirroring `binex ui`); exposing it is an explicit `--host 0.0.0.0` choice.
- **SSRF protection for `fetch_url` / `http_request` (#59)** — the HTTP tools now resolve a URL's host and reject private, loopback, link-local, reserved, multicast, and unspecified addresses (RFC 1918, `127.0.0.0/8`, `169.254.0.0/16` cloud metadata, `::1`, `fc00::/7`, `0.0.0.0`) before connecting. Redirects are followed manually and every hop is re-validated, so a public URL can't `302` into the metadata service; only `http`/`https` schemes are allowed. Opt out for local use with `BINEX_ALLOW_PRIVATE_URLS=1`. Matters on servers running `binex gateway` / `binex scheduler`.
- **`shell_command` executable allowlist (#58)** — the built-in shell tool no longer runs arbitrary binaries chosen by the model. It now permits only a conservative default allowlist (`ls`, `cat`, `grep`, `wc`, …); `rm`, `curl`, `python -c ...`, etc. are blocked unless explicitly allowed via `BINEX_SHELL_ALLOW="python3,..."` or `BINEX_SHELL_ALLOW_ALL=1`. An absolute path can't bypass the check (it matches on the basename). A prompt-injected or confused agent can no longer run destructive or exfiltrating commands by default.

### Features

- **Observer mode — CrewAI task/agent attribution (full build)** — observer mode (#73) now groups an observed CrewAI run by *task* and *agent*, not just a flat call list. Capture moved to wrapping `litellm.completion`/`acompletion` (CrewAI reassigns `litellm.callbacks` mid-run, which silently dropped the prototype's callback-based observer); attribution wraps `crewai.Agent.execute_task` so each captured call is tagged with the running `(task, agent)` via a context variable. On flush, calls become a **parent task node** (`crewai://<role>`) with per-call **child records** (`parent_task_id`), so `binex trace` shows tasks with their agent's calls nested. Task node ids are **name-based** (the synthesized "pseudo-spec"), so `binex diff` aligns two observed runs of the same crew out of the box. Everything stays guest-safe: if CrewAI is absent or its API drifted, capture still works (flat trace) with a logged warning, never a crash — and the store auto-initializes so a first-time user needs zero config. Ships with a real-CrewAI newcomer-path integration test (mocked LLM transport only), a crash-safety test, and a CI matrix (`observe-crewai`) pinning the tested CrewAI version. (#73)
- **UI: first-run guided tour** — the first time a user opens the Web UI on an empty Dashboard (no stored runs), a lightweight 5-step walkthrough (built on driver.js) spotlights the key areas in order: sidebar navigation → Editor → Scaffold → Run a workflow → inspect results. It auto-starts only for a genuine first run and remembers it's been seen (`localStorage`), so it never nags an existing user or reappears after being skipped/completed. Re-launchable anytime via **"Take the guided tour"** in the help panel. (#32)
- **Docker: CLI + Web UI in a container** — `docker/Dockerfile.webui` (multi-stage: builds the React frontend, installs Binex with it, serves the Web UI on 8420) and `docker/docker-compose.webui.yml` for `docker compose up`, with a `binex-data` volume for run/artifact/workspace persistence, API keys via env, and an optional Ollama sidecar (`--profile local`) for a fully-local stack. The image ships without `git` (the git-backed freeze/bisect/provenance features degrade gracefully to a no-op, and a container run has no repo to capture); the Dockerfile documents the one-line add for using them against a mounted repo. Distinct from the existing `docker/docker-compose.yml` (the A2A agent-server mesh). (#33)
- **UI: "Files changed" per node in the debug view** — for a run with a [workspace](#), each node's detail now lists the files it changed in the shared git workspace (#75). A new `GET /runs/{id}/files-changed` reconstructs the per-node file diffs from the workspace repo after the fact (reading each `node: <id>` commit's changed files, since the in-memory node→commit map is gone once the run ends). Runs without a workspace simply show nothing. (#75)
- **UI: binary-artifact thumbnails in the lineage graph** — the lineage API now flags binary nodes (`binary`/`mime`/`blob_url`) and the lineage graph renders an inline **image thumbnail** on image artifacts (with a mime tag), instead of a JSON-envelope preview. Selecting one shows the full-size image, an audio player, or a download link in the detail panel. Reuses the blob-serving endpoint (#76). (#76)
- **UI: `×N runtime` badge on `foreach` nodes** — the visual editor now parses a node's `foreach` field and shows an amber `×N runtime` badge on it, so dynamic fan-out (#77) is visible *before* the run expands it (one node with the badge, not N unknown workers). Ordinary nodes are unaffected. (#77)
- **UI: Replay button for observed-run calls** — in the debug view of an `observed` run (#73), each captured LLM call's Replay button now opens a **single-call replay** dialog: swap the model and/or edit the prompt, re-send, and see the original vs. new response **side by side** with a changed/identical badge, the replay cost (flagged as experimentation), and any requested-but-not-executed tool calls. Powered by the merged `POST /runs/{id}/calls/{call_id}/replay` endpoint (#74). Non-observed runs keep the existing from-step node replay. (#74)
- **UI: inline previews for binary artifacts in the debug view** — building on the binary-artifact backend, the debug report now flags binary output artifacts (`binary`/`mime`/`size`/`blob_url`; the envelope is kept intact, not stringified) and the debug view renders an **inline preview** when one is expanded: `<img>` for images, an `<audio>` player, an inline PDF, or a download link otherwise — with a mime badge on the row. Detection is robust (the flag *or* the envelope's `kind`) and degrades gracefully when a payload URL is absent. (#76)
- **UI backend: binary previews & per-call replay endpoints** — the Web UI API can now serve binary artifacts and drive single-call replay. `GET /runs/{id}/artifacts` flags binary artifacts (`binary: true`, `mime`, `size`, `blob_url`) and a new `GET /runs/{id}/artifacts/{artifact_id}/blob` streams the raw payload with its correct `Content-Type` — the foundation for inline image/audio/PDF previews and lineage thumbnails (#76). `POST /runs/{id}/calls/{call_id}/replay` re-runs one captured LLM call (optional `model`/`prompt`/`mock_response`) and returns the original-vs-replay comparison — the foundation for the observed-run "Replay" button (#74/#73). Backend only; the React components consume these next. (#76, #74)
- **Stateless single-call replay of observed runs** — because observer mode (#73) captures each call's *complete* request (messages, model), any one call from an observed run can be replayed statelessly — all of the framework's memory/context is already baked into the captured messages, so nothing needs reconstructing. `binex replay <run-id> --call <call-id> [--model X] [--prompt-file F]` re-sends the call (optionally with a swapped model or edited prompt) and shows the original vs. new response side by side — the dominant iteration loop ("this agent answered badly → try another prompt/model on the same input") without touching the user's codebase. Deliberately bounded: replay **stops at tool use** (a requested tool call is displayed with its arguments but never executed), there is **no downstream continuation** (the result is a comparison artifact, not fed back into the pipeline), and the replay's cost is recorded as `source: replay` and **excluded from run-level cost aggregation** (shown as experimentation spend). `--mock-response` allows fully offline verification (pairs with `binex observe-demo`). (#74)
- **Observer mode (prototype) — debug an existing CrewAI run without migrating it** — the `crewai://` adapter asks users to move their Crew *inside* a Binex workflow, and even then it runs as one opaque node. Observer mode watches an existing run in place — two lines in the user's own code: `with observe("my-run"): crew.kickoff()`. Interception is at the **LiteLLM** layer (a custom callback), so it captures the full raw request (messages, model, params) and response of every call with exact token/cost accounting — which is also what makes single-call replay (#74) possible. The observed run lands in the normal `.binex` store (per-call records, costs, response artifacts), marked `observed` and shown as such in `binex debug`, so opaque LLM spend becomes a local, private per-call cost breakdown. As a guest in someone else's process, `observe()` **never crashes the user's run** — every internal error is swallowed to a log warning. This is the validation-gate prototype for #73; per-agent/task attribution and the replay UI build on top once the approach is validated. Includes `binex observe-demo` — a fully offline (LiteLLM `mock_response`, no API key) simulated multi-agent run that exercises the real capture path so the trace + per-call cost breakdown can be verified without a real Crew. (#73)
- **Binary artifacts — images, audio, PDFs as first-class node outputs** — the artifact store was JSON-only, so an image generator, TTS, or PDF renderer had no native way to emit its result into the DAG. An artifact is now a JSON envelope plus, for binaries, a **content-addressed payload**: the envelope `{kind: "binary", mime, size, sha256, path}` is the artifact's `content` (JSON artifacts unchanged — fully backward compatible), and the bytes live at `.binex/artifacts/blobs/<sha256>`. Content addressing gives **free deduplication** (an asset flowing through five nodes is stored once) and a ready-made cache key — node caching (#68) already hashes artifact content, so the sha in the envelope is picked up for free. Binaries feed into LLM nodes **routed by mime type**: `image/*` into a vision-capable model as a real image message (LiteLLM multimodal), while a model without vision (or audio/video) gets a textual descriptor plus the file so the agent can pass it onward without "seeing" it — a runtime warning flags the downgrade. `binex clean blobs` garbage-collects blobs no run references (with `--dry-run`). Size-limited (100MB) with no transcoding or image-diffing in v1; a blob-serving UI (previews, lineage thumbnails) and a native `media://` adapter are deferred follow-ups. (#76)
- **Workspace — a shared, git-snapshotted filesystem for multi-agent runs** — many workflows are agents collaborating on an *accumulating body of files* (a coder writes `src/`, an asset agent fills `assets/`, a tester runs the build), which pipe-passed artifacts can't model. A run can now declare a `workspace` (empty, copied from a local dir, or a git clone); it lives at `.binex/workspaces/<run_id>/` and **is itself a git repository**. After each write node an automatic commit tagged `node: <id>` gives, for free: per-node file diffs (`files_changed`), file-level lineage, rollback, and **restore points** so replay/resume work for file-based flows. LLM nodes get `read_file`/`write_file`/`list_files` tools **jailed to the workspace root** — absolute paths, `..`, and symlink escapes are all rejected (critical alongside `shell_command`, #58); `local://`/`python://` handlers receive the root via `task.config["_workspace_root"]`. Concurrency is correct-by-construction: nodes declare `workspace: read` or `workspace: write`, and an async readers-writer lock serializes writers while readers parallelize. Pipe-passed JSON artifacts remain the mechanism for small structured data — the two coexist. Workspaces are heavy, so `binex clean workspaces [--older-than N] [--dry-run]` reclaims them. v1 defers per-node worktree merge, and debug/diff surfaces land in a follow-up. (#75)
- **Dynamic fan-out — runtime `foreach` nodes** — `scatter` fixes N at load time; real workloads decide N at runtime (a planner picks the subtasks, a lister finds 600 episodes). A node with `foreach: <mapper>` stays a single placeholder in the static DAG and, when the mapper emits its array, **expands at runtime** into one worker per item plus an aggregator — the scheduler stays static ("more nodes appeared"), reusing the same DAG-mutation path rather than a dynamic scheduler. Guardrails are mandatory and up-front: a `max_items` cap (default 100) and a pre-expansion **budget estimate** stop a mapper that returns 10 000 items (by bug or prompt injection) *before* any worker runs. `on_item_failure: continue` (default) hands the aggregator the successes plus a failure list without failing the run; `fail_fast` blocks. Each item is keyed by content hash (or an explicit `item_key` JSONPath) rather than list index, so node cache (#68) and cross-run diff still match "episode 42" when the list shifts. Downstream nodes that depended on the foreach node are transparently rewired to its aggregator. v1 is single-level (no nested foreach) and non-streaming. (#77)
- **Semantic diff (`binex diff --semantic`)** — tells "reworded the same answer" from "the answer actually changed", instead of drowning you in textual noise. For each node whose content differs, a cheap model answers **narrow, targeted questions** — did the JSON structure change? did factual claims change? did only tone/format change? — at **temperature 0** with a per-question confidence, so verdicts are stable and auditable. Structure/facts changes are flagged meaningful (⚠); tone/format-only changes collapse as cosmetic; a judge error or unparseable reply fails safe (conservatively "changed", never silently collapsed). This is the first feature where Binex spends *your* tokens, so it is strictly opt-in and cost-transparent: nothing runs without `--semantic`, and it prints a token/dollar **estimate and asks for confirmation before any call** (`--yes` to skip). `--semantic-model` is configurable and works fully local via Ollama (shown as free). `--json` adds a `semantic` array. Raises the signal quality of `binex diff`, `bisect`, and `eval`, which all consume diff verdicts. (#71)
- **`binex bisect history` — find the commit that broke pipeline quality** — a `git bisect run` for agent workflows. Given a good and a bad commit (or run ID, resolved to its recorded commit), it binary-searches the ancestry path, re-running the workflow *as it existed at each probe commit* and judging pass/fail with the eval criterion (#60: the workflow's own assertions, plus an optional `--baseline` diff with `--min-similarity`/`--max-*-delta`). Each probe runs in an isolated **git worktree**, so the working tree and `HEAD` are never touched; a commit whose workflow file is missing or can't be evaluated is **skipped**, never falsely blamed. Reports the first bad commit and hands off to the node-level bisect to find the offending node within it. Node caching (#68) keeps it affordable. `binex bisect` is now a group (`runs` + `history`); the bare `binex bisect <good> <bad>` form is unchanged. (#72)
- **Git provenance in run metadata** — every run now records the commit it executed at (`git_sha`) and whether the working tree was dirty (`git_dirty`), captured best-effort from the workflow's repo (missing git / non-repo / errors are silent — no run ever fails over this). Surfaced in `binex debug` (`Commit: <sha> (dirty)`) and its `--json`. This is the cheap, ship-now half of history bisect (#72): it maps runs to commits so a future `binex bisect history` can binary-search the commit that broke pipeline quality. (#72)
- **Workflow eval & regression testing** — turn diff/bisect from a post-mortem tool into a pre-merge safety net. Nodes can declare block-on **assertions** in YAML (`contains`/`lacks`/`matches`/`equals`/`min_length`/`max_length` on output, `cost_max`/`latency_max_ms` on metrics, and an LLM-as-judge `judge` rubric); a failed assertion fails the node — and its dependents — on every run, not just during eval. The new `binex eval <workflow>` command runs the workflow and exits non-zero on any assertion/node failure, and with `--baseline <run-id>` diffs the fresh run against a stored "golden" run using the existing diff engine, failing on divergence beyond `--min-similarity` / `--max-latency-delta-ms` / `--max-cost-delta` (a node status change always diverges). Judge calls and unparseable judge replies **fail closed** so a broken judge can't green-light a regression. Ships with a GitHub Actions recipe for running evals on PRs that touch workflow YAML or prompts. Foundation for `binex bisect` (#72). (#60)
- **`binex freeze` — pipeline lockfile & drift detection** — writes a `binex.lock` (a package-lock.json for a pipeline): per node, the agent, resolved model, and content hashes of the prompt, parameters, and tools. `binex freeze --check` and `binex run --frozen` report exactly what drifted since the lock — half the answer to "why did yesterday's run behave differently", before any debugging. The lock is honest about pinnability: `gpt-4o` and other bare aliases are marked `pinned: false` (the provider changes them underneath), while dated snapshots (`gpt-4o-2024-11-20`) and digests are `pinned: true`. (#69)
- **Generalized cost tracking** — cost is no longer assumed to be token-based. A `local://`/`python://` handler that accepts a `report_cost` parameter can declare its own cost — `report_cost(seconds=7200, unit_price=0.0001)`, `report_cost(characters=5000, unit_price=...)`, `report_cost(requests=1, unit_price=...)`, or an explicit `report_cost(cost=...)`. Records gain `unit` (`tokens`/`seconds`/`characters`/`requests`/`custom`), `quantity`, `unit_price`, and `provenance` (`litellm`/`declared`/`manual`); existing token records default to `tokens`/`litellm` (backward compatible, with a sqlite migration). Aggregations, the cost dashboard, and budgets consume the generalized records transparently, and `binex cost simulate` leaves non-token costs unchanged across model swaps. (#79)
- **Progress protocol & heartbeat timeouts** — long-running non-LLM nodes (Whisper, rendering, training) can report progress so they're visibly alive instead of being killed by the default deadline. A `local://`/`python://` handler that accepts a `report_progress` parameter calls `report_progress(fraction, message)`; subprocess/`a2a://` agents use the binex-trace SDK's new `trace.progress(...)`. Progress surfaces as a `node:progress` runtime event (per-node UI progress) and a trace event. A new `heartbeat_timeout_ms` node field applies the timeout to **silence** rather than total duration — a node that keeps reporting stays alive, while `deadline_ms` remains an optional hard cap. (#78)
- **Repair escalation** — combines auto-repair (#65) with fallback chains (#66). With `repair: { escalate: true }` and a fallback chain, a node whose schema repair is exhausted promotes to the next model and retries the repair ladder there (trace event `escalated: schema_repair_exhausted`, distinct from transport-error fallback). This turns the two reliability features into an automatic cost optimizer — route everything through a cheap model, let the strong model catch only the hard tail. `--no-fallback` disables escalation too. (#67)
- **Model fallback chains** — a node can list `fallbacks: [model2, model3]`; when the primary model fails on an infrastructure error (rate limit `429`, `5xx`, timeout, model-not-found, or auth `401` with a loud warning), Binex moves to the next model instead of failing the whole run. It never falls back on a model that answered but poorly (that's auto-repair). For reproducibility — silent model swaps would corrupt diff/bisect/eval — each execution records `requested_model` and `actual_model`, the swap is stored on `artifact.metadata.fallbacks`, and `binex run --no-fallback` (or `BINEX_NO_FALLBACK=1`) disables the chain for clean benchmarks. `binex validate` warns when a fallback has a smaller context window than the primary or lacks function-calling while the node declares tools. (#66)
- **Node caching** — reuse a node's result when nothing that affects its output has changed, so editing a downstream prompt no longer forces re-running (and re-paying for) unchanged upstream nodes. The cache key is a content hash of the agent, resolved prompt, model parameters, tools, and input-artifact content; a hit is served at `$0` with a distinct `node:cache_hit` trace event pointing to the source run. Opt-in via per-node `cache: true` or run-level `binex run --cache`; `binex run --offline` runs only from cache (a miss fails the node — VCR-style iteration). New `binex clean cache [--older-than DAYS] [--dry-run]` clears the cache. (#68)
- **Auto-repair for structured output** — instead of failing (or blindly re-running) a node whose output doesn't match its `output_schema`, Binex now repairs it via a cheapest-first ladder: (1) **deterministic repair**, always on and zero-token — strips markdown fences, extracts the first balanced JSON value, drops trailing commas, and replaces the artifact content with clean JSON for downstream nodes (works for every agent type); (2) **native structured output** — `llm://` nodes whose model supports it get the schema passed into the completion call (`response_format`), detected per-model; (3) **feedback loop** — `repair: { max_attempts: N }` re-asks the model in-context with the validation errors, up to N times (`local://`/`a2a://` stay fail-fast). Repair tokens are counted in run cost; the artifact records `metadata.repair_attempts` and which step succeeded. (#65)

- **Event-driven scheduler** — the orchestrator now dispatches each node as soon as its dependencies complete, waking on the first completion (`asyncio.wait(FIRST_COMPLETED)`) instead of awaiting a whole batch. A slow node no longer blocks nodes whose dependencies already finished, and the busy-wait polling loop is gone. Combined with the concurrency cap, wide DAGs are both faster and safe. (#56)
- **Concurrency cap** — the orchestrator no longer dispatches unlimited nodes at once. A `concurrency` workflow field caps in-flight node execution, as a global scalar (`concurrency: 8`) or a per-provider mapping (`concurrency: {default: 8, openai: 5, ollama: 1}`). Providers are derived from the agent URI; a node holds a global slot plus its provider slot (acquired global-first, so no deadlock). Configurable via the `BINEX_MAX_CONCURRENCY` env var (default `8`); the workflow field takes precedence. Prevents wide fan-out (e.g. `scatter` with N=50) from tripping provider rate limits. (#55)
- **`binex resume <run-id>`** — continue a failed or interrupted run from where it stopped. Completed nodes are cached (artifacts reused, budget not re-spent); failed, timed-out, pending, and orphaned-running nodes are re-executed. The resumed run is a new immutable child linked via `resumed_from`. Partitioning is by node status (not a topological prefix), so parallel-branch failures resume correctly. Per-node drift detection re-runs only nodes whose definition changed; a topology change is refused unless `--force`. `cancelled`/`stopped` runs resume with a warning; `running` runs are refused without `--force` to avoid double execution. `--from <node>` forces re-execution from a node and its descendants. Budget is cumulative across the resume chain. (#54)
- **`binex cost simulate`** — estimate what a run would cost on a different model from its stored token counts and litellm pricing, with **zero LLM calls**. `--node NODE --model M` swaps one node; `--all-nodes M` re-prices the whole pipeline. Results are shown as a range, not a point: the swapped node gets a ±10% tokenizer band, nodes downstream of the swap get a wider band (a different model may change output length, cascading into downstream inputs), and unpriced models keep the original cost and are flagged. `--json` for machine-readable output. (#70)
- **Eval suites, MCP server, and OTel trace import** — three capabilities landing together. **Eval suites** promote the single-workflow eval (#60) to a declarative suite: a `suite.yaml` lists cases with their inputs, assertions, and thresholds, `binex eval run` executes them (`--parallel N`), `binex eval bless` records a run as the case's baseline, and `binex eval baselines` lists what is blessed; `--format github` emits `::error`/`::warning` annotations and `--strict-baseline` turns a missing baseline into a failure, so a suite is a merge gate rather than a report. The original single-workflow form lives on as `binex eval golden`. **MCP server** — `binex mcp serve` exposes ten tools over stdio (list/run workflows, run status, debug a node, diagnose, diff, replay a node, run an eval suite, fetch an artifact), so an AI client can drive and inspect Binex without leaving the chat; register with `claude mcp add binex -- binex mcp serve`. **OTel import** — `binex import otel <file.json>` converts an OTLP/JSON trace into a Binex run, and `binex collect` runs a live collector endpoint that finalises a trace on its root span plus a quiet period; OpenInference (`llm.*`) attributes take precedence over OpenLLMetry (`gen_ai.*`). Imported runs are marked `source="otel-import"` and are read-only for replay/bisect — `ensure_replayable()` is the single gate enforcing that across CLI (exit 2), REST (422) and MCP. Also adds `ScriptedInputAdapter`, which answers `human://` nodes from preset values so a workflow with a human step can run non-interactively in an eval. (#121)
- **`binex bisect --semantic` and a dependency-order walk** — on prose the similarity ratio is not a weak signal, it is the wrong one: rewording scores ~0.44 and gets flagged, while inserting a "not" scores ~0.98 and passes. With `--semantic` a temperature-0 judge decides every text node whose output differs at all, using the same narrow rubric as `diff --semantic`; only *structure* and *facts* count as a divergence, `--threshold` stops deciding text nodes, and structured content never reaches the judge because the field-wise comparison already answers exactly and for free. The walk stops at the first meaningful divergence — later nodes are consequences, not causes — and a judge that cannot be reached falls back to the threshold rather than silently turning every node into a match. Cost is estimated and confirmed before any call, on stderr so `--json` stays parseable. Separately, nodes are now walked in **dependency order**, recovered from the artifact references in the execution records (no workflow file needed, so imported runs work too), with ties broken on node id: previously the walk followed store order, so on a fan-out which sibling was blamed as the root cause depended on which branch happened to finish first. (#133)

### Bug Fixes

- **SQLite WAL mode** — the store now opens the database with `PRAGMA journal_mode=WAL` (plus `busy_timeout=5000` and `synchronous=NORMAL`). The Web UI can read run data while the orchestrator is actively writing execution/cost records, instead of hitting `database is locked` during live runs. (#57)
- **Replay no longer reuses stale cached upstream silently** — `binex replay --from X` reuses every node before `X` verbatim, so if one of those definitions changed in the workflow file since the original run, the replay quietly mixed old outputs with a new workflow. `resume` already checked for this; replay did not. A drift gate now compares each cached node against the original run's workflow snapshot and refuses with `WorkflowDriftError`, naming the drifted nodes — CLI exits 2 with `--allow-drift` as the escape hatch, REST returns 409 `workflow_drift`, MCP returns `code="workflow_drift"`. Replay also stores its own snapshot, so a replay run is drift-checkable in turn. The comparison excludes input keys bound from `${user.*}`: a snapshot holds the substituted value while the file holds the template, and comparing them flagged every `--var` run as drifted — which was **also live in `resume`**, where it silently re-executed (and re-paid for) every node of any parameterised workflow. Also fixes a three-way drift in the built-in agent prefix list: `cao` was dispatched but never reserved, so a plugin could claim `cao://`, pass conflict validation, and then be silently shadowed. (#131)
- **Structured artifact content is compared by field, not as `str(dict)`** — `Artifact.content` is usually a mapping, but the comparison path stringified it and scored the result with `difflib`. A character ratio measures how many characters moved, which on structured data is anti-correlated with meaning because the changes that matter most are the smallest: reordered keys scored 0.636 and were flagged as the divergence, while `"approved"` → `"rejected"` scored 0.915 and passed as a match, and a changed number beside a long text field scored 0.999. No threshold separates those. Mappings and lists are now compared field by field — similarity is the fraction of unchanged leaf paths, so key order is irrelevant — and `diff`, `bisect` and the Web UI name the field that moved (`decision: 'approved' -> 'rejected'`) instead of printing a ratio. Text content keeps the character ratio; that is what `--semantic` is for. **Note for eval users:** `min_similarity` reads the same value, so thresholds tuned against the old numbers will shift — one changed field in a ten-field object now scores 0.9 instead of 0.9858. See `docs/eval.md` for the measured before/after table. (#132)
- **`last_n` in the export endpoint** — `GET /api/v1/export` accepted the parameter but ignored it, always exporting every run. (#114)
- **Pinned `mcp<2`** — `mcp` 2.0.0 removed `mcp.server.fastmcp`, which `binex mcp serve` imports; an unpinned install broke the MCP server on first use. (#129)

### Chore

- **E2E suite migrated to pytest** — the Playwright tests were standalone scripts; they are now a pytest suite with Page Object Model, failure artifacts (screenshot/video/trace), parallel execution and a CI job. Selectors live only in page objects, page objects expose actions and locators but never assertions, and finite sets (sidebar links, export formats) are enums rather than strings. (#113, #117, #126)
- **`tests/unit` split into per-layer packages** — one flat directory became `models/`, `stores/`, `adapters/`, `runtime/`, `graph/`, `cli/`, `gateway/`, `workflow_spec/`, `ui_api/`, `tools/`, `telemetry/`, `trace/`, `agents/`, `scheduler/`, `eval/`, `qa/`, mirroring `src/binex/`. (#115)
- **Web UI API coverage** — the tools, system, scheduler, gateway, CAO, MCP-wiring, SSE-events, export and replay routers gained tests; several were previously untested end to end. (#116, #118, #120, #122, #123, #125)
- **Coverage gate and nightly sweep** — a `coverage` workflow fails under 80% (measured 84%), `tests/` is linted alongside `src/`, and a nightly job runs the full suite on 3.11/3.12/3.13 plus the browser E2E, so dependency drift surfaces without waiting for a PR. (#127)
- **Frontend tests run in CI** — `ui/` had 175 vitest tests that were never executed by any workflow, and as a result a broken `reactflow` mock had been failing on `master` unnoticed. A `frontend` job now runs `npm ci`, `tsc --noEmit` and `vitest run` on Node 20; the mock was rebuilt as a partial mock (`importOriginal`) so it cannot rot the same way again. (#130, #103)

## v0.7.5

Amber redesign, pattern step editor, and repository polish.

### Features

- **Amber UI redesign** — full palette audit across editor, dashboard, and landing page. Amber primary token, sharp corners, JetBrains Mono typography, dark #0b0b0c base.
- **Pattern Step Editor** — per-step model, prompt, and `max_retries` overrides in the visual editor. Collapsible step rows with model inheritance display.
- **Per-step retry policy** — `max_retries` in YAML `steps:` block applies `RetryPolicy` with exponential backoff to individual pattern sub-nodes at runtime.
- **Built-in prompts** — 20 prompt templates for all 9 pattern types (`.md` files in prompt library + "Default" button in step editor).
- **Docs theme** — MkDocs documentation restyled to match landing page: amber accent, dark background, JetBrains Mono, no light mode.

### Bug Fixes

- **Dropdown clipping** — fixed `CollapsibleSection` `overflow-hidden` blocking ModelSelect dropdown in node editor.
- **Landing page links** — replaced all placeholder `href="#"` with real GitHub/docs URLs.
- **E2E navigation test** — updated sidebar collapse/active-link assertions for inline-style sidebar (no Tailwind classes).

### Chore

- Removed internal dev files from repo root: `SCAN_RESULTS.md`, `improvement_log.md`, `program.md`, `program_propose.md`, VHS tape scripts.

## v0.7.0

Pattern Nodes release — macro-node patterns that expand into full sub-DAG pipelines.

### Features

- **Pattern Nodes** — 9 built-in patterns: `critic`, `debate`, `best_of_n`, `reflexion`, `scatter`, `fsm`, `constitutional`, `chain_of_verification`, `plan_execute`. Each expands into a wired sub-DAG at runtime.
- **PatternExpander** — `expand_patterns()` resolves pattern nodes in a `WorkflowSpec` before execution. Handles nested pattern chains, back-edges (loops), and external `depends_on` wiring.
- **YAML integration** — patterns declared inline via `pattern:` field on any node; `config.steps` for per-step model/prompt overrides.
- **UI: Node Palette** — 9 pattern types in the DAG editor palette with icons and descriptions.
- **UI: Pattern Group** — collapsed sub-DAG view in the graph editor with expandable detail.
- **UI: Pattern Config** — per-step model, prompt, and config overrides in the sidebar.
- **Workflow cookbook** — example YAML workflows for all 9 patterns in `docs/`.

### Bug Fixes

- **Pattern expander** — fixed critical bug where cross-pattern `depends_on` was not rewired for expanded nodes (chained patterns produced stale pattern IDs).
- **`has_rich()`** — added `sys.stdout.isatty()` check to prevent Rich hanging in non-TTY environments (CI, CliRunner).
- **CI stability** — added `pytest-timeout` (30s per test) to prevent hanging tests from blocking CI indefinitely.

## v0.6.5

Security, Performance & Observability release.

### Security (CRITICAL)

- **shell_command** — patched command injection: replaced `shell=True` with `shell=False` + `shlex.split()`. Shell metacharacters no longer interpreted.
- **calculator** — patched arbitrary code execution: replaced raw `eval()` with AST whitelist validation. Only math expressions and whitelisted functions permitted.

### Features

- **binex-trace SDK** — lightweight A2A agent tracing via structured JSON on stderr. API: `trace.task()`, `trace.log()`, `trace.checkpoint()`. Zero runtime dependencies.
- **Trace events storage** — trace events persisted in SQLite alongside execution records
- **`binex trace subtasks`** — new CLI command to render subtask tree from captured stderr
- **`binex trace node --node`** — show trace events in node detail view

### Performance

- **Cost dashboard** — batch SELECT + SQL aggregation replacing N+1 queries
- **CAO sessions** — batch UPDATE for session status changes

### Documentation

- **Trace SDK guide** — `docs/features/trace-sdk.md`
- **Security model** — `docs/features/security.md`

## v0.6.4

Type Safety & Performance release.

### Features

- **Mypy strict type annotations** — full typing added to all modules (cli, ui, runtime, trace, agents, tools, models, stores)
- **Query pagination** — `limit` and `offset` parameters on `list_runs()` for large dataset handling
- **Scheduler documentation** — new `docs/cli/scheduler.md` with CLI commands, YAML config, and examples
- **Tools & MCP documentation** — new `docs/features/tools-mcp.md` covering built-in tools, MCP servers, and security

### Fixes

- **SQLite column order** — replaced `SELECT *` with explicit column list to fix migration-induced column order mismatch
- **Diff page inline display** — artifact diffs now render inline under the table row instead of at the bottom of the page
- **5 real type mismatches** caught and corrected by mypy strict checking
- **71 ruff lint errors** fixed (I001 import sorting, E501 line length, F401 unused imports)
- **Exception logging** — swallowed exceptions now logged in observability module
- **Budget checks** — made non-blocking for Web UI responsiveness
- **Artifact access safety** — guard against empty artifact lists in runtime dispatcher

### Performance

- **SQLite indexes** — added on `cao_sessions.status` and `run_id` for execution/cost records
- **Cost calculation** — new `get_node_cost()` to avoid loading all cost records during budget checks
- **Replay artifacts** — batch-fetch to eliminate N+1 queries
- **BFS scheduler** — `deque.popleft()` instead of `list.pop(0)` for O(1)
- **HTTP client** — reuse `httpx.AsyncClient` in A2A adapters and health checker

## v0.6.3

Logo & Landing redesign release.

### Features

- **Logo redesign** — "Binary Flow" mark from binary tree DAG paths, purple→cyan gradient, new favicon
- **Landing page redesign** — "Electric Minimalism with Cinematic Motion" — asymmetrical hero, staggered features grid, Syne + Inter fonts, entrance animations
- **Blog plugin** — mkdocs-blog integration with first post

### Fixes

- Human workflows — pre-create run record to prevent live page 404
- Blog post improvements — content clarity, CTA, og:image

## v0.6.2

Web UI Tools & Scheduler release.

### Features

- **Built-in Tools** — 10 built-in tools: calculator, dice_roll, fetch_url, http_request, web_search, read_file, write_file, shell_command, json_parse, random_choice
- **MCP Server Integration** — Model Context Protocol support via stdio and HTTP/SSE transports
- **Tools in Web UI Editor** — tool picker, MCP config panel, collapsible sections for LLM nodes
- **Scheduler Cron** — `schedule` field for cron expressions; `binex scheduler start/list/add/remove` CLI commands
- **Cost Dashboard** — `/costs` page with KPI cards, trend chart, cost breakdown, budget status

### Fixes

- Cost dashboard route and diff page combobox selectors
- Select component option handling in E2E tests

## v0.6.1

PyPI compatibility release.

### Fixes

- README images converted to absolute GitHub URLs for PyPI display

## v0.6.0

Web UI Enhancement release.

### Features

- **Scaffold redesign** — template cards with categories, MiniGraph SVG preview, node count badges; 4→5 categories (new: Agentic Patterns)
- **3 new agentic patterns** — reflection, plan-execute-verify, dry-run-harness (20 scaffold templates total)
- **8 workflow prompts** — planner, analyzer, executor, task decomposer, and more for DAG-native roles (119 prompts total)
- **Prompt Library** — new Build page with search, category tabs, markdown preview, "Use in Editor" integration; custom prompt creation with built-in deletion protection
- **Model Selector v2** — provider-aware selection via `GET /api/v1/providers`, searchable Command popover, tier badges, configured vs unconfigured providers, recently used models
- **`binex list`** — discover available workflows in current directory and examples (`--json` supported)
- **`binex start` consolidation** — `binex init` now alias for `binex start`; added `--quick` flag for non-interactive setup
- **README refresh** — inline screenshots, 3-panel GIF demo, quickstart callouts
- **Landing page** — project website with feature overview

### Fixes

- Editor visual mode sync — YAML↔canvas changes now propagate correctly
- HelpPanel z-index overlap with editor sidebar resolved
- Scaffold prompt inlining — generated YAML now includes system_prompt content instead of placeholder text

### Notes

- `__version__` synced with pyproject.toml (was 0.4.0, now 0.6.0)
- New API endpoint: `GET /api/v1/providers` for model selector
- Scaffold API now includes `category`, `description`, `use_case`, `node_count` fields

## v0.4.0

Observability & Persistence release.

### Features

- **OpenTelemetry integration** — optional run-level and node-level tracing spans (`binex.run`, `binex.node.<id>`), zero overhead when disabled (no-op fallback)
- **Workflow schema versioning** — `version` field on workflows (default 1), migration framework for future schema changes
- **Workflow snapshots** — every `binex run` stores an immutable SHA256-deduplicated snapshot of the workflow definition in SQLite
- **`binex workflow version <file>`** — display the schema version of a workflow file
- **`binex workflow diff <run1> <run2>`** — compare workflow definitions used in two different runs (unified diff)
- **CSV/JSON export** — `binex export <run-id>` for run data export (`--format json`, `--last N`, `--include-artifacts`)
- **Webhook notifications** — run lifecycle events (completed, failed, budget exceeded) sent to configured webhook URLs

### Installation

```bash
pip install binex[telemetry]   # OpenTelemetry tracing (optional)
```

### Notes

- Existing workflows without a `version` field default to version 1 (backward compatible)
- `workflow_snapshots` SQLite table and `workflow_hash` column added via lazy migration
- OTEL tracing activates only when `opentelemetry` is installed AND `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_TRACES_EXPORTER` is set

## v0.3.0

Framework Adapters release.

### Features

- A2A Gateway — standalone proxy with routing, auth, fallback, health checking
- LangChain adapter — run LangChain chains as workflow nodes
- CrewAI adapter — integrate CrewAI crews via A2A protocol
- AutoGen adapter — bridge AutoGen agents into Binex pipelines
- Plugin system for custom adapters via entry points

## v0.2.0

Developer Experience release.

### Features

- `binex diagnose <run-id>` — automated root-cause analysis for failed runs
- `binex bisect <run-id>` — binary search for regression-introducing node
- Streaming output for long-running LLM nodes
- Improved `binex diff` with side-by-side artifact comparison
- Node output schema validation (`output_schema` in YAML)

## v0.1.0

First public release.

### Features

- DAG-based workflow runtime with topological scheduling
- Artifact lineage tracking across pipeline steps
- Replayable workflows with agent swap support
- Run diffing for side-by-side comparison
- CLI interface: run, debug, trace, replay, diff, artifacts, explore, scaffold, validate, doctor
- Agent adapters: LLM (via LiteLLM), local Python, A2A protocol, human-in-the-loop
- Human approval gates with conditional branching
- 9 LLM providers out of the box (OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Groq, Mistral, DeepSeek, Together)
- Rich colored output (optional)
- SQLite execution store + filesystem artifact store
- Interactive project initialization wizard
- DSL shorthand for workflow generation
- MkDocs documentation site
