import yaml from 'js-yaml';
import type { Node, Edge } from 'reactflow';

export interface GraphToYamlOptions {
  mcpServers?: Record<string, unknown>;
  schedule?: string;
}

export function graphToYaml(nodes: Node[], edges: Edge[], workflowName = 'my-workflow', options?: GraphToYamlOptions): string {
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
      agent: d.agent ?? 'local://echo',
      outputs: ['output'],
    };

    // system_prompt is top-level in YAML (used by LLM and Human adapters)
    const promptText = d.system_prompt ?? d.config?.system_prompt ?? d.config?.prompt_message;
    if (promptText) entry.system_prompt = promptText;

    const config: Record<string, unknown> = {};
    if (d.config?.max_tokens) config.max_tokens = d.config.max_tokens;
    if (d.config?.temperature != null) config.temperature = d.config.temperature;
    if (d.config?.budget_limit) config.budget_limit = d.config.budget_limit;
    if (d.config?.skill) config.skill = d.config.skill;
    if (Object.keys(config).length > 0) entry.config = config;

    // CAO adapter config block
    if (d.nodeType === 'cao') {
      const cao: Record<string, unknown> = {};
      if (d.config?.provider) cao.provider = d.config.provider;
      if (d.config?.mode && d.config.mode !== 'handoff') cao.mode = d.config.mode;
      if (d.config?.output_format && d.config.output_format !== 'auto') cao.output_format = d.config.output_format;
      if (d.config?.output_field) cao.output_field = d.config.output_field;
      if (d.config?.timeout_minutes && d.config.timeout_minutes !== 30) cao.timeout_minutes = d.config.timeout_minutes;
      if (Object.keys(cao).length > 0) entry.cao = cao;
    }

    // Tools
    if (d.tools?.length) entry.tools = d.tools;

    if (deps[node.id]?.length) {
      const depLabels = deps[node.id].map((depId) => {
        const depNode = nodes.find((n) => n.id === depId);
        return depNode?.data?.label || depId;
      });
      entry.depends_on = depLabels;

      // Generate inputs dict from dependencies
      const inputs: Record<string, string> = {};
      for (const dep of depLabels) {
        inputs[dep] = `\${${dep}.output}`;
      }
      entry.inputs = inputs;
    } else {
      // Root nodes get user input
      entry.inputs = { query: '${user.query}' };
    }

    const nodeLabel = d.label ?? node.id;
    nodesObj[nodeLabel] = entry;
  }

  const doc: Record<string, unknown> = { name: workflowName };
  if (options?.schedule) doc.schedule = options.schedule;
  if (options?.mcpServers && Object.keys(options.mcpServers).length > 0) {
    doc.mcp_servers = options.mcpServers;
  }
  doc.nodes = nodesObj;

  return yaml.dump(doc, { indent: 2, lineWidth: 120, noRefs: true });
}
