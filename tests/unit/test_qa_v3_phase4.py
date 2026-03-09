"""QA v3 Phase 4: Security & Integration — Regression, OWASP, E2E.

Covers CAT-12 (TC-SEC-*), CAT-13 (TC-E2E-*).
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.tools import ToolDefinition, execute_tool_call, load_python_tool, resolve_tools
from binex.trace.lineage import build_lineage_tree

SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "binex"


def _make_artifact(run_id, node_id, content, art_type="result"):
    return Artifact(
        id=f"{run_id}_{node_id}_out", run_id=run_id,
        type=art_type, content=content,
        lineage=Lineage(produced_by=node_id),
    )


class FakeAdapter:
    def __init__(self, content="done"):
        self._content = content

    async def execute(self, task, inputs, trace_id):
        return [_make_artifact(task.run_id, task.node_id, self._content)]

    async def cancel(self, task_id): pass
    async def health(self): return AgentHealth.ALIVE


def _make_spec(nodes_dict):
    nodes = {}
    for nid, ndata in nodes_dict.items():
        nodes[nid] = NodeSpec(
            agent=ndata.get("agent", "llm://test"),
            outputs=ndata.get("outputs", ["result"]),
            depends_on=ndata.get("depends_on", []),
            when=ndata.get("when"),
            inputs=ndata.get("inputs", {}),
        )
    return WorkflowSpec(name="test", nodes=nodes)


# ===========================================================================
# CAT-12: Security & Regression (TC-SEC-001 .. TC-SEC-010)
# ===========================================================================


class TestSecurityRegression:
    """Security tests and regression checks."""

    # TC-SEC-001: Tool python:// URI — no arbitrary code via URI itself
    def test_sec_001_tool_uri_no_arbitrary_exec(self):
        """python:// URI requires module.function format — can't run arbitrary code."""
        with pytest.raises(ValueError, match="must start with"):
            load_python_tool("exec://import os; os.system('rm -rf /')")
        with pytest.raises(ValueError, match="must be python://"):
            load_python_tool("python://os")  # no function part

    # TC-SEC-002: Tool execution — exceptions contained
    @pytest.mark.asyncio
    async def test_sec_002_tool_exceptions_contained(self):
        def dangerous():
            raise RuntimeError("crash!")

        td = ToolDefinition(
            name="bad", description="", parameters={},
            callable=dangerous, is_async=False,
        )
        result = await execute_tool_call(td, {})
        assert "Error" in result
        assert "crash!" in result

    # TC-SEC-003: Path traversal regression (BUG-001)
    def test_sec_003_path_traversal_regression(self):
        from binex.stores.backends.filesystem import FilesystemArtifactStore
        store = FilesystemArtifactStore("/tmp/test_binex_qa")
        # _sanitize_component should reject ..
        with pytest.raises(ValueError, match="Invalid"):
            store._sanitize_component("../etc/passwd")
        with pytest.raises(ValueError, match="Invalid"):
            store._sanitize_component("foo/bar")
        with pytest.raises(ValueError, match="Invalid"):
            store._sanitize_component("foo\\bar")

    # TC-SEC-004: Lineage recursion regression (BUG-002)
    @pytest.mark.asyncio
    async def test_sec_004_lineage_recursion_regression(self):
        """Circular derived_from should not cause infinite recursion."""
        art_a = Artifact(
            id="a", run_id="r", type="t", content="x",
            lineage=Lineage(produced_by="n1", derived_from=["b"]),
        )
        art_b = Artifact(
            id="b", run_id="r", type="t", content="y",
            lineage=Lineage(produced_by="n2", derived_from=["a"]),
        )
        store = InMemoryArtifactStore()
        await store.store(art_a)
        await store.store(art_b)
        # Should not hang or crash
        tree = await build_lineage_tree(store, "a")
        assert tree is not None

    # TC-SEC-005: yaml.safe_load used everywhere (never yaml.load)
    def test_sec_005_yaml_safe_load_only(self):
        """Scan all Python files for yaml.load (without safe_load)."""
        py_files = list(SRC_DIR.rglob("*.py"))
        assert len(py_files) > 0

        unsafe_files = []
        for f in py_files:
            content = f.read_text()
            # Find yaml.load calls that are NOT yaml.safe_load
            if "yaml.load(" in content and "yaml.safe_load(" not in content:
                # Could be a false positive, check more carefully
                for line_no, line in enumerate(content.split("\n"), 1):
                    if "yaml.load(" in line and "safe_load" not in line:
                        unsafe_files.append(f"{f.name}:{line_no}")

        assert not unsafe_files, f"Unsafe yaml.load found in: {unsafe_files}"

    # TC-SEC-006: SQL parameterized queries
    def test_sec_006_sql_parameterized(self):
        """Scan sqlite store for string formatting in SQL queries."""
        sqlite_file = SRC_DIR / "stores" / "backends" / "sqlite.py"
        if not sqlite_file.exists():
            pytest.skip("sqlite backend not found")
        content = sqlite_file.read_text()
        # Check for f-string SQL — patterns like f"SELECT ... {var}"
        # or .format() on SQL strings
        lines = content.split("\n")
        suspicious = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # f-string with SQL keywords
            if 'f"' in stripped or "f'" in stripped:
                sql_kw = ["SELECT", "INSERT", "UPDATE", "DELETE", "DROP"]
                if any(kw in stripped.upper() for kw in sql_kw):
                    suspicious.append(f"Line {i}: {stripped[:80]}")
        assert not suspicious, "Potential SQL injection:\n" + "\n".join(suspicious)

    # TC-SEC-007: Tool schema — no code eval
    def test_sec_007_no_eval_in_tools(self):
        """tools.py should not use eval() or exec()."""
        tools_file = SRC_DIR / "tools.py"
        content = tools_file.read_text()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in ("eval", "exec"), (
                        f"tools.py uses {node.func.id}() — security risk"
                    )

    # TC-SEC-008: Human adapter — no command injection via input
    def test_sec_008_human_no_cmd_injection(self):
        """Human adapters use click.prompt (not os.system, subprocess)."""
        human_file = SRC_DIR / "adapters" / "human.py"
        content = human_file.read_text()
        assert "os.system" not in content
        assert "subprocess" not in content
        assert "eval(" not in content

    # TC-SEC-009: when condition — no eval/exec
    def test_sec_009_when_no_eval(self):
        """Orchestrator evaluate_when uses regex, not eval."""
        orch_file = SRC_DIR / "runtime" / "orchestrator.py"
        content = orch_file.read_text()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in ("eval", "exec"), (
                        f"orchestrator.py uses {node.func.id}() in when eval — security risk"
                    )

    # TC-SEC-010: Start wizard writes in project dir only
    def test_sec_010_start_writes_project_dir(self):
        """start.py file writes should use Path, not absolute hardcoded paths."""
        start_file = SRC_DIR / "cli" / "start.py"
        content = start_file.read_text()
        # Should not write to /etc, /tmp, system dirs
        assert "/etc/" not in content
        assert "/usr/" not in content


# ===========================================================================
# CAT-13: Integration & E2E (TC-E2E-001 .. TC-E2E-010)
# ===========================================================================


class TestIntegrationE2E:
    """End-to-end integration tests."""

    # TC-E2E-001: Hello full lifecycle
    def test_e2e_001_hello_lifecycle(self):
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        stores = (exec_store, art_store)
        from binex.cli.hello import hello_cmd
        with patch("binex.cli.hello._get_stores", return_value=stores):
            result = CliRunner().invoke(hello_cmd, [])
        assert result.exit_code == 0
        assert "Run ID:" in result.output

    # TC-E2E-003: Conditional routing skip branch
    @pytest.mark.asyncio
    async def test_e2e_003_conditional_routing(self):
        spec = _make_spec({
            "classifier": {"agent": "llm://test", "outputs": ["category"]},
            "premium": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["classifier"],
                "when": "${classifier.category} == premium",
            },
            "standard": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["classifier"],
                "when": "${classifier.category} != premium",
            },
            "reporter": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["premium", "standard"],
            },
        })

        class CategoryAdapter:
            async def execute(self, task, inputs, trace_id):
                return [_make_artifact(task.run_id, task.node_id, "premium", "category")]
            async def cancel(self, tid): pass
            async def health(self): return AgentHealth.ALIVE

        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        orch.dispatcher.register_adapter("llm://test", CategoryAdapter())
        summary = await orch.run_workflow(spec)
        assert summary.status == "completed"
        # standard skipped, premium + classifier + reporter completed
        assert summary.skipped_nodes == 1
        assert summary.completed_nodes == 3

    # TC-E2E-005: Tool calling → LLM response
    @pytest.mark.asyncio
    async def test_e2e_005_tool_calling(self):
        """Verify tool schema resolution works end-to-end."""
        inline_tools = [{"name": "calc", "description": "Calculate", "parameters": {}}]
        resolved = resolve_tools(inline_tools)
        assert len(resolved) == 1
        assert resolved[0].name == "calc"
        schema = resolved[0].to_openai_schema()
        assert schema["type"] == "function"

    # TC-E2E-009: All CLI commands registered
    def test_e2e_009_all_commands_registered(self):
        from binex.cli.main import cli
        commands = cli.commands if hasattr(cli, "commands") else {}
        expected = {"run", "hello", "init", "start", "debug", "replay", "scaffold"}
        for cmd in expected:
            assert cmd in commands, f"Command '{cmd}' not registered in CLI"

    # TC-E2E-010: Workflow with all adapter types
    @pytest.mark.asyncio
    async def test_e2e_010_all_adapter_types(self):
        """Workflow with local and llm adapters completes."""
        spec = _make_spec({
            "local_node": {
                "agent": "local://echo",
                "outputs": ["result"],
            },
            "llm_node": {
                "agent": "llm://test",
                "outputs": ["result"],
                "depends_on": ["local_node"],
            },
        })
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())

        class EchoAdapter:
            async def execute(self, task, inputs, trace_id):
                return [_make_artifact(task.run_id, task.node_id, "echo")]
            async def cancel(self, tid): pass
            async def health(self): return AgentHealth.ALIVE

        orch.dispatcher.register_adapter("local://echo", EchoAdapter())
        orch.dispatcher.register_adapter("llm://test", FakeAdapter())
        summary = await orch.run_workflow(spec)
        assert summary.status == "completed"
        assert summary.completed_nodes == 2

    # TC-E2E-008: Error handling — failed node recorded
    @pytest.mark.asyncio
    async def test_e2e_008_error_handling(self):
        """Failed adapter causes node to be marked failed."""
        class FailAdapter:
            async def execute(self, task, inputs, trace_id):
                raise RuntimeError("connection refused")
            async def cancel(self, tid): pass
            async def health(self): return AgentHealth.ALIVE

        spec = _make_spec({
            "step1": {"agent": "llm://fail", "outputs": ["result"]},
        })
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        orch.dispatcher.register_adapter("llm://fail", FailAdapter())
        summary = await orch.run_workflow(spec)
        assert summary.status == "failed"
        assert summary.failed_nodes == 1

    # TC-E2E-002: Run + debug inspect
    @pytest.mark.asyncio
    async def test_e2e_002_run_then_debug(self):
        """Run workflow, then build debug report from same stores."""
        spec = _make_spec({
            "a": {"agent": "llm://test", "outputs": ["result"]},
            "b": {"agent": "llm://test", "outputs": ["result"], "depends_on": ["a"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("llm://test", FakeAdapter())
        summary = await orch.run_workflow(spec)

        from binex.trace.debug_report import build_debug_report
        report = await build_debug_report(exec_store, art_store, summary.run_id)
        assert report is not None
        assert report.status == "completed"
        assert len(report.nodes) == 2
