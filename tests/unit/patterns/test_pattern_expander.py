import pytest

from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.patterns.models import PatternSpec, StepConfig
from binex.patterns.templates.best_of_n import expand_best_of_n
from binex.patterns.templates.chain_of_verification import expand_chain_of_verification
from binex.patterns.templates.constitutional import expand_constitutional
from binex.patterns.templates.critic import expand_critic
from binex.patterns.templates.debate import expand_debate
from binex.patterns.templates.fsm import expand_fsm
from binex.patterns.templates.plan_execute import expand_plan_execute
from binex.patterns.templates.reflexion import expand_reflexion
from binex.patterns.templates.scatter import expand_scatter


class TestCriticExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="r", pattern="critic", model="llm://claude-sonnet-4-6")
        nodes, edges, back_edges = expand_critic(spec)

        assert len(nodes) == 3
        ids = {n.id for n in nodes}
        assert ids == {"r.draft", "r.critique", "r.refine"}

        for n in nodes:
            assert n.agent == "llm://claude-sonnet-4-6"

        assert ("r.draft", "r.critique") in edges
        assert ("r.critique", "r.refine") in edges

    def test_step_model_override(self):
        spec = PatternSpec(
            id="r", pattern="critic", model="llm://claude-sonnet-4-6",
            steps={"draft": StepConfig(model="llm://claude-haiku-4-5", prompt="Quick draft")},
        )
        nodes, edges, back_edges = expand_critic(spec)
        draft = next(n for n in nodes if n.id == "r.draft")
        assert draft.agent == "llm://claude-haiku-4-5"
        assert "Quick draft" in draft.system_prompt

    def test_rounds_create_back_edge(self):
        spec = PatternSpec(id="r", pattern="critic", model="llm://m", config={"rounds": 3})
        nodes, edges, back_edges = expand_critic(spec)
        assert len(back_edges) == 1
        be = back_edges[0]
        assert be["node_id"] == "r.refine"
        assert be["target"] == "r.draft"
        assert be["max_iterations"] == 3

    def test_group_metadata(self):
        spec = PatternSpec(id="r", pattern="critic", model="llm://m")
        nodes, _, _ = expand_critic(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "r"
            assert n.config.get("_pattern_type") == "critic"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(id="r", pattern="critic", model="llm://m", depends_on=["upstream"])
        nodes, _, _ = expand_critic(spec)
        draft = next(n for n in nodes if n.id == "r.draft")
        assert "upstream" in draft.depends_on


class TestDebateExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="d", pattern="debate", model="llm://m")
        nodes, edges, back_edges = expand_debate(spec)
        # 2 agents + collector + judge = 4
        assert len(nodes) == 4
        ids = {n.id for n in nodes}
        assert ids == {"d.agent_1", "d.agent_2", "d.collector", "d.judge"}

    def test_edge_wiring(self):
        spec = PatternSpec(id="d", pattern="debate", model="llm://m")
        nodes, edges, back_edges = expand_debate(spec)
        assert ("d.agent_1", "d.collector") in edges
        assert ("d.agent_2", "d.collector") in edges
        assert ("d.collector", "d.judge") in edges

    def test_custom_agent_count(self):
        spec = PatternSpec(id="d", pattern="debate", model="llm://m", config={"agents": 4})
        nodes, edges, back_edges = expand_debate(spec)
        assert len(nodes) == 6  # 4 agents + collector + judge
        agent_ids = {n.id for n in nodes if "agent_" in n.id}
        assert len(agent_ids) == 4

    def test_model_override(self):
        spec = PatternSpec(
            id="d", pattern="debate", model="llm://m",
            steps={"judge": StepConfig(model="llm://big")},
        )
        nodes, _, _ = expand_debate(spec)
        judge = next(n for n in nodes if n.id == "d.judge")
        assert judge.agent == "llm://big"

    def test_rounds_back_edge(self):
        spec = PatternSpec(id="d", pattern="debate", model="llm://m", config={"rounds": 3})
        nodes, edges, back_edges = expand_debate(spec)
        assert len(back_edges) == 1
        be = back_edges[0]
        assert be["node_id"] == "d.judge"
        assert be["target"] == "d.agent_1"
        assert be["max_iterations"] == 3

    def test_group_metadata(self):
        spec = PatternSpec(id="d", pattern="debate", model="llm://m")
        nodes, _, _ = expand_debate(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "d"
            assert n.config.get("_pattern_type") == "debate"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(id="d", pattern="debate", model="llm://m", depends_on=["up"])
        nodes, _, _ = expand_debate(spec)
        agent1 = next(n for n in nodes if n.id == "d.agent_1")
        assert "up" in agent1.depends_on


class TestBestOfNExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="b", pattern="best_of_n", model="llm://m")
        nodes, edges, back_edges = expand_best_of_n(spec)
        assert len(nodes) == 4  # 3 variants + judge
        ids = {n.id for n in nodes}
        assert ids == {"b.variant_1", "b.variant_2", "b.variant_3", "b.judge"}

    def test_edge_wiring(self):
        spec = PatternSpec(id="b", pattern="best_of_n", model="llm://m")
        nodes, edges, back_edges = expand_best_of_n(spec)
        assert ("b.variant_1", "b.judge") in edges
        assert ("b.variant_2", "b.judge") in edges
        assert ("b.variant_3", "b.judge") in edges
        assert len(back_edges) == 0

    def test_custom_variant_count(self):
        spec = PatternSpec(id="b", pattern="best_of_n", model="llm://m", config={"variants": 5})
        nodes, edges, back_edges = expand_best_of_n(spec)
        assert len(nodes) == 6  # 5 variants + judge

    def test_model_override(self):
        spec = PatternSpec(
            id="b", pattern="best_of_n", model="llm://m",
            steps={"judge": StepConfig(model="llm://big")},
        )
        nodes, _, _ = expand_best_of_n(spec)
        judge = next(n for n in nodes if n.id == "b.judge")
        assert judge.agent == "llm://big"

    def test_group_metadata(self):
        spec = PatternSpec(id="b", pattern="best_of_n", model="llm://m")
        nodes, _, _ = expand_best_of_n(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "b"
            assert n.config.get("_pattern_type") == "best_of_n"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(id="b", pattern="best_of_n", model="llm://m", depends_on=["up"])
        nodes, _, _ = expand_best_of_n(spec)
        v1 = next(n for n in nodes if n.id == "b.variant_1")
        assert "up" in v1.depends_on


class TestReflexionExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="rx", pattern="reflexion", model="llm://m")
        nodes, edges, back_edges = expand_reflexion(spec)
        assert len(nodes) == 2
        ids = {n.id for n in nodes}
        assert ids == {"rx.actor", "rx.reflector"}

    def test_edge_wiring(self):
        spec = PatternSpec(id="rx", pattern="reflexion", model="llm://m")
        nodes, edges, back_edges = expand_reflexion(spec)
        assert ("rx.actor", "rx.reflector") in edges

    def test_back_edge(self):
        spec = PatternSpec(
            id="rx", pattern="reflexion", model="llm://m", config={"max_iterations": 5}
        )
        nodes, edges, back_edges = expand_reflexion(spec)
        assert len(back_edges) == 1
        be = back_edges[0]
        assert be["node_id"] == "rx.reflector"
        assert be["target"] == "rx.actor"
        assert be["max_iterations"] == 5

    def test_default_back_edge_iterations(self):
        spec = PatternSpec(id="rx", pattern="reflexion", model="llm://m")
        _, _, back_edges = expand_reflexion(spec)
        assert back_edges[0]["max_iterations"] == 3

    def test_model_override(self):
        spec = PatternSpec(
            id="rx", pattern="reflexion", model="llm://m",
            steps={"reflector": StepConfig(model="llm://big")},
        )
        nodes, _, _ = expand_reflexion(spec)
        reflector = next(n for n in nodes if n.id == "rx.reflector")
        assert reflector.agent == "llm://big"

    def test_group_metadata(self):
        spec = PatternSpec(id="rx", pattern="reflexion", model="llm://m")
        nodes, _, _ = expand_reflexion(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "rx"
            assert n.config.get("_pattern_type") == "reflexion"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(id="rx", pattern="reflexion", model="llm://m", depends_on=["up"])
        nodes, _, _ = expand_reflexion(spec)
        actor = next(n for n in nodes if n.id == "rx.actor")
        assert "up" in actor.depends_on


class TestScatterExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="s", pattern="scatter", model="llm://m", config={"max_workers": 3})
        nodes, edges, back_edges = expand_scatter(spec)
        assert len(nodes) == 5  # mapper + 3 workers + reducer
        ids = {n.id for n in nodes}
        assert ids == {"s.mapper", "s.worker_1", "s.worker_2", "s.worker_3", "s.reducer"}

    def test_edge_wiring(self):
        spec = PatternSpec(id="s", pattern="scatter", model="llm://m", config={"max_workers": 2})
        nodes, edges, back_edges = expand_scatter(spec)
        assert ("s.mapper", "s.worker_1") in edges
        assert ("s.mapper", "s.worker_2") in edges
        assert ("s.worker_1", "s.reducer") in edges
        assert ("s.worker_2", "s.reducer") in edges
        assert len(back_edges) == 0

    def test_model_override(self):
        spec = PatternSpec(
            id="s", pattern="scatter", model="llm://m", config={"max_workers": 2},
            steps={"reducer": StepConfig(model="llm://big")},
        )
        nodes, _, _ = expand_scatter(spec)
        reducer = next(n for n in nodes if n.id == "s.reducer")
        assert reducer.agent == "llm://big"

    def test_group_metadata(self):
        spec = PatternSpec(id="s", pattern="scatter", model="llm://m", config={"max_workers": 2})
        nodes, _, _ = expand_scatter(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "s"
            assert n.config.get("_pattern_type") == "scatter"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(
            id="s",
            pattern="scatter",
            model="llm://m",
            config={"max_workers": 2},
            depends_on=["up"],
        )
        nodes, _, _ = expand_scatter(spec)
        mapper = next(n for n in nodes if n.id == "s.mapper")
        assert "up" in mapper.depends_on


class TestFSMExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="f", pattern="fsm", model="llm://m")
        nodes, edges, back_edges = expand_fsm(spec)
        assert len(nodes) == 2  # start, end
        ids = {n.id for n in nodes}
        assert ids == {"f.start", "f.end"}

    def test_custom_states(self):
        spec = PatternSpec(
            id="f",
            pattern="fsm",
            model="llm://m",
            config={"states": ["idle", "active", "done"]},
        )
        nodes, edges, back_edges = expand_fsm(spec)
        assert len(nodes) == 3
        ids = {n.id for n in nodes}
        assert ids == {"f.idle", "f.active", "f.done"}

    def test_edge_wiring(self):
        spec = PatternSpec(
            id="f", pattern="fsm", model="llm://m", config={"states": ["a", "b", "c"]}
        )
        nodes, edges, back_edges = expand_fsm(spec)
        assert ("f.a", "f.b") in edges
        assert ("f.b", "f.c") in edges

    def test_back_edges(self):
        spec = PatternSpec(
            id="f",
            pattern="fsm",
            model="llm://m",
            config={"states": ["a", "b", "c"], "max_iterations": 5},
        )
        nodes, edges, back_edges = expand_fsm(spec)
        assert len(back_edges) == 2  # b->a and c->a
        targets = {be["node_id"] for be in back_edges}
        assert targets == {"f.b", "f.c"}
        for be in back_edges:
            assert be["target"] == "f.a"
            assert be["max_iterations"] == 5

    def test_model_override(self):
        spec = PatternSpec(
            id="f", pattern="fsm", model="llm://m",
            steps={"end": StepConfig(model="llm://big")},
        )
        nodes, _, _ = expand_fsm(spec)
        end = next(n for n in nodes if n.id == "f.end")
        assert end.agent == "llm://big"

    def test_group_metadata(self):
        spec = PatternSpec(id="f", pattern="fsm", model="llm://m")
        nodes, _, _ = expand_fsm(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "f"
            assert n.config.get("_pattern_type") == "fsm"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(id="f", pattern="fsm", model="llm://m", depends_on=["up"])
        nodes, _, _ = expand_fsm(spec)
        start = next(n for n in nodes if n.id == "f.start")
        assert "up" in start.depends_on


class TestConstitutionalExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="c", pattern="constitutional", model="llm://m")
        nodes, edges, back_edges = expand_constitutional(spec)
        assert len(nodes) == 3
        ids = {n.id for n in nodes}
        assert ids == {"c.generate", "c.critique_principles", "c.revise"}
        assert len(back_edges) == 0

    def test_edge_wiring(self):
        spec = PatternSpec(id="c", pattern="constitutional", model="llm://m")
        nodes, edges, back_edges = expand_constitutional(spec)
        assert ("c.generate", "c.critique_principles") in edges
        assert ("c.critique_principles", "c.revise") in edges

    def test_model_override(self):
        spec = PatternSpec(
            id="c", pattern="constitutional", model="llm://m",
            steps={"revise": StepConfig(model="llm://big")},
        )
        nodes, _, _ = expand_constitutional(spec)
        revise = next(n for n in nodes if n.id == "c.revise")
        assert revise.agent == "llm://big"

    def test_group_metadata(self):
        spec = PatternSpec(id="c", pattern="constitutional", model="llm://m")
        nodes, _, _ = expand_constitutional(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "c"
            assert n.config.get("_pattern_type") == "constitutional"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(id="c", pattern="constitutional", model="llm://m", depends_on=["up"])
        nodes, _, _ = expand_constitutional(spec)
        gen = next(n for n in nodes if n.id == "c.generate")
        assert "up" in gen.depends_on


class TestChainOfVerificationExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="cv", pattern="chain_of_verification", model="llm://m")
        nodes, edges, back_edges = expand_chain_of_verification(spec)
        assert len(nodes) == 4
        ids = {n.id for n in nodes}
        assert ids == {"cv.generate", "cv.extract_claims", "cv.verify_each", "cv.revise"}
        assert len(back_edges) == 0

    def test_edge_wiring(self):
        spec = PatternSpec(id="cv", pattern="chain_of_verification", model="llm://m")
        nodes, edges, back_edges = expand_chain_of_verification(spec)
        assert ("cv.generate", "cv.extract_claims") in edges
        assert ("cv.extract_claims", "cv.verify_each") in edges
        assert ("cv.verify_each", "cv.revise") in edges

    def test_model_override(self):
        spec = PatternSpec(
            id="cv", pattern="chain_of_verification", model="llm://m",
            steps={"verify_each": StepConfig(model="llm://big")},
        )
        nodes, _, _ = expand_chain_of_verification(spec)
        verify = next(n for n in nodes if n.id == "cv.verify_each")
        assert verify.agent == "llm://big"

    def test_group_metadata(self):
        spec = PatternSpec(id="cv", pattern="chain_of_verification", model="llm://m")
        nodes, _, _ = expand_chain_of_verification(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "cv"
            assert n.config.get("_pattern_type") == "chain_of_verification"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(
            id="cv", pattern="chain_of_verification", model="llm://m", depends_on=["up"]
        )
        nodes, _, _ = expand_chain_of_verification(spec)
        gen = next(n for n in nodes if n.id == "cv.generate")
        assert "up" in gen.depends_on


class TestPlanExecuteExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="pe", pattern="plan_execute", model="llm://m")
        nodes, edges, back_edges = expand_plan_execute(spec)
        assert len(nodes) == 3
        ids = {n.id for n in nodes}
        assert ids == {"pe.planner", "pe.executor", "pe.verifier"}

    def test_edge_wiring(self):
        spec = PatternSpec(id="pe", pattern="plan_execute", model="llm://m")
        nodes, edges, back_edges = expand_plan_execute(spec)
        assert ("pe.planner", "pe.executor") in edges
        assert ("pe.executor", "pe.verifier") in edges

    def test_back_edge(self):
        spec = PatternSpec(
            id="pe", pattern="plan_execute", model="llm://m", config={"max_iterations": 5}
        )
        nodes, edges, back_edges = expand_plan_execute(spec)
        assert len(back_edges) == 1
        be = back_edges[0]
        assert be["node_id"] == "pe.verifier"
        assert be["target"] == "pe.planner"
        assert be["max_iterations"] == 5

    def test_default_back_edge_iterations(self):
        spec = PatternSpec(id="pe", pattern="plan_execute", model="llm://m")
        _, _, back_edges = expand_plan_execute(spec)
        assert back_edges[0]["max_iterations"] == 3

    def test_model_override(self):
        spec = PatternSpec(
            id="pe", pattern="plan_execute", model="llm://m",
            steps={"executor": StepConfig(model="llm://big")},
        )
        nodes, _, _ = expand_plan_execute(spec)
        executor = next(n for n in nodes if n.id == "pe.executor")
        assert executor.agent == "llm://big"

    def test_group_metadata(self):
        spec = PatternSpec(id="pe", pattern="plan_execute", model="llm://m")
        nodes, _, _ = expand_plan_execute(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "pe"
            assert n.config.get("_pattern_type") == "plan_execute"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(id="pe", pattern="plan_execute", model="llm://m", depends_on=["up"])
        nodes, _, _ = expand_plan_execute(spec)
        planner = next(n for n in nodes if n.id == "pe.planner")
        assert "up" in planner.depends_on


class TestExpandPatterns:
    """Integration tests for expand_patterns() at WorkflowSpec level."""

    def _make_spec(self, nodes_raw: dict) -> WorkflowSpec:
        # Build minimal WorkflowSpec from node dicts
        nodes = {}
        for node_id, cfg in nodes_raw.items():
            nodes[node_id] = NodeSpec(**cfg)
        return WorkflowSpec(version="1.0", name="test", nodes=nodes)

    def _pattern_node(self, pattern: str, depends_on: list[str] | None = None):
        return NodeSpec(agent="llm://m", pattern=pattern, outputs=[], depends_on=depends_on or [])

    def _regular_node(self, depends_on: list[str] | None = None):
        return NodeSpec(agent="llm://m", outputs=[], depends_on=depends_on or [])

    def test_single_pattern_expands(self):
        from binex.patterns.expander import expand_patterns
        spec = WorkflowSpec(
            version="1.0", name="t",
            nodes={"a": self._pattern_node("critic")},
        )
        result = expand_patterns(spec)
        assert "a" not in result.nodes
        assert "a.draft" in result.nodes
        assert "a.refine" in result.nodes

    def test_chained_patterns_rewired(self):
        """Pattern B depends on pattern A — B's entry must depend on A's exit, not 'a'."""
        from binex.patterns.expander import expand_patterns
        spec = WorkflowSpec(
            version="1.0", name="t",
            nodes={
                "a": self._pattern_node("critic"),
                "b": self._pattern_node("debate", depends_on=["a"]),
            },
        )
        result = expand_patterns(spec)
        assert "a" not in result.nodes
        assert "b" not in result.nodes
        # Critic exit = a.refine; debate entry = b.agent_1
        b_entry = result.nodes["b.agent_1"]
        assert "a.refine" in b_entry.depends_on, (
            f"b.agent_1.depends_on should contain 'a.refine', got {b_entry.depends_on}"
        )
        assert "a" not in b_entry.depends_on, (
            f"Stale pattern ID 'a' still in b.agent_1.depends_on: {b_entry.depends_on}"
        )

    def test_regular_node_after_pattern_rewired(self):
        """A regular node depending on a pattern should depend on the exit node."""
        from binex.patterns.expander import expand_patterns
        spec = WorkflowSpec(
            version="1.0", name="t",
            nodes={
                "a": self._pattern_node("critic"),
                "sink": self._regular_node(depends_on=["a"]),
            },
        )
        result = expand_patterns(spec)
        sink = result.nodes["sink"]
        assert "a.refine" in sink.depends_on
        assert "a" not in sink.depends_on


class TestTemplateRegistry:
    def test_all_patterns_registered(self):
        from binex.patterns.templates import TEMPLATE_REGISTRY
        expected = {
            "critic",
            "debate",
            "best_of_n",
            "reflexion",
            "scatter",
            "fsm",
            "constitutional",
            "chain_of_verification",
            "plan_execute",
        }
        assert set(TEMPLATE_REGISTRY.keys()) == expected

    def test_expand_pattern_dispatches(self):
        from binex.patterns.templates import expand_pattern
        spec = PatternSpec(id="t", pattern="debate", model="llm://m")
        nodes, edges, back_edges = expand_pattern(spec)
        assert len(nodes) == 4  # debate default: 2 agents + collector + judge

    def test_expand_pattern_unknown_raises(self):
        from binex.patterns.templates import expand_pattern
        # Bypass PatternSpec validation to test registry error handling
        spec = PatternSpec.model_construct(id="t", pattern="nonexistent", model="llm://m")
        with pytest.raises(ValueError, match="No template for pattern"):
            expand_pattern(spec)
