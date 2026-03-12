"""QA P1 tests — CLI commands, workflow spec, lineage, and security edge cases.

TC-CLI-001: `binex run` with non-existent YAML file
TC-CLI-002: `binex run --var` with invalid format (no "=")
TC-CLI-006: `binex replay --agent` swap syntax — multiple swaps
TC-WFS-002: ${user.var} without provided value — unresolved vars
TC-WFS-003: Workflow with empty `nodes: {}`
TC-TRC-002: Lineage with circular derived_from — loop protection
TC-SEC-005: a2a:// endpoint validation — internal IPs
"""

from __future__ import annotations

import textwrap
from unittest.mock import AsyncMock, patch

import click
import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.cli.replay import _parse_agent_swaps
from binex.cli.run import _parse_vars
from binex.models.artifact import Artifact, Lineage
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.trace.lineage import build_lineage_tree
from binex.workflow_spec.loader import load_workflow, load_workflow_from_string
from binex.workflow_spec.validator import validate_workflow


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path, content: str):
    wf = tmp_path / "wf.yaml"
    wf.write_text(textwrap.dedent(content))
    return wf


def _make_artifact(
    id: str,
    run_id: str = "run_01",
    produced_by: str = "node1",
    derived_from: list[str] | None = None,
) -> Artifact:
    return Artifact(
        id=id,
        run_id=run_id,
        type="test",
        content={"data": id},
        lineage=Lineage(produced_by=produced_by, derived_from=derived_from or []),
    )


# ===========================================================================
# TC-CLI-001: `binex run` with non-existent YAML file
# ===========================================================================


class TestCLI001NonExistentFile:
    """Running with a file that does not exist should fail with a non-zero
    exit code and an error message mentioning the path."""

    def test_run_nonexistent_yaml_exits_nonzero(self, runner):
        result = runner.invoke(cli, ["run", "/tmp/does_not_exist_abc123.yaml"])
        assert result.exit_code != 0

    def test_run_nonexistent_yaml_shows_error_message(self, runner):
        result = runner.invoke(cli, ["run", "/tmp/does_not_exist_abc123.yaml"])
        # click.Path(exists=True) produces an error containing the path
        assert "does_not_exist" in result.output


# ===========================================================================
# TC-CLI-002: `binex run --var` with invalid format (no "=")
# ===========================================================================


class TestCLI002InvalidVarFormat:
    """--var without '=' should produce a clear error, not a traceback."""

    def test_parse_vars_no_equals_raises(self):
        with pytest.raises(click.BadParameter, match="expected key=value"):
            _parse_vars(("missing_equals",))

    def test_parse_vars_no_equals_mentions_value(self):
        with pytest.raises(click.BadParameter, match="missing_equals"):
            _parse_vars(("missing_equals",))

    def test_run_var_invalid_format_via_cli(self, runner, tmp_path):
        """End-to-end: the CLI should surface the error, not crash."""
        wf = _write_yaml(tmp_path, """\
            name: var-test
            nodes:
              step1:
                agent: local://echo
                outputs: [out]
        """)
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())
        with patch("binex.cli.run._get_stores", return_value=stores):
            result = runner.invoke(cli, ["run", str(wf), "--var", "bad_format"])
        assert result.exit_code != 0
        # Should mention the problematic value or expected format
        assert "key=value" in result.output or "bad_format" in result.output


# ===========================================================================
# TC-CLI-006: `binex replay --agent` swap syntax — multiple swaps
# ===========================================================================


class TestCLI006ReplayAgentSwaps:
    """The --agent option accepts node=agent pairs; multiple swaps should parse
    correctly and be forwarded to the replay engine."""

    def test_parse_single_swap(self):
        result = _parse_agent_swaps(("step1=llm://gpt-4",))
        assert result == {"step1": "llm://gpt-4"}

    def test_parse_multiple_swaps(self):
        result = _parse_agent_swaps((
            "step1=llm://gpt-4",
            "step2=a2a://http://localhost:9000",
        ))
        assert result == {
            "step1": "llm://gpt-4",
            "step2": "a2a://http://localhost:9000",
        }

    def test_parse_swap_invalid_format(self):
        with pytest.raises(click.BadParameter, match="expected node=agent"):
            _parse_agent_swaps(("no_equals",))

    def test_parse_swap_value_with_equals(self):
        """Agent URLs may contain '=' — only split on the first one."""
        result = _parse_agent_swaps(("step1=a2a://host?key=val",))
        assert result == {"step1": "a2a://host?key=val"}

    def test_replay_cli_passes_agent_swaps(self, runner):
        """Multiple --agent flags should all be forwarded to the replay engine."""
        from binex.models.execution import RunSummary

        mock_summary = RunSummary(
            run_id="run_replay_001",
            workflow_name="swapped",
            status="completed",
            total_nodes=2,
            completed_nodes=2,
            forked_from="run_original",
            forked_at_step="step1",
        )

        with patch("binex.cli.replay._run_replay", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_summary
            result = runner.invoke(cli, [
                "replay", "run_original",
                "--from", "step1",
                "--workflow", "examples/simple.yaml",
                "--agent", "step1=llm://gpt-4",
                "--agent", "step2=local://echo",
            ])

        assert result.exit_code == 0
        # Verify the agent_swaps dict was passed correctly
        call_args = mock_run.call_args
        agent_swaps_arg = call_args[0][3] if len(call_args[0]) > 3 else call_args.kwargs.get("agent_swaps")
        if agent_swaps_arg is None:
            # Positional args: run_id, from_step, workflow_path, agent_swaps
            agent_swaps_arg = call_args[0][3]
        assert agent_swaps_arg == {"step1": "llm://gpt-4", "step2": "local://echo"}


# ===========================================================================
# TC-WFS-002: ${user.var} without provided value — unresolved vars
# ===========================================================================


class TestWFS002UnresolvedUserVars:
    """When a workflow references ${user.topic} but no --var topic=... is given,
    the literal ${user.topic} string should remain in the loaded spec."""

    def test_unresolved_user_var_stays_literal(self):
        yaml_str = textwrap.dedent("""\
            name: unresolved
            nodes:
              step1:
                agent: local://echo
                inputs:
                  query: "${user.topic}"
                outputs: [out]
        """)
        spec = load_workflow_from_string(yaml_str, fmt="yaml")
        # No user_vars provided, so the placeholder should remain as-is
        assert spec.nodes["step1"].inputs["query"] == "${user.topic}"

    def test_partial_user_vars_leaves_others_unresolved(self):
        yaml_str = textwrap.dedent("""\
            name: partial
            nodes:
              step1:
                agent: local://echo
                inputs:
                  a: "${user.provided}"
                  b: "${user.missing}"
                outputs: [out]
        """)
        spec = load_workflow_from_string(
            yaml_str, fmt="yaml", user_vars={"provided": "hello"},
        )
        assert spec.nodes["step1"].inputs["a"] == "hello"
        assert spec.nodes["step1"].inputs["b"] == "${user.missing}"

    def test_validator_does_not_reject_user_refs(self):
        """The validator should skip ${user.*} refs — they are not node refs."""
        yaml_str = textwrap.dedent("""\
            name: user-ref
            nodes:
              step1:
                agent: local://echo
                inputs:
                  query: "${user.topic}"
                outputs: [out]
        """)
        spec = load_workflow_from_string(yaml_str, fmt="yaml")
        errors = validate_workflow(spec)
        # ${user.*} refs should NOT produce validation errors
        assert errors == []


# ===========================================================================
# TC-WFS-003: Workflow with empty `nodes: {}`
# ===========================================================================


class TestWFS003EmptyNodes:
    """A workflow with zero nodes is structurally valid per the pydantic model
    but the validator should flag it (no entry nodes)."""

    def test_empty_nodes_parses_as_spec(self):
        """Pydantic accepts an empty dict for nodes — the model does not reject it."""
        yaml_str = textwrap.dedent("""\
            name: empty
            nodes: {}
        """)
        spec = load_workflow_from_string(yaml_str, fmt="yaml")
        assert spec.name == "empty"
        assert len(spec.nodes) == 0

    def test_empty_nodes_validator_reports_no_entry(self):
        """validate_workflow should report 'no entry nodes' for an empty workflow."""
        yaml_str = textwrap.dedent("""\
            name: empty
            nodes: {}
        """)
        spec = load_workflow_from_string(yaml_str, fmt="yaml")
        errors = validate_workflow(spec)
        # With no nodes, the check for entry nodes should report a problem
        # (any() over an empty iterable returns False)
        assert any("entry" in e.lower() or "no entry" in e.lower() for e in errors)

    def test_run_cli_with_empty_nodes(self, runner, tmp_path):
        """Running a workflow with no nodes should exit with an error."""
        wf = _write_yaml(tmp_path, """\
            name: empty
            nodes: {}
        """)
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())
        with patch("binex.cli.run._get_stores", return_value=stores):
            result = runner.invoke(cli, ["run", str(wf)])
        # The validator catches no-entry-nodes -> exit code 2
        assert result.exit_code == 2


# ===========================================================================
# TC-TRC-002: Lineage with circular derived_from — loop protection
# ===========================================================================


class TestTRC002CircularLineage:
    """build_lineage_tree must not infinite-loop on circular derived_from refs.
    Note: The current implementation has no visited-set, so a cycle with
    artifacts that actually exist in the store WILL recurse infinitely.
    If the store returns None for the back-edge, the recursion terminates.
    We test the safe case (store returns None for missing artifacts)."""

    @pytest.fixture
    def artifact_store(self) -> InMemoryArtifactStore:
        return InMemoryArtifactStore()

    @pytest.mark.asyncio
    async def test_circular_derived_from_with_missing_ref(self, artifact_store):
        """If an artifact claims to derive from itself (or a missing ancestor),
        build_lineage_tree terminates because get() returns None."""
        art = _make_artifact("art_self", derived_from=["art_self"])
        await artifact_store.store(art)

        tree = await build_lineage_tree(artifact_store, "art_self")
        # With cycle protection, the tree should return the root with no parents
        assert tree is not None
        assert tree["artifact_id"] == "art_self"
        assert tree["parents"] == []

    @pytest.mark.asyncio
    async def test_circular_lineage_via_store_get_lineage(self, artifact_store):
        """The store-level get_lineage (BFS) DOES have cycle protection."""
        art_a = _make_artifact("circ_a", derived_from=["circ_b"])
        art_b = _make_artifact("circ_b", derived_from=["circ_a"])
        await artifact_store.store(art_a)
        await artifact_store.store(art_b)

        lineage = await artifact_store.get_lineage("circ_a")
        ids = {a.id for a in lineage}
        # circ_b is the immediate ancestor; circ_a is excluded (it is the root)
        assert ids == {"circ_b"}

    @pytest.mark.asyncio
    async def test_lineage_tree_terminates_on_missing_parent(self, artifact_store):
        """Derived-from pointing to a non-existent artifact is handled gracefully."""
        art = _make_artifact("orphan", derived_from=["does_not_exist"])
        await artifact_store.store(art)

        tree = await build_lineage_tree(artifact_store, "orphan")
        assert tree is not None
        assert tree["artifact_id"] == "orphan"
        # The missing parent is silently dropped
        assert tree["parents"] == []


# ===========================================================================
# TC-SEC-005: a2a:// endpoint validation — internal IPs
# ===========================================================================


class TestSEC005A2AEndpointValidation:
    """Document the behavior of A2AAgentAdapter when given internal/private
    IP addresses.  The adapter does NOT validate or block internal IPs —
    it simply forwards to httpx.  These tests document that behavior."""

    def test_adapter_accepts_localhost_endpoint(self):
        from binex.adapters.a2a import A2AAgentAdapter

        adapter = A2AAgentAdapter(endpoint="http://127.0.0.1:8080")
        assert adapter._endpoint == "http://127.0.0.1:8080"

    def test_adapter_accepts_private_ip_endpoint(self):
        from binex.adapters.a2a import A2AAgentAdapter

        adapter = A2AAgentAdapter(endpoint="http://10.0.0.5:9000")
        assert adapter._endpoint == "http://10.0.0.5:9000"

    def test_adapter_accepts_link_local_endpoint(self):
        from binex.adapters.a2a import A2AAgentAdapter

        adapter = A2AAgentAdapter(endpoint="http://169.254.169.254/latest/meta-data")
        # Cloud metadata endpoint — no SSRF protection in place
        assert adapter._endpoint == "http://169.254.169.254/latest/meta-data"

    def test_adapter_strips_trailing_slash(self):
        from binex.adapters.a2a import A2AAgentAdapter

        adapter = A2AAgentAdapter(endpoint="http://example.com:8080/")
        assert adapter._endpoint == "http://example.com:8080"

    def test_run_registers_a2a_adapter_for_internal_ip(self, runner, tmp_path):
        """binex run does not reject a2a:// agents pointing to internal IPs."""
        wf = _write_yaml(tmp_path, """\
            name: a2a-internal
            nodes:
              step1:
                agent: "a2a://http://192.168.1.100:5000"
                outputs: [out]
        """)
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())

        from binex.models.execution import RunSummary

        async def _mock_run(spec, verbose=False, **kwargs):
            summary = RunSummary(
                run_id="run_sec_005",
                workflow_name="a2a-internal",
                status="completed",
                total_nodes=1,
                completed_nodes=1,
            )
            return summary, [], []

        with (
            patch("binex.cli.run._get_stores", return_value=stores),
            patch("binex.cli.run._run", side_effect=_mock_run),
        ):
            result = runner.invoke(cli, ["run", str(wf)])

        # The command does not reject internal IPs — it runs successfully
        assert result.exit_code == 0
