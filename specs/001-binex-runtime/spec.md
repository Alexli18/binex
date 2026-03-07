# Feature Specification: Binex Runtime

**Feature Branch**: `001-binex-runtime`
**Created**: 2026-03-07
**Status**: Draft
**Input**: User description: "Binex — debuggable runtime for A2A agents"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Multi-Agent Workflow (Priority: P1)

A developer defines a research pipeline as a YAML workflow (e.g., planner -> researchers -> validator -> summarizer), then runs it via CLI. Binex parses the DAG, schedules tasks respecting dependencies, dispatches each task to the appropriate agent via adapters, collects typed artifacts, and returns the final result.

**Why this priority**: Without DAG execution, nothing else works. This is the core value proposition — orchestrating multi-agent pipelines with typed artifact flow.

**Independent Test**: Can be fully tested by running `binex run workflow.yaml` with a simple 2-agent workflow using local Python adapters, verifying that artifacts flow between nodes and the final output is produced.

**Acceptance Scenarios**:

1. **Given** a valid YAML workflow with 5 nodes (planner, 2 researchers, validator, summarizer), **When** the user runs `binex run workflow.yaml`, **Then** nodes execute in dependency order, parallel nodes run concurrently, and the final summary artifact is returned.
2. **Given** a workflow where node "researcher_1" fails, **When** the retry policy allows 2 retries, **Then** the node is re-executed up to 2 times before being marked as terminal failure.
3. **Given** a workflow with a node exceeding its deadline, **When** the deadline is reached, **Then** the node is cancelled, marked as timed_out, and downstream nodes are blocked.

---

### User Story 2 - Trace and Inspect a Pipeline Run (Priority: P1)

After a pipeline run completes (or fails), a developer inspects the execution trace to understand what happened at each step: which agent ran, what artifacts were produced, how long each step took, and the full artifact lineage chain.

**Why this priority**: Debuggability is a core differentiator. Without trace and lineage, Binex is just another orchestrator.

**Independent Test**: Can be tested by running a pipeline, then using `binex trace <run_id>` to view the timeline, `binex trace graph <run_id>` to see the DAG visualization, and `binex artifacts lineage <artifact_id>` to trace provenance.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the user runs `binex trace <run_id>`, **Then** a human-readable timeline is displayed showing each step with agent, status, latency, and artifact references.
2. **Given** a completed run with 5 artifacts, **When** the user runs `binex artifacts lineage <artifact_id>` on the final artifact, **Then** the full provenance chain is displayed showing derived_from and produced_by relationships back to the original input.
3. **Given** a failed run, **When** the user runs `binex trace <run_id>`, **Then** the failed step is clearly indicated with error details and the blocking state of downstream nodes.

---

### User Story 3 - Replay a Pipeline from a Specific Step (Priority: P2)

A developer wants to re-run part of a pipeline — either because a step failed and they want to retry from that point, or because they want to swap an agent and compare results. Replay creates a new run that reuses cached artifacts from earlier steps.

**Why this priority**: Replay enables iterative development and A/B testing of agents without re-running expensive upstream steps. High value but depends on trace and execution store from P1 stories.

**Independent Test**: Can be tested by running a pipeline, then using `binex replay <run_id> --from <step>` to re-execute from a specific node, verifying that upstream artifacts are reused and downstream steps re-execute.

**Acceptance Scenarios**:

1. **Given** a completed run_42 with 5 steps, **When** the user runs `binex replay run_42 --from validator`, **Then** a new run_43 is created where planner and researcher steps reuse cached artifacts and validator + summarizer are re-executed.
2. **Given** a completed run_42, **When** the user runs `binex replay run_42 --agent validator=strict_validator`, **Then** a new run is created with the validator node bound to the strict_validator agent, and all downstream nodes re-execute with new inputs.
3. **Given** two runs (original and replayed), **When** the user runs `binex diff run_42 run_43`, **Then** a step-by-step comparison is displayed showing artifact differences and execution metadata differences.

---

### User Story 4 - Register and Discover Agents (Priority: P2)

A developer registers agents in the local registry (either by providing endpoints or by configuring seed URLs for crawling). The registry tracks agent capabilities, health status, and provides capability-based search.

**Why this priority**: Agent discovery is needed for production use but for MVP, agents can be specified directly in workflow YAML. Registry adds discoverability and health awareness.

**Independent Test**: Can be tested by starting the registry service, registering an agent endpoint, verifying the agent card is crawled and indexed, then searching by capability.

**Acceptance Scenarios**:

1. **Given** an A2A-compatible agent running at a URL, **When** the user registers the agent endpoint in the registry, **Then** the registry crawls the agent card, indexes capabilities, and the agent appears in search results.
2. **Given** a registered agent becomes unresponsive, **When** the registry performs periodic health checks, **Then** the agent's health status transitions from "alive" to "degraded" to "down" based on consecutive failures.
3. **Given** multiple agents with overlapping capabilities, **When** the user searches for a capability, **Then** agents are ranked by health, latency, and capability match.

---

### User Story 5 - Local Development Environment (Priority: P2)

A developer sets up a complete local development stack with Docker Compose, including Ollama for local LLM inference, reference agents, and the registry. The `binex dev` command bootstraps everything needed to run and debug pipelines locally.

**Why this priority**: Lowers the barrier to entry. Developers need a zero-config local setup to start experimenting.

**Independent Test**: Can be tested by running `binex dev` and verifying that all services start, reference agents are reachable, and the research pipeline example runs successfully.

**Acceptance Scenarios**:

1. **Given** Docker is installed, **When** the user runs `binex dev`, **Then** all services (LLM inference, 4 reference agents, registry) start and are accessible.
2. **Given** the local stack is running, **When** the user runs the research pipeline example, **Then** the pipeline completes successfully using local models.
3. **Given** the local stack is running, **When** the user runs `binex doctor`, **Then** all components report healthy status.

---

### User Story 6 - Validate and Scaffold Workflows (Priority: P3)

A developer validates a workflow YAML file before running it, catching structural errors (missing dependencies, cycles, unknown agents) early. They can also scaffold a new agent from a template.

**Why this priority**: Developer experience improvement. Validation prevents runtime errors, scaffolding accelerates agent creation.

**Independent Test**: Can be tested by running `binex validate workflow.yaml` on both valid and invalid workflow files, verifying appropriate success/error messages.

**Acceptance Scenarios**:

1. **Given** a workflow YAML with a cycle in the dependency graph, **When** the user runs `binex validate workflow.yaml`, **Then** a clear error message identifies the cycle.
2. **Given** a valid workflow YAML, **When** the user runs `binex validate workflow.yaml`, **Then** success is reported with a summary of nodes, edges, and required agents.
3. **Given** the user wants to create a new agent, **When** they run `binex scaffold agent`, **Then** a template agent project is generated with the necessary boilerplate.

---

### Edge Cases

- What happens when a workflow has a single node with no dependencies? It executes immediately without scheduling overhead.
- How does the system handle an agent returning an artifact of unexpected type? The artifact is stored with a warning; the downstream node receives it as-is (no runtime type enforcement in MVP).
- What happens when replay is requested for a run that references a no-longer-available agent? The replay fails with a clear error identifying the unavailable agent.
- How does the system handle concurrent runs of the same workflow? Each run gets a unique run_id and operates on independent artifact/execution records — no cross-run interference.
- What happens when the execution store backend is unavailable? The run fails at startup with a clear error before dispatching any tasks.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST parse YAML/JSON workflow definitions into executable DAGs with nodes, edges, and per-node configuration (agent, inputs, outputs, depends_on, retry_policy, deadline).
- **FR-002**: System MUST execute DAG nodes respecting dependency order, running independent nodes in parallel.
- **FR-003**: System MUST manage task lifecycle state transitions: requested -> accepted -> running -> completed/failed/cancelled/timed_out.
- **FR-004**: System MUST support configurable retry policies per node (max_retries, backoff strategy) and per-node deadlines.
- **FR-005**: System MUST produce typed artifacts at each node with lineage metadata (produced_by, derived_from).
- **FR-006**: System MUST persist all artifacts in an Artifact Store with operations: store, get, list_by_run, get_lineage.
- **FR-007**: System MUST persist all execution records in an Execution Store with operations: record, get_run, get_step, list_runs.
- **FR-008**: System MUST support three agent adapter types: A2A-compatible remote agents, local in-process agents, and direct LLM call agents.
- **FR-009**: System MUST generate human-readable execution traces showing timeline, per-step details, and DAG visualization.
- **FR-010**: System MUST support replay from any step in a completed or failed run, creating a new immutable run that reuses cached upstream artifacts.
- **FR-011**: System MUST support agent swap during replay, binding different agents to specific nodes.
- **FR-012**: System MUST support diffing two runs at both artifact and execution metadata levels.
- **FR-013**: System MUST support artifact lineage traversal, showing the full provenance chain for any artifact.
- **FR-014**: System MUST provide a local agent registry that crawls agent capability cards, indexes capabilities, and tracks agent health (alive/slow/degraded/down).
- **FR-015**: System MUST provide a CLI with commands: run, dev, trace, trace graph, trace node, replay, diff, artifacts (list/show/lineage), doctor, validate, scaffold.
- **FR-016**: System MUST validate workflow definitions for structural correctness (cycles, missing references, invalid configuration) before execution.
- **FR-017**: System MUST provide a containerized setup for local development including LLM inference, reference agents, and registry.
- **FR-018**: System MUST include 4 reference agents (planner, researcher, validator, summarizer) demonstrating a research pipeline.
- **FR-019**: System MUST isolate protocol-specific SDK usage to adapters — core orchestration must not depend on protocol SDK internals.

### Key Entities

- **Workflow**: A DAG definition specifying nodes, their agents, inputs/outputs, dependencies, retry policies, and deadlines. Loaded from YAML/JSON files.
- **TaskNode**: A single unit of work in the DAG, bound to an agent, with defined inputs and outputs. Has a lifecycle state machine (requested -> accepted -> running -> completed/failed/cancelled/timed_out).
- **Artifact**: A typed output produced by a task node. Carries lineage metadata (produced_by, derived_from) enabling full provenance tracking.
- **ExecutionRecord**: Metadata about a single node execution: run, task, agent, status, input/output artifact references, prompt, model, latency, timestamp, error.
- **Run**: A complete execution of a workflow, identified by a unique ID. Immutable once completed. Replays create new runs.
- **AgentInfo**: Registry entry for a discovered agent: endpoint, capabilities, health status, latency metrics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A 5-node research pipeline (planner, 2 researchers, validator, summarizer) completes successfully end-to-end using local agents.
- **SC-002**: Parallel nodes in a DAG execute concurrently, reducing total pipeline time compared to sequential execution by at least 30% on a pipeline with 2+ parallel branches.
- **SC-003**: Replay from a mid-pipeline step reuses all upstream cached artifacts and produces a complete new run in under 50% of the original full-run time.
- **SC-004**: Developers can set up the full local environment and run the example pipeline within 10 minutes from a clean install.
- **SC-005**: Artifact lineage queries traverse the full provenance chain for any artifact in under 2 seconds for pipelines with up to 20 nodes.
- **SC-006**: The diff command clearly identifies which steps produced different artifacts and execution metadata between two runs.
- **SC-007**: Workflow validation catches 100% of structural errors (cycles, missing dependencies, invalid references) before execution.
- **SC-008**: Failed nodes with retry policies are automatically retried according to configuration without manual intervention.

## Assumptions

- Developers have Docker installed for local development setup.
- A2A SDK provides stable bindings for agent communication.
- Python 3.11+ is the target runtime environment.
- Local file-based storage is sufficient as the default store backend for single-user/local usage.
- The A2A Gateway (routing, proxy, auth) is explicitly out of scope for MVP (Phase 2).
- Human-in-the-loop approval gates are out of scope for MVP (Phase 2).
- Deterministic execution mode is out of scope for MVP (Phase 2).
- Trace viewer UI is out of scope for MVP (Phase 2).
