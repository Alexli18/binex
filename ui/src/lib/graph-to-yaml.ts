import yaml from 'js-yaml';
import type { Node, Edge } from 'reactflow';
import type { LoopContainerData } from './loop-types';

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

  // Separate loop containers from regular nodes
  const loopContainers = nodes.filter((n) => n.type === 'loopContainer');
  const regularNodes = nodes.filter((n) => n.type !== 'loopContainer');

  // Build set of child node IDs (those inside loops)
  const childNodeIds = new Set<string>();
  for (const n of regularNodes) {
    if (n.parentNode && loopContainers.some((l) => l.id === n.parentNode)) {
      childNodeIds.add(n.id);
    }
  }

  // Process ALL regular nodes (including loop children — they stay at top-level in backend format)
  for (const node of regularNodes) {
    nodesObj[node.data.label || node.id] = buildNodeEntry(node, nodes, deps);
  }

  // Process loop containers
  for (const loop of loopContainers) {
    const loopData = loop.data as LoopContainerData;
    const children = regularNodes.filter((n) => n.parentNode === loop.id);

    // Build loop spec (backend format: loop.exit.field + loop.contains)
    const loopSpec: Record<string, unknown> = {
      max_iterations: loopData.maxIterations || 5,
      accumulate: false,
      contains: children.map((c) => c.data.label || c.id),
    };

    if (loopData.exitCondition && loopData.exitCondition.field && loopData.exitCondition.value !== undefined) {
      loopSpec.exit = {
        field: loopData.exitCondition.field,
        operator: loopData.exitCondition.operator,
        value: loopData.exitCondition.value,
      };
    }

    if (loopData.entryNode) loopSpec.entry_node = loopData.entryNode;
    if (loopData.outputNode) loopSpec.output_node = loopData.outputNode;

    const loopEntry: Record<string, unknown> = {
      type: 'loop',
      loop: loopSpec,
    };

    // Loop-level dependencies
    if (deps[loop.id]?.length) {
      const depLabels = deps[loop.id].map((depId) => {
        const depNode = nodes.find((n) => n.id === depId);
        return depNode?.data?.label || depId;
      });
      loopEntry.depends_on = depLabels;
      const inputs: Record<string, string> = {};
      for (const dep of depLabels) {
        inputs[dep] = `\${${dep}.output}`;
      }
      loopEntry.inputs = inputs;
    }

    nodesObj[loopData.label || loop.id] = loopEntry;
  }

  const doc: Record<string, unknown> = { name: workflowName };
  if (options?.schedule) doc.schedule = options.schedule;
  if (options?.mcpServers && Object.keys(options.mcpServers).length > 0) {
    doc.mcp_servers = options.mcpServers;
  }
  doc.nodes = nodesObj;

  return yaml.dump(doc, { indent: 2, lineWidth: 120, noRefs: true });
}

function buildNodeEntry(
  node: Node,
  allNodes: Node[],
  deps: Record<string, string[]>,
): Record<string, unknown> {
  const d = node.data;
  const entry: Record<string, unknown> = {
    agent: d.agent || 'local://echo',
    outputs: ['output'],
  };

  const promptText = d.system_prompt || d.config?.system_prompt || d.config?.prompt_message;
  if (promptText) entry.system_prompt = promptText;

  const config: Record<string, unknown> = {};
  if (d.config?.max_tokens) config.max_tokens = d.config.max_tokens;
  if (d.config?.temperature != null) config.temperature = d.config.temperature;
  if (d.config?.budget_limit) config.budget_limit = d.config.budget_limit;
  if (d.config?.skill) config.skill = d.config.skill;
  if (Object.keys(config).length > 0) entry.config = config;

  if (d.tools?.length) entry.tools = d.tools;

  if (deps[node.id]?.length) {
    const depLabels = deps[node.id].map((depId) => {
      const depNode = allNodes.find((n) => n.id === depId);
      return depNode?.data?.label || depId;
    });
    entry.depends_on = depLabels;

    const inputs: Record<string, string> = {};
    for (const dep of depLabels) {
      inputs[dep] = `\${${dep}.output}`;
    }
    entry.inputs = inputs;
  } else {
    entry.inputs = { query: '${user.query}' };
  }

  return entry;
}
