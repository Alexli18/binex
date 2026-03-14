import { useEffect, useRef, useState } from 'react';
import { useCostEstimate } from '../hooks/useCostDashboard';
import type { NodeEstimate } from '../hooks/useCostDashboard';
import { DollarSign, AlertTriangle, Loader2, ChevronUp, ChevronDown } from 'lucide-react';

interface CostEstimatePanelProps {
  yamlContent: string;
}

const TYPE_COLORS: Record<string, string> = {
  llm: 'bg-blue-500',
  local: 'bg-green-500',
  human: 'bg-purple-500',
  a2a: 'bg-slate-500',
};

function getNodeTypeColor(type: string): string {
  return TYPE_COLORS[type] ?? 'bg-slate-500';
}

export function CostEstimatePanel({ yamlContent }: CostEstimatePanelProps) {
  const estimate = useCostEstimate();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastContentRef = useRef<string>('');
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!yamlContent.trim()) return;
    debounceRef.current = setTimeout(() => {
      if (yamlContent !== lastContentRef.current) {
        lastContentRef.current = yamlContent;
        estimate.mutate(yamlContent);
      }
    }, 1000);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [yamlContent]);

  const data = estimate.data;
  const total = data ? (data.total_estimate ?? 0) : 0;
  const nodeCount = data?.nodes.length ?? 0;
  const warningCount = data?.warnings.length ?? 0;

  const maxCost = data
    ? Math.max(...data.nodes.map((n) => n.estimated_cost ?? 0).filter((c) => c > 0), 0.0001)
    : 1;

  return (
    <div className="border-t border-slate-700 bg-slate-800">
      {/* Compact header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <DollarSign className="w-3.5 h-3.5 text-green-400" />
          <span className="text-xs font-medium text-slate-300">Cost</span>
          {estimate.isPending && <Loader2 className="w-3 h-3 text-slate-500 animate-spin" />}
          {data && (
            <span className="text-xs font-mono text-slate-100">${total.toFixed(4)}</span>
          )}
          {warningCount > 0 && (
            <span className="flex items-center gap-0.5 text-amber-400">
              <AlertTriangle className="w-3 h-3" />
              <span className="text-[10px]">{warningCount}</span>
            </span>
          )}
          {nodeCount > 0 && (
            <span className="text-[10px] text-slate-500">{nodeCount} nodes</span>
          )}
        </div>
        {expanded ? <ChevronDown className="w-3.5 h-3.5 text-slate-500" /> : <ChevronUp className="w-3.5 h-3.5 text-slate-500" />}
      </button>

      {/* Expanded detail */}
      {expanded && data && (
        <div className="px-3 pb-3 space-y-2">
          {/* Per-node bars */}
          <div className="space-y-1">
            {data.nodes.map((node: NodeEstimate) => {
              const cost = node.estimated_cost ?? 0;
              const widthPct = maxCost > 0 ? (cost / maxCost) * 100 : 0;
              const color = getNodeTypeColor(node.type);
              return (
                <div key={node.node_id} className="flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${color}`} />
                  <span className="text-[10px] text-slate-400 w-16 truncate shrink-0" title={node.node_id}>
                    {node.node_id}
                  </span>
                  <div className="flex-1 bg-slate-700 rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full ${color}`}
                      style={{ width: `${Math.max(widthPct, 2)}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 w-14 text-right shrink-0">
                    {cost > 0 ? `$${cost.toFixed(4)}` : 'N/A'}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Warnings */}
          {warningCount > 0 && (
            <div className="space-y-0.5">
              {data.warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-1 text-[10px] text-amber-400">
                  <AlertTriangle className="w-2.5 h-2.5 mt-0.5 shrink-0" />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
