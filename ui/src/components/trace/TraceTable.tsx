import { cn } from '@/lib/utils';
import { getStatusColors } from '@/lib/design-tokens';
import type { TraceEntry, Anomaly } from '@/hooks/useAnalysis';

export interface TraceTableProps {
  timeline: TraceEntry[];
  anomalies: Anomaly[];
}

export function TraceTable({ timeline, anomalies }: TraceTableProps) {
  const anomalyNodeIds = new Set(anomalies.map((a) => a.node_id));

  if (timeline.length === 0) {
    return <p className="text-[#4a4a52] text-sm p-4">No timeline entries</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#252528] text-left text-xs text-[#4a4a52]">
            <th className="pb-2 pr-4 font-medium">Node</th>
            <th className="pb-2 pr-4 font-medium">Status</th>
            <th className="pb-2 pr-4 font-medium">Duration</th>
            <th className="pb-2 pr-4 font-medium">Offset</th>
            <th className="pb-2 font-medium">Started</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#252528]/50">
          {timeline.map((entry) => {
            const sc = getStatusColors(entry.status);
            const isAnomaly = anomalyNodeIds.has(entry.node_id);
            return (
              <tr
                key={entry.node_id}
                className={cn(
                  'transition-colors hover:bg-[#1a1a1d]/50',
                  isAnomaly && 'bg-orange-900/10',
                )}
              >
                <td className="py-2 pr-4 font-mono text-xs text-[#80808a]">
                  {entry.node_id}
                  {isAnomaly && (
                    <span className="ml-1.5 text-orange-400 text-[10px]">anomaly</span>
                  )}
                </td>
                <td className="py-2 pr-4">
                  <span className={cn('px-1.5 py-0.5 rounded text-xs', sc.bg, sc.text)}>
                    {entry.status}
                  </span>
                </td>
                <td className="py-2 pr-4 font-mono text-xs">
                  {entry.duration_s?.toFixed(3) ?? '-'}s
                </td>
                <td className="py-2 pr-4 font-mono text-xs text-[#80808a]">
                  {entry.offset_s?.toFixed(3) ?? '-'}s
                </td>
                <td className="py-2 font-mono text-xs text-[#80808a]">
                  {entry.started_at ?? '-'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
