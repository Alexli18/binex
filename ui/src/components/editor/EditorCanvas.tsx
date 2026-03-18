import { useCallback, useState, useEffect, useRef } from 'react';
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
import { NodePalette, type NodeTypeConfig, NODE_TYPES } from './NodePalette';
import type { LoopContainerData } from '@/lib/loop-types';
import {
  findParentLoop,
  getAbsolutePosition,
  getNextFreePosition,
  calculateLoopSize,
} from '@/lib/loop-utils';

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
  isVisible?: boolean;
}

function InnerCanvas({
  rfNodes,
  rfEdges,
  setRfNodes,
  setRfEdges,
  onRfNodesChange,
  onRfEdgesChange,
  onGraphChange,
  isVisible,
}: EditorCanvasProps) {
  const { screenToFlowPosition, getNodes, fitView } = useReactFlow();
  const [pendingLoopConfig, setPendingLoopConfig] = useState<string | null>(null);

  const dragOverRef = useRef<string | null>(null);
  const prevVisibleRef = useRef(isVisible);

  // Re-fit view when becoming visible (YAML → Visual switch)
  // React Flow needs a frame to measure node dimensions after display:none → flex
  useEffect(() => {
    if (isVisible && !prevVisibleRef.current) {
      requestAnimationFrame(() => {
        fitView({ duration: 200 });
      });
    }
    prevVisibleRef.current = isVisible;
  }, [isVisible, fitView]);

  // Handle "+" button event from LoopContainerNode
  useEffect(() => {
    const handler = (e: Event) => {
      const { loopId } = (e as CustomEvent<{ loopId: string }>).detail;
      const allNodes = getNodes();
      const loop = allNodes.find((n) => n.id === loopId);
      if (!loop) return;
      const children = allNodes.filter((n) => n.parentNode === loopId);
      const pos = getNextFreePosition(loop, children);
      nodeIdCounter += 1;
      const id = `llm_${nodeIdCounter}`;
      const defaultLlm = NODE_TYPES.find((t) => t.type === 'llm')!;
      const newNode: Node = {
        id,
        type: 'editable',
        position: pos,
        parentNode: loopId,
        extent: 'parent' as const,
        data: {
          label: id,
          nodeType: 'llm',
          agent: defaultLlm.defaultAgent,
          config: {},
          color: defaultLlm.color,
        },
      };
      setRfNodes((nds) => {
        const updated = [...nds, newNode];
        const loopChildren = updated.filter((n) => n.parentNode === loopId);
        const newSize = calculateLoopSize(loopChildren);
        return updated.map((n) =>
          n.id === loopId
            ? { ...n, style: { ...n.style, width: newSize.width, height: newSize.height } }
            : n,
        );
      });
      onGraphChange();
    };
    window.addEventListener('binex:loop-add-node', handler);
    return () => window.removeEventListener('binex:loop-add-node', handler);
  }, [getNodes, setRfNodes, onGraphChange]);

  const onConnect = useCallback(
    (connection: Connection) => {
      setRfEdges((eds) => addEdge(connection, eds));
      setTimeout(onGraphChange, 0);
    },
    [setRfEdges, onGraphChange],
  );

  const onDragOver = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      const pos = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      const loopNodes = getNodes().filter((n) => n.type === 'loopContainer');
      const overLoop = findParentLoop(pos, loopNodes);
      if (overLoop !== dragOverRef.current) {
        dragOverRef.current = overLoop;
        // Update loop node data for highlight
        setRfNodes((nds) =>
          nds.map((n) =>
            n.type === 'loopContainer'
              ? { ...n, data: { ...n.data, isDragOver: n.id === overLoop } }
              : n,
          ),
        );
      }
    },
    [screenToFlowPosition, getNodes, setRfNodes],
  );

  const onDragLeave = useCallback(
    (event: React.DragEvent) => {
      // Only clear when leaving the canvas entirely
      if (event.currentTarget.contains(event.relatedTarget as Element)) return;
      dragOverRef.current = null;
      setRfNodes((nds) =>
        nds.map((n) =>
          n.type === 'loopContainer' && n.data?.isDragOver
            ? { ...n, data: { ...n.data, isDragOver: false } }
            : n,
        ),
      );
    },
    [setRfNodes],
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      // Clear drag highlight
      dragOverRef.current = null;
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

      const loop = parentLoop ? loopNodes.find((n) => n.id === parentLoop)! : null;
      const existingChildren = parentLoop
        ? getNodes().filter((n) => n.parentNode === parentLoop)
        : [];
      const nodePosition = loop
        ? getNextFreePosition(loop, existingChildren)
        : position;

      const newNode: Node = {
        id,
        type: 'editable',
        position: nodePosition,
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
      setRfNodes((nds) => {
        const updated = [...nds, newNode];
        if (!parentLoop) return updated;
        // Auto-resize loop container
        const loopChildren = updated.filter((n) => n.parentNode === parentLoop);
        const newSize = calculateLoopSize(loopChildren);
        return updated.map((n) =>
          n.id === parentLoop
            ? { ...n, style: { ...n.style, width: newSize.width, height: newSize.height } }
            : n,
        );
      });
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

      setRfNodes((nds) => {
        const moved = nds.map((n) => {
          if (n.id !== draggedNode.id) return n;

          if (newParent) {
            const loop = loopNodes.find((l) => l.id === newParent)!;
            const existingChildren = nds.filter(
              (c) => c.parentNode === newParent && c.id !== draggedNode.id,
            );
            const pos = getNextFreePosition(loop, existingChildren);
            return {
              ...n,
              position: pos,
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
        });

        // Auto-resize affected loops
        const affectedLoops = new Set<string>();
        if (newParent) affectedLoops.add(newParent);
        if (currentParent) affectedLoops.add(currentParent);

        return moved.map((n) => {
          if (!affectedLoops.has(n.id)) return n;
          const children = moved.filter((c) => c.parentNode === n.id);
          const newSize = calculateLoopSize(children);
          return { ...n, style: { ...n.style, width: newSize.width, height: newSize.height } };
        });
      });
      setTimeout(onGraphChange, 0);
    },
    [getNodes, setRfNodes, onGraphChange],
  );

  const onNodesDelete = useCallback(
    (deleted: Node[]) => {
      // Auto-resize loops that lost children
      const affectedLoops = new Set<string>();
      for (const d of deleted) {
        if (d.parentNode) affectedLoops.add(d.parentNode);
      }
      if (affectedLoops.size > 0) {
        setRfNodes((nds) =>
          nds.map((n) => {
            if (!affectedLoops.has(n.id)) return n;
            const children = nds.filter(
              (c) => c.parentNode === n.id && !deleted.some((d) => d.id === c.id),
            );
            const newSize = calculateLoopSize(children);
            return { ...n, style: { ...n.style, width: newSize.width, height: newSize.height } };
          }),
        );
      }
      setTimeout(onGraphChange, 0);
    },
    [onGraphChange, setRfNodes],
  );

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
        onDragLeave={onDragLeave}
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
