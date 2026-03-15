import { useCallback } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  useReactFlow,
  addEdge,
  Background,
  Controls,
  type Connection,
  type Node,
  type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { EditableNode } from './EditableNode';
import { NodePalette, type NodeTypeConfig } from './NodePalette';

const rfNodeTypes = { editable: EditableNode };

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
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
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

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      onNodesChange={onRfNodesChange}
      onEdgesChange={onRfEdgesChange}
      onConnect={onConnect}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onNodesDelete={onNodesDelete}
      onEdgesDelete={onEdgesDelete}
      nodeTypes={rfNodeTypes}
      fitView
      deleteKeyCode="Delete"
      className="bg-slate-950"
    >
      <Background color="#334155" gap={20} />
      <Controls className="!bg-slate-800 !border-slate-700 !shadow-lg" />
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
