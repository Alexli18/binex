import { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  type Edge,
  type Node,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { layoutGraph, type WorkflowEdge, type WorkflowNode } from '../../lib/yaml-to-graph';
import { CustomNode } from './CustomNode';

const nodeTypes = { custom: CustomNode };

interface WorkflowGraphProps {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  onNodeClick?: (nodeId: string) => void;
}

export function WorkflowGraph({ nodes, edges, onNodeClick }: WorkflowGraphProps) {
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);

  useEffect(() => {
    if (nodes.length === 0) return;
    layoutGraph(nodes, edges).then((layout) => {
      setRfNodes(
        layout.nodes.map((n) => ({
          id: n.id,
          type: 'custom',
          position: n.position,
          data: n.data,
        })),
      );
      setRfEdges(
        layout.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          animated: nodes.find((n) => n.id === e.source)?.status === 'running',
          style: { stroke: '#64748b', strokeWidth: 2 },
        })),
      );
    });
  }, [nodes, edges]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node.id);
    },
    [onNodeClick],
  );

  return (
    <div className="w-full h-full min-h-[400px] bg-slate-900 rounded-lg">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#334155" gap={16} />
        <Controls className="!bg-slate-800 !border-slate-700 !shadow-lg [&>button]:!bg-slate-700 [&>button]:!border-slate-600 [&>button]:!text-slate-300 [&>button:hover]:!bg-slate-600" />
      </ReactFlow>
    </div>
  );
}
