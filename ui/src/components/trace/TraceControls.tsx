import { AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Anomaly } from '@/hooks/useAnalysis';
import { HelpTooltip } from '@/components/common/HelpTooltip';

export interface TraceControlsProps {
  runId: string;
  status: string;
  totalDuration: number;
  anomalies: Anomaly[];
}

export function TraceControls({
  runId,
  status,
  totalDuration,
  anomalies,
}: TraceControlsProps) {
  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold inline-flex items-center gap-2">
            Trace Timeline
            <HelpTooltip
              side="right"
              content="Gantt chart of node execution. Bar width = duration, position = start offset. Nodes with orange rings took significantly longer than average."
            />
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Total duration: {totalDuration.toFixed(3)}s |{' '}
            Status: {status}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to={`/runs/${runId}/debug`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Debug
          </Link>
          <Link
            to={`/runs/${runId}/diagnose`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Diagnose
          </Link>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-blue-500" />
          <span>Completed</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-red-500" />
          <span>Failed</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-amber-500" />
          <span>Running</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded ring-2 ring-orange-400 ring-offset-1 ring-offset-slate-900 bg-blue-500" />
          <span>Anomaly</span>
        </div>
      </div>

      {/* Anomalies */}
      {anomalies.length > 0 && (
        <div className="border border-orange-700/50 rounded-lg bg-orange-900/10 p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={16} className="text-orange-400" />
            <h2 className="text-sm font-medium text-orange-300 inline-flex items-center gap-1.5">
              Latency Anomalies ({anomalies.length})
              <HelpTooltip
                side="right"
                content="Nodes that took significantly longer than average. The ratio shows how many times slower than the mean duration."
              />
            </h2>
          </div>
          <div className="space-y-2">
            {anomalies.map((a) => (
              <div
                key={a.node_id}
                className="flex items-center justify-between text-sm bg-orange-900/20 rounded px-3 py-2"
              >
                <span className="font-mono text-xs text-slate-300">
                  {a.node_id}
                </span>
                <span className="text-orange-300">
                  {a.duration_s.toFixed(3)}s ({a.ratio.toFixed(1)}x avg)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
