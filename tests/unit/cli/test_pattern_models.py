import pytest

from binex.patterns.models import PatternSpec, StepConfig


class TestStepConfig:
    def test_minimal(self):
        s = StepConfig(prompt="Do the thing")
        assert s.prompt == "Do the thing"
        assert s.model is None

    def test_with_model_override(self):
        s = StepConfig(prompt="Draft it", model="llm://claude-haiku-4-5")
        assert s.model == "llm://claude-haiku-4-5"

class TestPatternSpec:
    def test_critic_minimal(self):
        p = PatternSpec(id="researcher", pattern="critic", model="llm://claude-sonnet-4-6")
        assert p.pattern == "critic"
        assert p.config == {}
        assert p.steps == {}

    def test_critic_with_steps(self):
        p = PatternSpec(
            id="researcher",
            pattern="critic",
            model="llm://claude-sonnet-4-6",
            system_prompt="Research X",
            config={"rounds": 2},
            steps={"draft": StepConfig(model="llm://claude-haiku-4-5", prompt="Write draft")},
        )
        assert p.config["rounds"] == 2
        assert p.steps["draft"].model == "llm://claude-haiku-4-5"

    def test_unknown_pattern_rejected(self):
        with pytest.raises(ValueError, match="Unknown pattern"):
            PatternSpec(id="x", pattern="nonexistent", model="llm://m")

    def test_debate_requires_agents_count(self):
        p = PatternSpec(id="d", pattern="debate", model="llm://m", config={"agents": 3})
        assert p.config["agents"] == 3
