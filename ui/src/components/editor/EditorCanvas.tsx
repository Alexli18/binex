import { useCallback, useState } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  useReactFlow,
  addEdge,
  Background,
  Controls,
  type Connection,
  type Node,
  type Edge,
  type NodeDragHandler,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { toast } from 'sonner';
import { EditableNode } from './EditableNode';
import { LoopContainerNode } from './LoopContainerNode';
import { LoopConfigModal } from './LoopConfigModal';
import { NodePalette, type NodeTypeConfig } from './NodePalette';
import type { LoopContainerData } from '@/lib/loop-types';
import { findParentLoop, getAbsolutePosition } from '@/lib/loop-utils';

const rfNodeTypes = {
  editable: EditableNode,
  loopContainer: LoopContainerNode,
};

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
  const { screenToFlowPosition, getNodes } = useReactFlow();
  const [pendingLoopConfig, setPendingLoopConfig] = useState<string | null>(null);

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
      const id = `${ntConfig.type === 'loopContainer' ? 'loop' : ntConfig.type}_${nodeIdCounter}`;

      if (ntConfig.type === 'loopContainer') {
        // Check if dropped inside another loop — nested loops forbidden
        const loopNodes = getNodes().filter((n) => n.type === 'loopContainer');
        const parentLoop = findParentLoop(position, loopNodes);
        if (parentLoop) {
          toast.error('Nested loops are not supported');
          return;
        }

        // Create loop container node
        const newNode: Node = {
          id,
          type: 'loopContainer',
          position,
          style: { width: 450, height: 250 },
          data: {
            label: id,
            exitCondition: null,
            maxIterations: 5,
          } as LoopContainerData,
        };
        setRfNodes((nds) => [...nds, newNode]);
        // Open mandatory config modal
        setPendingLoopConfig(id);
        return;
      }

      // Regular node — check if dropped inside a loop
      const loopNodes = getNodes().filter((n) => n.type === 'loopContainer');
      const parentLoop = findParentLoop(position, loopNodes);

      // Warning for human-approve inside loop
      if (parentLoop && ntConfig.type === 'human-approve') {
        toast.warning(
          'Human approval inside a loop will pause every iteration.',
          { duration: 5000 },
        );
      }

      const newNode: Node = {
        id,
        type: 'editable',
        position: parentLoop
          ? (() => {
              const loop = loopNodes.find((n) => n.id === parentLoop)!;
              return {
                x: position.x - loop.position.x,
                y: position.y - loop.position.y,
              };
            })()
          : position,
        data: {
          label: id,
          nodeType: ntConfig.type,
          agent: ntConfig.defaultAgent,
          config: {},
          color: ntConfig.color,
        },
        ...(parentLoop
          ? { parentNode: parentLoop, extent: 'parent' as const }
          : {}),
      };
      setRfNodes((nds) => [...nds, newNode]);
      setTimeout(onGraphChange, 0);
    },
    [screenToFlowPosition, setRfNodes, getNodes, onGraphChange],
  );

  // Handle node drag stop — detect if node was dragged into/out of a loop
  const onNodeDragStop: NodeDragHandler = useCallback(
    (_event, draggedNode) => {
      if (draggedNode.type === 'loopContainer') return;

      const allNodes = getNodes();
      const loopNodes = allNodes.filter(
        (n) => n.type === 'loopContainer' && n.id !== draggedNode.id,
      );
      const absPos = getAbsolutePosition(draggedNode, allNodes);
      const newParent = findParentLoop(absPos, loopNodes);
      const currentParent = draggedNode.parentNode || null;

      if (newParent === currentParent) return;

      // Prevent nesting loop inside loop
      if (draggedNode.type === 'loopContainer' && newParent) {
        toast.error('Nested loops are not supported');
        return;
      }

      // Warning for human-approve into loop
      if (newParent && draggedNode.data?.nodeType === 'human-approve') {
        toast.warning(
          'Human approval inside a loop will pause every iteration.',
          { duration: 5000 },
        );
      }

      setRfNodes((nds) =>
        nds.map((n) => {
          if (n.id !== draggedNode.id) return n;

          if (newParent) {
            const loop = loopNodes.find((l) => l.id === newParent)!;
            return {
              ...n,
              position: {
                x: absPos.x - loop.position.x,
                y: absPos.y - loop.position.y,
              },
              parentNode: newParent,
              extent: 'parent' as const,
            };
          } else {
            // Drag out of loop
            const updated = { ...n, position: absPos };
            delete updated.parentNode;
            delete updated.extent;
            return updated;
          }
        }),
      );
      setTimeout(onGraphChange, 0);
    },
    [getNodes, setRfNodes, onGraphChange],
  );

  const onNodesDelete = useCallback(() => {
    setTimeout(onGraphChange, 0);
  }, [onGraphChange]);

  const onEdgesDelete = useCallback(() => {
    setTimeout(onGraphChange, 0);
  }, [onGraphChange]);

  return (
    <>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onRfNodesChange}
        onEdgesChange={onRfEdgesChange}
        onConnect={onConnect}
        onDragOver={onDragOver}
        onDrop={onDrop}
        onNodeDragStop={onNodeDragStop}
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

      {/* Mandatory config modal for new loop */}
      {pendingLoopConfig && (
        <LoopConfigModal
          open
          mode="create"
          onClose={() => {
            // Cancel: remove the pending loop node
            setRfNodes((nds) => nds.filter((n) => n.id !== pendingLoopConfig));
            setPendingLoopConfig(null);
          }}
          onSave={(config) => {
            setRfNodes((nds) =>
              nds.map((n) =>
                n.id === pendingLoopConfig ? { ...n, data: config } : n,
              ),
            );
            setPendingLoopConfig(null);
            onGraphChange();
          }}
        />
      )}
    </>
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
