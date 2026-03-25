import pytest
from binex.patterns.models import PatternSpec
from binex.patterns.templates.critic import expand_critic


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
        from binex.patterns.models import StepConfig
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
