import yaml from 'js-yaml';
import type { Node, Edge } from 'reactflow';

export function graphToYaml(nodes: Node[], edges: Edge[], workflowName = 'my-workflow'): string {
  if (nodes.length === 0) return '';

  const nodesObj: Record<string, Record<string, unknown>> = {};

  const deps: Record<string, string[]> = {};
  for (const e of edges) {
    if (!deps[e.target]) deps[e.target] = [];
    deps[e.target].push(e.source);
  }

  for (const node of nodes) {
    const d = node.data;
    const entry: Record<string, unknown> = {
      agent: d.agent || 'local://echo',
    };

    const config: Record<string, unknown> = {};
    if (d.config?.max_tokens) config.max_tokens = d.config.max_tokens;
    if (d.config?.temperature != null) config.temperature = d.config.temperature;
    if (d.config?.system_prompt) config.system_prompt = d.config.system_prompt;
    if (d.config?.budget_limit) config.budget_limit = d.config.budget_limit;
    if (d.config?.skill) config.skill = d.config.skill;
    if (d.config?.prompt_message) config.prompt_message = d.config.prompt_message;
    if (Object.keys(config).length > 0) entry.config = config;

    if (deps[node.id]?.length) {
      entry.depends_on = deps[node.id].map((depId) => {
        const depNode = nodes.find((n) => n.id === depId);
        return depNode?.data?.label || depId;
      });
    }

    const nodeLabel = d.label || node.id;
    nodesObj[nodeLabel] = entry;
  }

  return yaml.dump({ name: workflowName, nodes: nodesObj }, { indent: 2, lineWidth: 120, noRefs: true });
}
