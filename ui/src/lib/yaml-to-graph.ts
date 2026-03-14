import yaml from 'js-yaml';
import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js';

export interface WorkflowNode {
  id: string;
  label: string;
  type: string;
  status?: string;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
}

export interface GraphLayout {
  nodes: Array<{ id: string; position: { x: number; y: number }; data: WorkflowNode }>;
  edges: WorkflowEdge[];
}

interface ParsedWorkflow {
  name?: string;
  nodes?: Record<string, { agent: string; depends_on?: string[] }>;
}

const elk = new ELK();

export function parseWorkflowYaml(yamlContent: string): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  const parsed = yaml.load(yamlContent) as ParsedWorkflow;
  if (!parsed?.nodes) return { nodes: [], edges: [] };

  const nodes: WorkflowNode[] = Object.entries(parsed.nodes).map(([id, spec]) => {
    const agent = spec.agent || '';
    const type = agent.split('://')[0] || 'local';
    return { id, label: id, type };
  });

  const edges: WorkflowEdge[] = [];
  for (const [id, spec] of Object.entries(parsed.nodes)) {
    if (spec.depends_on) {
      for (const dep of spec.depends_on) {
        edges.push({ id: `${dep}->${id}`, source: dep, target: id });
      }
    }
  }

  return { nodes, edges };
}

export async function layoutGraph(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
): Promise<GraphLayout> {
  const elkGraph: ElkNode = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.spacing.nodeNode': '50',
      'elk.layered.spacing.nodeNodeBetweenLayers': '80',
    },
    children: nodes.map((n) => ({ id: n.id, width: 180, height: 50 })),
    edges: edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  };

  const layout = await elk.layout(elkGraph);

  const layoutNodes = (layout.children || []).map((child) => {
    const nodeData = nodes.find((n) => n.id === child.id)!;
    return {
      id: child.id,
      position: { x: child.x || 0, y: child.y || 0 },
      data: nodeData,
    };
  });

  return { nodes: layoutNodes, edges };
}
