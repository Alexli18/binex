import { useEffect, useRef } from 'react';
import { useCostEstimate } from '../hooks/useCostDashboard';
import type { NodeEstimate } from '../hooks/useCostDashboard';
import { DollarSign, AlertTriangle, Loader2 } from 'lucide-react';

interface CostEstimatePanelProps {
  yamlContent: string;
}

const TYPE_COLORS: Record<string, string> = {
  llm: 'bg-blue-500',
  local: 'bg-green-500',
  human: 'bg-purple-500',
  a2a: 'bg-slate-500',
};

const TYPE_LABELS: Record<string, string> = {
  llm: 'LLM',
  local: 'Local',
  human: 'Human',
  a2a: 'A2A',
};

function getNodeTypeColor(type: string): string {
  return TYPE_COLORS[type] ?? 'bg-slate-500';
}

export function CostEstimatePanel({ yamlContent }: CostEstimatePanelProps) {
  const estimate = useCostEstimate();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastContentRef = useRef<string>('');

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

  const maxCost = estimate.data
    ? Math.max(
        ...estimate.data.nodes
          .map((n) => n.estimated_cost ?? 0)
          .filter((c) => c > 0),
        0.0001,
      )
    : 1;

  return (
    <div className="border-t border-gray-200 p-4">
      <div className="flex items-center gap-2 mb-3">
        <DollarSign className="w-4 h-4 text-green-600" />
        <h3 className="text-sm font-semibold text-gray-700">Cost Estimate</h3>
        {estimate.isPending && (
          <Loader2 className="w-3 h-3 text-gray-400 animate-spin" />
        )}
      </div>

      {estimate.isError && (
        <p className="text-xs text-red-500">Could not estimate costs</p>
      )}

      {estimate.data && (
        <div className="space-y-3">
          {/* Total */}
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-gray-500">Total estimate</span>
            <span className="text-lg font-bold font-mono text-gray-900">
              ${estimate.data.total_estimate.toFixed(4)}
            </span>
          </div>

          {/* Per-node bars */}
          <div className="space-y-1.5">
            {estimate.data.nodes.map((node: NodeEstimate) => {
              const cost = node.estimated_cost ?? 0;
              const widthPct = maxCost > 0 ? (cost / maxCost) * 100 : 0;
              const color = getNodeTypeColor(node.type);

              return (
                <div key={node.node_id} className="flex items-center gap-2">
                  <span
                    className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${color}`}
                    title={TYPE_LABELS[node.type] ?? node.type}
                  />
                  <span className="text-xs text-gray-600 w-20 truncate flex-shrink-0" title={node.node_id}>
                    {node.node_id}
                  </span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${color} transition-all`}
                      style={{ width: `${Math.max(widthPct, 2)}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono text-gray-500 w-16 text-right flex-shrink-0">
                    {cost > 0 ? `$${cost.toFixed(4)}` : 'N/A'}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Warnings */}
          {estimate.data.warnings.length > 0 && (
            <div className="space-y-1">
              {estimate.data.warnings.map((w, i) => (
                <div
                  key={i}
                  className="flex items-start gap-1.5 bg-amber-50 border border-amber-200 rounded px-2 py-1.5"
                >
                  <AlertTriangle className="w-3 h-3 text-amber-500 mt-0.5 flex-shrink-0" />
                  <span className="text-xs text-amber-700">{w}</span>
                </div>
              ))}
            </div>
          )}

          {/* Legend */}
          <div className="flex gap-3 pt-1 border-t border-gray-100">
            {Object.entries(TYPE_LABELS).map(([type, label]) => (
              <div key={type} className="flex items-center gap-1">
                <span className={`w-2 h-2 rounded-full ${TYPE_COLORS[type]}`} />
                <span className="text-[10px] text-gray-400">{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!estimate.data && !estimate.isPending && !estimate.isError && (
        <p className="text-xs text-gray-400">
          Edit workflow YAML to see cost estimates
        </p>
      )}
    </div>
  );
}
