import { describe, it, expect } from 'vitest';
import { parseWorkflowYaml } from './yaml-to-graph';

describe('parseWorkflowYaml', () => {
  it('extracts foreach so the editor can badge runtime fan-out (#77)', () => {
    const yaml = `
name: fan-out
nodes:
  plan:
    agent: llm://gpt-4o
  work:
    agent: llm://gpt-4o-mini
    foreach: plan
    depends_on: [plan]
`;
    const { nodes, edges } = parseWorkflowYaml(yaml);
    const work = nodes.find((n) => n.id === 'work')!;
    expect(work.foreach).toBe('plan');
    const plan = nodes.find((n) => n.id === 'plan')!;
    expect(plan.foreach).toBeUndefined();
    expect(edges).toContainEqual({ id: 'plan->work', source: 'plan', target: 'work' });
  });

  it('leaves foreach undefined for ordinary nodes', () => {
    const { nodes } = parseWorkflowYaml('nodes:\n  a:\n    agent: local://x\n');
    expect(nodes[0].foreach).toBeUndefined();
  });
});
