import yaml from 'js-yaml';
import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js';

export interface WorkflowNode {
  id: string;
  label: string;
  type: string;
  status?: string;
  isLoop?: boolean;
  parentLoop?: string;
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

interface ParsedNodeSpec {
  agent?: string;
  type?: string;
  depends_on?: string[];
  nodes?: Record<string, ParsedNodeSpec>;
}

interface ParsedWorkflow {
  name?: string;
  nodes?: Record<string, ParsedNodeSpec>;
}

const elk = new ELK();

export function parseWorkflowYaml(yamlContent: string): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  const parsed = yaml.load(yamlContent) as ParsedWorkflow;
  if (!parsed?.nodes) return { nodes: [], edges: [] };

  const nodes: WorkflowNode[] = [];
  const edges: WorkflowEdge[] = [];

  for (const [id, spec] of Object.entries(parsed.nodes)) {
    if (spec.type === 'loop') {
      // Loop container node
      nodes.push({ id, label: id, type: 'loop', isLoop: true });

      if (spec.depends_on) {
        for (const dep of spec.depends_on) {
          edges.push({ id: `${dep}->${id}`, source: dep, target: id });
        }
      }

      // Child nodes inside loop
      if (spec.nodes) {
        for (const [childId, childSpec] of Object.entries(spec.nodes)) {
          const agent = childSpec.agent || '';
          const type = agent.split('://')[0] || 'local';
          nodes.push({ id: childId, label: childId, type, parentLoop: id });

          if (childSpec.depends_on) {
            for (const dep of childSpec.depends_on) {
              edges.push({ id: `${dep}->${childId}`, source: dep, target: childId });
            }
          }
        }
      }
    } else {
      // Regular node
      const agent = spec.agent || '';
      const type = agent.split('://')[0] || 'local';
      nodes.push({ id, label: id, type });

      if (spec.depends_on) {
        for (const dep of spec.depends_on) {
          edges.push({ id: `${dep}->${id}`, source: dep, target: id });
        }
      }
    }
  }

  return { nodes, edges };
}

export async function layoutGraph(
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
): Promise<GraphLayout> {
  const nodeIds = new Set(nodes.map((n) => n.id));
  // Filter edges to only include those whose source and target exist in nodes
  const validEdges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));

  // Separate loop containers and their children
  const childNodes = nodes.filter((n) => n.parentLoop);
  const topLevelNodes = nodes.filter((n) => !n.parentLoop);

  // Build ELK graph with compound nodes for loops
  const elkChildren: ElkNode[] = [];

  for (const n of topLevelNodes) {
    if (n.isLoop) {
      // Loop container with children
      const loopChildren = childNodes.filter((c) => c.parentLoop === n.id);
      elkChildren.push({
        id: n.id,
        width: 450,
        height: Math.max(250, loopChildren.length * 80 + 120),
        children: loopChildren.map((c) => ({ id: c.id, width: 180, height: 50 })),
        edges: validEdges
          .filter((e) => loopChildren.some((c) => c.id === e.source || c.id === e.target))
          .map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
        layoutOptions: {
          'elk.algorithm': 'layered',
          'elk.direction': 'DOWN',
          'elk.spacing.nodeNode': '30',
          'elk.padding': '[top=50,left=20,bottom=20,right=20]',
        },
      });
    } else {
      elkChildren.push({ id: n.id, width: 180, height: 50 });
    }
  }

  // Top-level edges (between top-level nodes, excluding internal loop edges)
  const topLevelEdges = validEdges.filter((e) => {
    const sTop = topLevelNodes.some((n) => n.id === e.source);
    const tTop = topLevelNodes.some((n) => n.id === e.target);
    return sTop && tTop;
  });

  const elkGraph: ElkNode = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.spacing.nodeNode': '50',
      'elk.layered.spacing.nodeNodeBetweenLayers': '80',
    },
    children: elkChildren,
    edges: topLevelEdges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  };

  const layout = await elk.layout(elkGraph).catch(() => elkGraph);

  const layoutNodes: GraphLayout['nodes'] = [];

  for (const child of layout.children || []) {
    const nodeData = nodes.find((n) => n.id === child.id)!;
    layoutNodes.push({
      id: child.id,
      position: { x: child.x || 0, y: child.y || 0 },
      data: nodeData,
    });

    // Process children of loop containers
    if (child.children) {
      for (const grandchild of child.children) {
        const childData = nodes.find((n) => n.id === grandchild.id)!;
        layoutNodes.push({
          id: grandchild.id,
          position: { x: (child.x || 0) + (grandchild.x || 0), y: (child.y || 0) + (grandchild.y || 0) },
          data: childData,
        });
      }
    }
  }

  return { nodes: layoutNodes, edges };
}
