import { memo, useState, useCallback } from 'react';
import { Handle, Position, useReactFlow, type NodeProps } from 'reactflow';
import { RefreshCw, Settings, Trash2, AlertTriangle, Plus } from 'lucide-react';
import type { LoopContainerData } from '@/lib/loop-types';
import { LoopFooterBadge } from './LoopFooterBadge';
import { LoopRuntimeBadge } from './LoopRuntimeBadge';
import { LoopConfigModal } from './LoopConfigModal';
import { cn } from '@/lib/utils';

const LOOP_COLOR = '#14b8a6'; // teal-500

function LoopContainerNodeInner({ data, id }: NodeProps<LoopContainerData>) {
  const { deleteElements, getNodes } = useReactFlow();
  const [configOpen, setConfigOpen] = useState(false);

  const childNodes = getNodes().filter((n) => n.parentNode === id);
  const hasNestedLoop = childNodes.some((n) => n.type === 'loopContainer');
  const hasHumanApproval = childNodes.some(
    (n) => n.data?.nodeType === 'human-approve',
  );

  const handleDelete = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      const children = getNodes().filter((n) => n.parentNode === id);
      deleteElements({
        nodes: [{ id }, ...children.map((c) => ({ id: c.id }))],
      });
    },
    [deleteElements, getNodes, id],
  );

  const notifyChange = useCallback(() => {
    window.dispatchEvent(new CustomEvent('binex:node-data-change'));
  }, []);

  const updateLabel = useCallback(
    (val: string) => {
      data.label = val;
      notifyChange();
    },
    [data, notifyChange],
  );

  const handleConfigSave = useCallback(
    (config: LoopContainerData) => {
      data.label = config.label;
      data.exitCondition = config.exitCondition;
      data.maxIterations = config.maxIterations;
      setConfigOpen(false);
      notifyChange();
    },
    [data, notifyChange],
  );

  const hasCondition =
    data.exitCondition &&
    data.exitCondition.field.trim() &&
    String(data.exitCondition.value).trim();

  return (
    <div
      className={cn(
        'rounded-xl border-2 border-dashed',
        'bg-slate-900/50',
        'shadow-lg shadow-black/10',
        'min-w-[400px] min-h-[200px]',
        'relative',
      )}
      style={{
        borderColor: data.isDragOver ? '#2dd4bf' : hasCondition ? LOOP_COLOR : '#ef4444',
        ...(data.isDragOver && {
          boxShadow: '0 0 20px rgba(20, 184, 166, 0.3)',
        }),
        transition: 'box-shadow 0.2s, border-color 0.2s',
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-teal-500 !border-teal-400"
      />

      {/* Header */}
      <div
        className={cn(
          'flex items-center justify-between',
          'px-3 py-2',
          'bg-slate-800/60 rounded-t-xl',
          'border-b border-dashed border-teal-500/30',
        )}
      >
        <div className="flex items-center gap-2">
          <RefreshCw size={14} className="text-teal-400" />
          <input
            value={data.label}
            onChange={(e) => updateLabel(e.target.value)}
            className="nodrag nowheel bg-transparent text-sm font-medium text-teal-300 border-none outline-none w-40"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setConfigOpen(true);
            }}
            className="nodrag p-1 text-slate-400 hover:text-teal-300 transition-colors"
            title="Loop settings"
          >
            <Settings size={13} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              window.dispatchEvent(
                new CustomEvent('binex:loop-add-node', { detail: { loopId: id } }),
              );
            }}
            className="nodrag p-1 text-slate-400 hover:text-teal-300 transition-colors"
            title="Add node to loop"
          >
            <Plus size={13} />
          </button>
          <button
            onClick={handleDelete}
            className="nodrag p-1 text-red-500 hover:text-red-400 transition-colors"
            title="Delete loop"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Content area — child nodes are rendered here by React Flow */}
      <div style={{ minHeight: 100, padding: '10px 20px 50px 20px' }}>
        {childNodes.length === 0 && (
          <div className="flex flex-col items-center justify-center h-[120px] gap-2">
            <div className="w-16 h-16 rounded-lg border-2 border-dashed border-teal-500/30 flex items-center justify-center">
              <Plus size={24} className="text-teal-500/40" />
            </div>
            <span className="text-slate-500 text-xs">Drop nodes here to add to loop</span>
          </div>
        )}
      </div>

      {/* Warnings */}
      {(hasNestedLoop || hasHumanApproval) && (
        <div className="absolute bottom-[50px] left-3 right-3 flex flex-col gap-0.5">
          {hasNestedLoop && (
            <div className="flex items-center gap-1 text-[10px] text-red-400">
              <AlertTriangle size={10} />
              <span>Nested loops are not supported</span>
            </div>
          )}
          {hasHumanApproval && (
            <div className="flex items-center gap-1 text-[10px] text-amber-400">
              <AlertTriangle size={10} />
              <span>Human approval inside loop may block iterations</span>
            </div>
          )}
        </div>
      )}

      {/* Footer badge */}
      <div className="absolute bottom-0 left-0 right-0">
        {data.runtime ? (
          <LoopRuntimeBadge
            currentIteration={data.runtime.currentIteration}
            maxIterations={data.maxIterations}
            exitCondition={data.exitCondition}
            currentValue={data.runtime.currentValue}
            totalCost={data.runtime.totalCost}
            status={data.runtime.status}
          />
        ) : (
          <LoopFooterBadge
            exitCondition={data.exitCondition}
            maxIterations={data.maxIterations}
            childCount={childNodes.length}
          />
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-teal-500 !border-teal-400"
      />

      {/* Config Modal */}
      {configOpen && (
        <LoopConfigModal
          open={configOpen}
          mode="edit"
          initialData={data}
          onClose={() => setConfigOpen(false)}
          onSave={handleConfigSave}
        />
      )}
    </div>
  );
}

export const LoopContainerNode = memo(LoopContainerNodeInner);
