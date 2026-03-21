import { useCallback, useMemo, useState } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  useReactFlow,
  addEdge,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  MarkerType,
  type Connection,
  type Node,
  type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { MousePointerClick } from 'lucide-react';
import { EditableNode } from './EditableNode';
import { NodePalette, type NodeTypeConfig } from './NodePalette';

const rfNodeTypes = { editable: EditableNode };

const defaultEdgeOptions = {
  type: 'smoothstep',
  style: { stroke: '#475569', strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#475569' },
};

const connectionLineStyle = { stroke: '#3b82f6', strokeWidth: 2, strokeDasharray: '6 3' };

let nodeIdCounter = 0;

export interface EditorCanvasProps {
  rfNodes: Node[];
  rfEdges: Edge[];
  setRfNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setRfEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  onRfNodesChange: Parameters<typeof ReactFlow>[0]['onNodesChange'];
  onRfEdgesChange: Parameters<typeof ReactFlow>[0]['onEdgesChange'];
  onGraphChange: () => void;
}

function InnerCanvas({
  rfNodes,
  rfEdges,
  setRfNodes,
  setRfEdges,
  onRfNodesChange,
  onRfEdgesChange,
  onGraphChange,
}: EditorCanvasProps) {
  const { screenToFlowPosition } = useReactFlow();
  const [isDragOver, setIsDragOver] = useState(false);

  const onConnect = useCallback(
    (connection: Connection) => {
      setRfEdges((eds) => addEdge(connection, eds));
      setTimeout(onGraphChange, 0);
    },
    [setRfEdges, onGraphChange],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    setIsDragOver(true);
  }, []);

  const onDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setIsDragOver(false);
      const raw = event.dataTransfer.getData('application/reactflow');
      if (!raw) return;
      const ntConfig: NodeTypeConfig = JSON.parse(raw);
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      nodeIdCounter += 1;
      const id = `${ntConfig.type}_${nodeIdCounter}`;
      const newNode: Node = {
        id,
        type: 'editable',
        position,
        data: {
          label: id,
          nodeType: ntConfig.type,
          agent: ntConfig.defaultAgent,
          config: {},
          color: ntConfig.color,
        },
      };
      setRfNodes((nds) => [...nds, newNode]);
      setTimeout(onGraphChange, 0);
    },
    [screenToFlowPosition, setRfNodes, onGraphChange],
  );

  const onNodesDelete = useCallback(() => {
    setTimeout(onGraphChange, 0);
  }, [onGraphChange]);

  const onEdgesDelete = useCallback(() => {
    setTimeout(onGraphChange, 0);
  }, [onGraphChange]);

  const isEmpty = useMemo(() => rfNodes.length === 0, [rfNodes.length]);

  const selectedNodeIds = useMemo(
    () => new Set(rfNodes.filter((n) => n.selected).map((n) => n.id)),
    [rfNodes],
  );

  const styledEdges = useMemo(() => {
    if (selectedNodeIds.size === 0) return rfEdges;
    return rfEdges.map((edge) => {
      const connected = selectedNodeIds.has(edge.source) || selectedNodeIds.has(edge.target);
      if (!connected) return { ...edge, style: { ...edge.style, stroke: '#334155', strokeWidth: 1.5, opacity: 0.4 } };
      return { ...edge, style: { ...edge.style, stroke: '#3b82f6', strokeWidth: 2.5 }, markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16, color: '#3b82f6' }, animated: true };
    });
  }, [rfEdges, selectedNodeIds]);

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={styledEdges}
      onNodesChange={onRfNodesChange}
      onEdgesChange={onRfEdgesChange}
      onConnect={onConnect}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onNodesDelete={onNodesDelete}
      onEdgesDelete={onEdgesDelete}
      nodeTypes={rfNodeTypes}
      defaultEdgeOptions={defaultEdgeOptions}
      connectionLineStyle={connectionLineStyle}
      fitView
      deleteKeyCode="Delete"
      className={`bg-slate-950 transition-all duration-150 ${isDragOver ? 'ring-2 ring-inset ring-blue-500/30' : ''}`}
    >
      <Background variant={BackgroundVariant.Dots} color={isDragOver ? '#3b82f640' : '#334155'} gap={24} size={1.5} />
      <Controls className="!bg-slate-800 !border-slate-700 !shadow-lg" />
      <MiniMap
        nodeColor={(node) => node.data?.color || '#475569'}
        maskColor="rgba(2, 6, 23, 0.7)"
        className="!bg-slate-900 !border-slate-700/60"
        style={{ width: 120, height: 80 }}
      />
      {isEmpty && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
          <div className="text-center space-y-3">
            <MousePointerClick size={40} className="text-slate-600 mx-auto" />
            <p className="text-sm text-slate-500">Drag a node from the sidebar to get started</p>
            <p className="text-xs text-slate-600">or open a workflow YAML file</p>
          </div>
        </div>
      )}
    </ReactFlow>
  );
}

export function EditorCanvas(props: EditorCanvasProps) {
  return (
    <div className="flex flex-1 min-w-0">
      <NodePalette />
      <div className="flex-1 min-w-0">
        <ReactFlowProvider>
          <InnerCanvas {...props} />
        </ReactFlowProvider>
      </div>
    </div>
  );
}
