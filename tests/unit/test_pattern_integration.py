from binex.workflow_spec.loader import load_workflow_from_string

CRITIC_YAML = """
name: test-critic
nodes:
  researcher:
    pattern: critic
    agent: llm://claude-sonnet-4-6
    system_prompt: "Research AI safety"
    config:
      rounds: 2
    outputs: [report]
  writer:
    agent: llm://claude-sonnet-4-6
    depends_on: [researcher]
    system_prompt: "Write article from research"
    outputs: [article]
"""


class TestPatternYAMLIntegration:
    def test_critic_expands_in_workflow(self):
        spec = load_workflow_from_string(CRITIC_YAML, fmt="yaml")
        # Pattern node replaced by 3 sub-nodes
        assert "researcher" not in spec.nodes
        assert "researcher.draft" in spec.nodes
        assert "researcher.critique" in spec.nodes
        assert "researcher.refine" in spec.nodes
        # Writer depends on exit node
        assert "researcher.refine" in spec.nodes["writer"].depends_on

    def test_dag_builds_after_expansion(self):
        from binex.graph.dag import DAG
        spec = load_workflow_from_string(CRITIC_YAML, fmt="yaml")
        dag = DAG.from_workflow(spec)
        order = dag.topological_order()
        assert order.index("researcher.draft") < order.index("researcher.critique")
        assert order.index("researcher.critique") < order.index("researcher.refine")
        assert order.index("researcher.refine") < order.index("writer")

    def test_no_pattern_nodes_unchanged(self):
        plain_yaml = """
name: test-plain
nodes:
  a:
    agent: llm://m
    outputs: [x]
  b:
    agent: llm://m
    depends_on: [a]
    outputs: [y]
"""
        spec = load_workflow_from_string(plain_yaml, fmt="yaml")
        assert "a" in spec.nodes
        assert "b" in spec.nodes
        assert len(spec.nodes) == 2
