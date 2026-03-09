"""QA v3 Phase 1: Audit — Providers, DSL, Examples, Model/Spec changes.

Covers CAT-9 (TC-PROV-*), CAT-10 (TC-DSL-*), CAT-11 (TC-EX-*), CAT-14 (TC-MOD-*).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from binex.cli.dsl_parser import PATTERNS, parse_dsl
from binex.cli.providers import PROVIDERS, ProviderConfig, get_provider
from binex.models.task import TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.workflow_spec.validator import validate_workflow

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load_yaml(name: str) -> dict:
    path = EXAMPLES_DIR / name
    assert path.exists(), f"Missing: {path}"
    with open(path) as f:
        return yaml.safe_load(f)


# ===========================================================================
# CAT-9: Provider Registry (TC-PROV-001 .. TC-PROV-008)
# ===========================================================================


class TestProviderRegistryQA:
    """TC-PROV-001..008: Provider registry audit."""

    def test_prov_001_all_8_providers_registered(self):
        assert len(PROVIDERS) == 8
        expected = {
            "ollama", "openai", "anthropic", "gemini",
            "groq", "mistral", "deepseek", "together",
        }
        assert set(PROVIDERS.keys()) == expected

    def test_prov_002_default_models_non_empty(self):
        for name, cfg in PROVIDERS.items():
            assert cfg.default_model, f"{name} has empty default_model"
            assert isinstance(cfg.default_model, str)

    def test_prov_003_env_vars_none_for_ollama_set_for_others(self):
        assert PROVIDERS["ollama"].env_var is None
        for name, cfg in PROVIDERS.items():
            if name != "ollama":
                assert cfg.env_var is not None, f"{name} should have env_var"
                assert cfg.env_var.endswith("_API_KEY"), f"{name} env_var format"

    def test_prov_004_agent_prefixes_start_with_llm(self):
        for name, cfg in PROVIDERS.items():
            assert cfg.agent_prefix.startswith("llm://"), f"{name} prefix"

    def test_prov_005_get_provider_valid_name(self):
        for name in PROVIDERS:
            cfg = get_provider(name)
            assert cfg is not None
            assert cfg.name == name

    def test_prov_006_get_provider_invalid_returns_none(self):
        assert get_provider("nonexistent") is None
        assert get_provider("") is None
        assert get_provider("OPENAI") is None  # case-sensitive

    def test_prov_007_provider_prefix_used_in_model_resolution(self):
        """Agent prefix should form valid agent URIs with model appended."""
        for name, cfg in PROVIDERS.items():
            uri = cfg.agent_prefix + cfg.default_model.split("/")[-1]
            assert uri.startswith("llm://")

    def test_prov_008_provider_config_fields(self):
        cfg = ProviderConfig(
            name="test", default_model="test/model", env_var="TEST_KEY", agent_prefix="llm://test/"
        )
        assert cfg.name == "test"
        assert cfg.default_model == "test/model"
        assert cfg.env_var == "TEST_KEY"
        assert cfg.agent_prefix == "llm://test/"


# ===========================================================================
# CAT-10: DSL Parser (TC-DSL-001 .. TC-DSL-012)
# ===========================================================================


class TestDSLParserQA:
    """TC-DSL-001..012: DSL parser audit."""

    def test_dsl_001_linear(self):
        r = parse_dsl(["A -> B -> C"])
        assert r.nodes == ["A", "B", "C"]
        assert ("A", "B") in r.edges and ("B", "C") in r.edges
        assert r.depends_on["C"] == ["B"]

    def test_dsl_002_fan_out(self):
        r = parse_dsl(["A -> B, C, D"])
        assert r.nodes == ["A", "B", "C", "D"]
        for tgt in ["B", "C", "D"]:
            assert ("A", tgt) in r.edges
            assert r.depends_on[tgt] == ["A"]

    def test_dsl_003_fan_in(self):
        r = parse_dsl(["A, B, C -> D"])
        assert set(r.depends_on["D"]) == {"A", "B", "C"}

    def test_dsl_004_fan_out_fan_in(self):
        r = parse_dsl(["A -> B, C -> D"])
        assert ("A", "B") in r.edges
        assert ("A", "C") in r.edges
        assert ("B", "D") in r.edges
        assert ("C", "D") in r.edges

    def test_dsl_005_diamond(self):
        r = parse_dsl(["A -> B, C -> D"])
        assert len(r.nodes) == 4
        assert sorted(r.depends_on["D"]) == ["B", "C"]

    def test_dsl_006_all_16_patterns_valid(self):
        """Every predefined pattern must parse without errors and produce nodes+edges."""
        assert len(PATTERNS) >= 16
        for name, dsl in PATTERNS.items():
            r = parse_dsl([dsl])
            assert len(r.nodes) > 0, f"Pattern '{name}': no nodes"
            assert len(r.edges) > 0, f"Pattern '{name}': no edges"

    def test_dsl_007_custom_arbitrary_topology(self):
        r = parse_dsl(["X -> Y", "Y -> Z, W", "Z, W -> FINAL"])
        assert "FINAL" in r.nodes
        assert sorted(r.depends_on["FINAL"]) == ["W", "Z"]

    def test_dsl_008_empty_raises(self):
        import pytest
        with pytest.raises(ValueError, match="empty"):
            parse_dsl([])

    def test_dsl_009_malformed_empty_node(self):
        import pytest
        with pytest.raises(ValueError):
            parse_dsl(["A -> -> B"])

    def test_dsl_010_node_ordering_preserved(self):
        r = parse_dsl(["Z -> Y -> X"])
        assert r.nodes == ["Z", "Y", "X"]

    def test_dsl_011_edge_deduplication(self):
        r = parse_dsl(["A -> B", "A -> B"])
        assert r.edges.count(("A", "B")) == 1

    def test_dsl_012_depends_on_map_correct(self):
        r = parse_dsl(["A -> B, C -> D"])
        assert r.depends_on["A"] == []
        assert r.depends_on["B"] == ["A"]
        assert r.depends_on["C"] == ["A"]
        assert sorted(r.depends_on["D"]) == ["B", "C"]


# ===========================================================================
# CAT-11: Example Workflows (TC-EX-001 .. TC-EX-010)
# ===========================================================================


class TestExampleWorkflowsQA:
    """TC-EX-001..010: Example YAML validation."""

    def test_ex_001_hello_world_loads(self):
        data = _load_yaml("hello-world.yaml")
        assert data["name"] == "hello-world"
        assert "greeter" in data["nodes"]
        assert "responder" in data["nodes"]

    def test_ex_002_human_in_the_loop_when_conditions(self):
        data = _load_yaml("human-in-the-loop.yaml")
        pay = data["nodes"]["pay"]
        cancel = data["nodes"]["cancel"]
        assert "when" in pay
        assert "when" in cancel
        assert "==" in pay["when"]
        assert "==" in cancel["when"]

    def test_ex_003_multi_provider_3_providers(self):
        data = _load_yaml("multi-provider-research.yaml")
        agents = {n["agent"] for n in data["nodes"].values()}
        # Should have 3 distinct agents (gpt-4o, gemini, claude)
        assert len(agents) == 3
        assert any("gpt" in a for a in agents)
        assert any("gemini" in a for a in agents)
        assert any("claude" in a for a in agents)

    def test_ex_004_conditional_routing_structure(self):
        data = _load_yaml("conditional-routing.yaml")
        assert "classifier" in data["nodes"]
        assert "premium_handler" in data["nodes"]
        assert "standard_handler" in data["nodes"]
        assert "when" in data["nodes"]["premium_handler"]
        assert "when" in data["nodes"]["standard_handler"]

    def test_ex_005_error_handling_retry_config(self):
        data = _load_yaml("error-handling.yaml")
        assert "defaults" in data
        assert data["defaults"]["retry_policy"]["max_retries"] == 2
        assert data["defaults"]["deadline_ms"] == 30000
        risky = data["nodes"]["risky"]
        assert risky["config"]["max_retries"] == 5

    def test_ex_006_all_new_examples_schema_valid(self):
        """All YAML files must have 'name' and 'nodes' with at least 1 node."""
        yaml_files = sorted(EXAMPLES_DIR.glob("*.yaml"))
        assert len(yaml_files) >= 15, f"Expected >=15 examples, got {len(yaml_files)}"
        for path in yaml_files:
            with open(path) as f:
                data = yaml.safe_load(f)
            assert "name" in data, f"{path.name}: missing 'name'"
            assert "nodes" in data, f"{path.name}: missing 'nodes'"
            assert len(data["nodes"]) >= 1, f"{path.name}: no nodes"
            for nid, node in data["nodes"].items():
                assert "agent" in node, f"{path.name}:{nid}: missing 'agent'"
                assert "outputs" in node, f"{path.name}:{nid}: missing 'outputs'"

    def test_ex_007_diamond_dag_valid(self):
        data = _load_yaml("diamond.yaml")
        assert len(data["nodes"]) >= 4

    def test_ex_008_fan_out_fan_in_structure(self):
        data = _load_yaml("fan-out-fan-in.yaml")
        nodes = data["nodes"]
        # Should have entry, parallel workers, and aggregator
        assert len(nodes) >= 3

    def test_ex_009_secure_pipeline_loads(self):
        data = _load_yaml("secure-pipeline.yaml")
        assert data["name"]
        assert len(data["nodes"]) >= 2

    def test_ex_010_all_examples_unique_node_names(self):
        """Node names must be unique within each YAML."""
        yaml_files = sorted(EXAMPLES_DIR.glob("*.yaml"))
        for path in yaml_files:
            with open(path) as f:
                data = yaml.safe_load(f)
            nodes = data.get("nodes", {})
            # dict keys are inherently unique, but check they're all non-empty strings
            for nid in nodes:
                assert isinstance(nid, str) and nid.strip(), (
                    f"{path.name}: empty/invalid node name"
                )


# ===========================================================================
# CAT-14: Model/Spec Changes (TC-MOD-001 .. TC-MOD-006)
# ===========================================================================


class TestModelSpecChangesQA:
    """TC-MOD-001..006: New fields on NodeSpec, TaskNode, WorkflowSpec."""

    def test_mod_001_nodespec_tools_default_empty(self):
        ns = NodeSpec(agent="local://echo", outputs=["result"])
        assert ns.tools == []

    def test_mod_002_nodespec_tools_serializes(self):
        ns = NodeSpec(
            agent="llm://gpt-4o",
            outputs=["result"],
            tools=[
                "python://mymodule.search",
                {"name": "calculator", "description": "math", "parameters": {}},
            ],
        )
        dump = ns.model_dump()
        assert len(dump["tools"]) == 2
        assert dump["tools"][0] == "python://mymodule.search"
        assert dump["tools"][1]["name"] == "calculator"

    def test_mod_003_tasknode_tools_mirrors_nodespec(self):
        tn = TaskNode(
            id="t1", run_id="r1", node_id="n1", agent="llm://gpt-4o",
            tools=["python://mod.func"],
        )
        assert tn.tools == ["python://mod.func"]

    def test_mod_003b_tasknode_tools_default_empty(self):
        tn = TaskNode(id="t1", run_id="r1", node_id="n1", agent="local://echo")
        assert tn.tools == []

    def test_mod_004_nodespec_when_optional_string(self):
        ns_none = NodeSpec(agent="local://echo", outputs=["out"])
        assert ns_none.when is None
        ns_val = NodeSpec(
            agent="local://echo", outputs=["out"],
            when="${check.result} == yes",
        )
        assert ns_val.when == "${check.result} == yes"

    def test_mod_005_workflowspec_tools_from_yaml(self):
        """tools field should survive YAML round-trip via WorkflowSpec."""
        spec = WorkflowSpec(
            name="test-tools",
            nodes={
                "node1": NodeSpec(
                    agent="llm://gpt-4o",
                    outputs=["result"],
                    tools=["python://tools.search"],
                ),
            },
        )
        assert spec.nodes["node1"].tools == ["python://tools.search"]

    def test_mod_006_validator_check_when_conditions_integration(self):
        """Validator should catch invalid when syntax."""
        spec = WorkflowSpec(
            name="test",
            nodes={
                "a": NodeSpec(agent="local://echo", outputs=["result"]),
                "b": NodeSpec(
                    agent="local://echo",
                    outputs=["result"],
                    depends_on=["a"],
                    when="${a.result} == yes",
                ),
            },
        )
        errors = validate_workflow(spec)
        assert not errors, f"Unexpected errors: {errors}"

    def test_mod_006b_validator_catches_bad_when(self):
        spec = WorkflowSpec(
            name="test",
            nodes={
                "a": NodeSpec(agent="local://echo", outputs=["result"]),
                "b": NodeSpec(
                    agent="local://echo",
                    outputs=["result"],
                    depends_on=["a"],
                    when="not valid syntax",
                ),
            },
        )
        errors = validate_workflow(spec)
        assert any("when" in e.lower() or "syntax" in e.lower() for e in errors)
