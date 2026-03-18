import { useState } from 'react';
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { StatusBadge } from './common/StatusBadge';
import type { LoopData, LoopIteration } from '../hooks/useLoopIterations';
import { cn } from '@/lib/utils';

interface LoopIterationsPanelProps {
  loops: LoopData[];
}

function IterationRow({ iteration, isLast }: { iteration: LoopIteration; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const totalCost = iteration.nodes.reduce((sum, n) => sum + (n.cost ?? 0), 0);
  const totalLatency = iteration.nodes.reduce((sum, n) => sum + (n.latency_ms ?? 0), 0);

  return (
    <div className={cn('border-slate-700/50', !isLast && 'border-b')}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-slate-800/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={14} className="text-slate-500" />
        ) : (
          <ChevronRight size={14} className="text-slate-500" />
        )}
        <span className={cn(
          'font-medium',
          isLast ? 'text-teal-400' : 'text-slate-300',
        )}>
          Iteration {iteration.iteration}
          {isLast && <span className="ml-1.5 text-[10px] bg-teal-500/20 text-teal-400 px-1.5 py-0.5 rounded">final</span>}
        </span>
        <StatusBadge status={iteration.status} />
        <span className="flex-1" />
        <span className="text-xs text-slate-500">{iteration.nodes.length} nodes</span>
        <span className="text-xs text-slate-500">{totalLatency}ms</span>
        <span className="text-xs font-mono text-slate-500">${totalCost.toFixed(4)}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-2">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="pb-1 font-medium pr-4">Node</th>
                <th className="pb-1 font-medium pr-4">Status</th>
                <th className="pb-1 font-medium pr-4">Latency</th>
                <th className="pb-1 font-medium text-right">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {iteration.nodes.map((node) => (
                <tr key={node.node_id}>
                  <td className="py-1.5 font-mono text-slate-300 pr-4">{node.node_id}</td>
                  <td className="py-1.5 pr-4"><StatusBadge status={node.status} /></td>
                  <td className="py-1.5 text-slate-400 pr-4">{node.latency_ms ?? '-'}ms</td>
                  <td className="py-1.5 text-right font-mono text-slate-400">${(node.cost ?? 0).toFixed(6)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {iteration.nodes.some((n) => n.error) && (
            <div className="mt-2 space-y-1">
              {iteration.nodes.filter((n) => n.error).map((n) => (
                <div key={n.node_id} className="text-xs bg-red-900/20 border border-red-500/20 rounded p-2">
                  <span className="font-mono text-red-400">{n.node_id}:</span>{' '}
                  <span className="text-red-300">{n.error}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function LoopIterationsPanel({ loops }: LoopIterationsPanelProps) {
  const [expandedLoops, setExpandedLoops] = useState<Set<string>>(
    () => new Set(loops.map((l) => l.loop_node_id)),
  );

  const toggleLoop = (id: string) => {
    setExpandedLoops((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
      <h3 className="text-sm font-medium text-slate-200 mb-3 flex items-center gap-2">
        <RefreshCw size={14} className="text-teal-400" />
        Loop Iterations
      </h3>
      <div className="space-y-3">
        {loops.map((loop) => {
          const isExpanded = expandedLoops.has(loop.loop_node_id);
          const totalCost = loop.iterations.reduce(
            (sum, it) => sum + it.nodes.reduce((s, n) => s + (n.cost ?? 0), 0),
            0,
          );
          return (
            <div
              key={loop.loop_node_id}
              className="border border-dashed border-teal-500/30 rounded-lg overflow-hidden"
            >
              <button
                onClick={() => toggleLoop(loop.loop_node_id)}
                className="w-full flex items-center gap-2 px-3 py-2 bg-slate-800/60 hover:bg-slate-700/40 transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown size={14} className="text-teal-400" />
                ) : (
                  <ChevronRight size={14} className="text-teal-400" />
                )}
                <RefreshCw size={12} className="text-teal-400" />
                <span className="text-sm font-medium text-teal-300">{loop.loop_node_id}</span>
                <span className="flex-1" />
                <span className="text-xs text-slate-500">
                  {loop.total_iterations} iteration{loop.total_iterations !== 1 ? 's' : ''}
                </span>
                <span className="text-xs font-mono text-slate-500">${totalCost.toFixed(4)}</span>
              </button>
              {isExpanded && (
                <div>
                  {loop.iterations.map((it, idx) => (
                    <IterationRow
                      key={it.iteration}
                      iteration={it}
                      isLast={idx === loop.iterations.length - 1}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
