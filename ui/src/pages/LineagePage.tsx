import { useCallback, useEffect, useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  Handle,
  Position,
  type NodeProps,
} from 'reactflow';
import 'reactflow/dist/style.css';
import ELK, { type ElkNode } from 'elkjs/lib/elk.bundled.js';
import { useLineage } from '../hooks/useAnalysis';
import type { LineageNode as LineageNodeData } from '../hooks/useAnalysis';

const elk = new ELK();

// Custom node for artifact display
interface ArtifactNodeData extends LineageNodeData {
  label: string;
}

function ArtifactNode({ data }: NodeProps<ArtifactNodeData>) {
  const typeColors: Record<string, string> = {
    text: 'border-blue-500',
    code: 'border-purple-500',
    json: 'border-green-500',
    decision: 'border-yellow-500',
    error: 'border-red-500',
  };

  const border = typeColors[data.type] || 'border-slate-500';
  const contentPreview =
    typeof data.content === 'string'
      ? data.content.slice(0, 50)
      : JSON.stringify(data.content).slice(0, 50);

  return (
    <div
      className={`bg-slate-800 rounded-lg border-2 ${border} px-3 py-2 shadow-md min-w-[180px] max-w-[240px]`}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-500" />
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] uppercase tracking-wider text-slate-500 bg-slate-700 px-1.5 py-0.5 rounded">
          {data.type}
        </span>
      </div>
      <p className="text-xs font-mono text-slate-300 truncate" title={data.id}>
        {data.id}
      </p>
      <p
        className="text-[11px] text-slate-500 mt-1 truncate"
        title={typeof data.content === 'string' ? data.content : ''}
      >
        {contentPreview}
        {(typeof data.content === 'string' ? data.content : JSON.stringify(data.content)).length > 50 && '...'}
      </p>
      <p className="text-[10px] text-slate-600 mt-1">
        by: {data.produced_by}
      </p>
      <Handle type="source" position={Position.Bottom} className="!bg-slate-500" />
    </div>
  );
}

const nodeTypes = { artifact: ArtifactNode };

async function layoutLineageGraph(
  nodes: LineageNodeData[],
  edges: { source: string; target: string }[],
): Promise<{ nodes: Node[]; edges: Edge[] }> {
  if (nodes.length === 0) return { nodes: [], edges: [] };

  const elkGraph: ElkNode = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.spacing.nodeNode': '40',
      'elk.layered.spacing.nodeNodeBetweenLayers': '60',
    },
    children: nodes.map((n) => ({ id: n.id, width: 200, height: 70 })),
    edges: edges.map((e, i) => ({
      id: `e-${i}`,
      sources: [e.source],
      targets: [e.target],
    })),
  };

  const layout = await elk.layout(elkGraph);

  const rfNodes: Node[] = (layout.children || []).map((child) => {
    const nodeData = nodes.find((n) => n.id === child.id)!;
    return {
      id: child.id,
      type: 'artifact',
      position: { x: child.x || 0, y: child.y || 0 },
      data: { ...nodeData, label: nodeData.id },
    };
  });

  const rfEdges: Edge[] = edges.map((e, i) => ({
    id: `edge-${i}`,
    source: e.source,
    target: e.target,
    animated: true,
    style: { stroke: '#475569' },
  }));

  return { nodes: rfNodes, edges: rfEdges };
}

export default function LineagePage() {
  const { runId } = useParams<{ runId: string }>();
  const { data, isLoading, error } = useLineage(runId);
  const [rfNodes, setRfNodes] = useState<Node[]>([]);
  const [rfEdges, setRfEdges] = useState<Edge[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<LineageNodeData | null>(null);

  useEffect(() => {
    if (!data || data.nodes.length === 0) {
      setRfNodes([]);
      setRfEdges([]);
      return;
    }
    layoutLineageGraph(data.nodes, data.edges).then((layout) => {
      setRfNodes(layout.nodes);
      setRfEdges(layout.edges);
    });
  }, [data]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const artifact = data?.nodes.find((n) => n.id === node.id) ?? null;
      setSelectedArtifact((prev) =>
        prev?.id === artifact?.id ? null : artifact,
      );
    },
    [data?.nodes],
  );

  const stats = useMemo(() => {
    if (!data) return null;
    const types = new Map<string, number>();
    for (const n of data.nodes) {
      types.set(n.type, (types.get(n.type) ?? 0) + 1);
    }
    return { total: data.nodes.length, edgeCount: data.edges.length, types };
  }, [data]);

  if (!runId) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        Select a run first to view artifact lineage.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="h-96 bg-slate-800 rounded animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">
          Failed to load lineage: {(error as Error).message}
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 flex flex-col gap-4 h-full">
      {/* Breadcrumb */}
      <div className="text-sm text-slate-500">
        <Link to="/" className="hover:text-slate-300">
          Dashboard
        </Link>{' '}
        /{' '}
        <Link to={`/runs/${runId}`} className="hover:text-slate-300">
          {runId?.slice(0, 8)}...
        </Link>{' '}
        / <span className="text-slate-200">Lineage</span>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Artifact Lineage</h1>
          {stats && (
            <p className="text-sm text-slate-400 mt-0.5">
              {stats.total} artifacts, {stats.edgeCount} edges
              {stats.types.size > 0 && (
                <span className="ml-2">
                  ({[...stats.types.entries()]
                    .map(([t, c]) => `${c} ${t}`)
                    .join(', ')})
                </span>
              )}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <Link
            to={`/runs/${runId}/debug`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Debug
          </Link>
          <Link
            to={`/runs/${runId}/trace`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Trace
          </Link>
        </div>
      </div>

      {/* Graph + Detail */}
      <div className="flex gap-4 flex-1 min-h-0">
        <div className="flex-1 border border-slate-700 rounded-lg bg-slate-800/50 overflow-hidden">
          {data && data.nodes.length > 0 ? (
            <div className="w-full h-full min-h-[400px]">
              <ReactFlow
                nodes={rfNodes}
                edges={rfEdges}
                nodeTypes={nodeTypes}
                onNodeClick={handleNodeClick}
                fitView
                proOptions={{ hideAttribution: true }}
              >
                <Background color="#334155" gap={20} />
                <Controls />
                <MiniMap
                  nodeColor={() => '#475569'}
                  style={{ background: '#0f172a' }}
                />
              </ReactFlow>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm min-h-[400px]">
              No artifacts found for this run.
            </div>
          )}
        </div>

        {/* Selected artifact detail panel */}
        {selectedArtifact && (
          <div className="w-80 border border-slate-700 rounded-lg bg-slate-800/50 overflow-y-auto p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-sm">Artifact Detail</h3>
              <button
                onClick={() => setSelectedArtifact(null)}
                className="text-slate-400 hover:text-slate-200 text-lg leading-none"
                aria-label="Close panel"
              >
                x
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div>
                <span className="text-slate-500 text-xs">ID</span>
                <p className="font-mono text-xs mt-0.5 break-all">
                  {selectedArtifact.id}
                </p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Type</span>
                <p className="mt-0.5">{selectedArtifact.type}</p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Produced by</span>
                <p className="font-mono text-xs mt-0.5">
                  {selectedArtifact.produced_by}
                </p>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Content</span>
                <pre className="mt-1 bg-slate-900 border border-slate-700 rounded p-2 text-xs text-slate-300 whitespace-pre-wrap break-words max-h-80 overflow-y-auto">
                  {typeof selectedArtifact.content === 'string'
                    ? selectedArtifact.content
                    : JSON.stringify(selectedArtifact.content, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
