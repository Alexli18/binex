import { useState, useMemo } from 'react';
import { CheckCircle2, XCircle, Clock, SkipForward, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { getStatusColors } from '@/lib/design-tokens';
import type { DebugNode } from '@/hooks/useAnalysis';

const statusIcon = (status: string) => {
  const tokens = getStatusColors(status);
  switch (status) {
    case 'completed':
      return <CheckCircle2 size={16} className={tokens.text} />;
    case 'failed':
      return <XCircle size={16} className={tokens.text} />;
    case 'running':
      return <Clock size={16} className={`${tokens.text} animate-pulse`} />;
    case 'skipped':
      return <SkipForward size={16} className={tokens.text} />;
    default:
      return <Clock size={16} className={tokens.text} />;
  }
};

export interface DebugNodeListProps {
  nodes: DebugNode[];
  selectedNodeId: string | null;
  errorsOnly: boolean;
  onSelectNode: (nodeId: string | null) => void;
  onErrorsOnlyChange: (value: boolean) => void;
}

export function DebugNodeList({
  nodes,
  selectedNodeId,
  errorsOnly,
  onSelectNode,
  onErrorsOnlyChange,
}: DebugNodeListProps) {
  const [filter, setFilter] = useState('');

  const filteredNodes = useMemo(() => {
    if (!filter) return nodes;
    const lower = filter.toLowerCase();
    return nodes.filter(
      (n) =>
        n.node_id.toLowerCase().includes(lower) ||
        n.status.toLowerCase().includes(lower),
    );
  }, [nodes, filter]);

  return (
    <div className="w-80 flex flex-col border border-[#252528] rounded-lg bg-[#1a1a1d]/50 overflow-hidden">
      {/* Filter */}
      <div className="p-3 border-b border-[#252528] space-y-2">
        <div className="relative">
          <Search
            size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#4a4a52]"
          />
          <Input
            type="text"
            placeholder="Filter nodes..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="pl-8"
            data-testid="debug-node-filter-input"
          />
        </div>
        <label className="flex items-center gap-2 text-xs text-[#80808a] cursor-pointer">
          <input
            type="checkbox"
            checked={errorsOnly}
            onChange={(e) => onErrorsOnlyChange(e.target.checked)}
            className="rounded border-[#333338] bg-[#131315] text-amber-400 focus:ring-amber-500 focus:ring-offset-0"
            data-testid="debug-errors-only-toggle"
          />
          Errors only
        </label>
      </div>

      {/* Node list */}
      <div className="flex-1 overflow-y-auto">
        {filteredNodes.length === 0 ? (
          <p className="p-4 text-sm text-[#4a4a52]">No nodes found</p>
        ) : (
          <ul className="divide-y divide-[#252528]/50">
            {filteredNodes.map((node) => (
              <li key={node.node_id}>
                <button
                  data-testid={`debug-node-${node.node_id}`}
                  onClick={() =>
                    onSelectNode(
                      selectedNodeId === node.node_id ? null : node.node_id,
                    )
                  }
                  className={cn(
                    'w-full text-left px-3 py-2.5 flex items-center gap-2.5 text-sm transition-colors',
                    selectedNodeId === node.node_id
                      ? 'bg-amber-500/20 border-l-2 border-amber-500'
                      : 'hover:bg-[#1a1a1d]/30 border-l-2 border-transparent',
                  )}
                >
                  {statusIcon(node.status)}
                  <div className="min-w-0 flex-1">
                    <p className="font-mono text-xs truncate">
                      {node.node_id}
                    </p>
                    {node.duration_s !== null && (
                      <p className="text-xs text-[#4a4a52] mt-0.5">
                        {node.duration_s.toFixed(3)}s
                      </p>
                    )}
                  </div>
                  {node.error && (
                    <XCircle size={12} className={`${getStatusColors('failed').text} shrink-0`} />
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function DebugNodeListSkeleton() {
  return (
    <div className="w-80 flex flex-col border border-[#252528] rounded-lg bg-[#1a1a1d]/50 overflow-hidden">
      <div className="p-3 border-b border-[#252528] space-y-2">
        <Skeleton className="h-8 w-full bg-[#252528]" />
        <Skeleton className="h-4 w-24 bg-[#252528]" />
      </div>
      <div className="flex-1 space-y-1 p-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full bg-[#252528]" />
        ))}
      </div>
    </div>
  );
}
