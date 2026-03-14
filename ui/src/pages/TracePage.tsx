import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { AlertTriangle } from 'lucide-react';
import { useTrace } from '../hooks/useAnalysis';
import type { TraceEntry } from '../hooks/useAnalysis';

const statusBarColor = (status: string) => {
  switch (status) {
    case 'completed':
      return 'bg-blue-500';
    case 'failed':
      return 'bg-red-500';
    case 'running':
      return 'bg-amber-500 animate-pulse';
    case 'skipped':
      return 'bg-slate-600';
    default:
      return 'bg-slate-500';
  }
};

interface TooltipInfo {
  entry: TraceEntry;
  x: number;
  y: number;
}

function GanttChart({
  timeline,
  totalDuration,
  anomalyNodeIds,
}: {
  timeline: TraceEntry[];
  totalDuration: number;
  anomalyNodeIds: Set<string>;
}) {
  const [tooltip, setTooltip] = useState<TooltipInfo | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const barHeight = 32;
  const labelWidth = 160;
  const chartPadding = 16;

  // Sort by offset
  const sorted = useMemo(
    () =>
      [...timeline].sort(
        (a, b) => (a.offset_s ?? 0) - (b.offset_s ?? 0),
      ),
    [timeline],
  );

  if (totalDuration === 0) {
    return (
      <p className="text-slate-500 text-sm p-4">
        No timeline data (total duration is 0).
      </p>
    );
  }

  return (
    <div className="relative">
      {/* Time axis */}
      <div
        className="flex items-center text-xs text-slate-500 mb-2"
        style={{ paddingLeft: labelWidth + chartPadding }}
      >
        <span>0s</span>
        <span className="flex-1 text-center">
          {(totalDuration / 2).toFixed(1)}s
        </span>
        <span>{totalDuration.toFixed(1)}s</span>
      </div>

      {/* Rows */}
      <div className="space-y-1">
        {sorted.map((entry) => {
          const offset = entry.offset_s ?? 0;
          const duration = entry.duration_s ?? 0;
          const leftPct = totalDuration > 0 ? Math.min((offset / totalDuration) * 100, 99) : 0;
          const rawWidthPct = totalDuration > 0 ? (duration / totalDuration) * 100 : 0;
          const widthPct = Math.max(Math.min(rawWidthPct, 100 - leftPct), 0.5);
          const isAnomaly = anomalyNodeIds.has(entry.node_id);
          const isSelected = selectedId === entry.node_id;

          return (
            <div
              key={entry.node_id}
              className={`flex items-center gap-2 rounded transition-colors ${
                isSelected ? 'bg-slate-700/50' : 'hover:bg-slate-800/50'
              }`}
              style={{ height: barHeight }}
            >
              {/* Label */}
              <div
                className="text-xs font-mono text-slate-400 truncate shrink-0 text-right pr-2"
                style={{ width: labelWidth }}
                title={entry.node_id}
              >
                {entry.node_id}
              </div>

              {/* Bar container */}
              <div className="flex-1 relative overflow-hidden" style={{ height: barHeight - 8 }}>
                <div
                  className={`absolute top-0 h-full rounded cursor-pointer transition-all ${statusBarColor(entry.status)} ${
                    isAnomaly
                      ? 'ring-2 ring-orange-400 ring-offset-1 ring-offset-slate-900'
                      : ''
                  } ${isSelected ? 'opacity-100' : 'opacity-80 hover:opacity-100'}`}
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    minWidth: 4,
                  }}
                  onClick={() =>
                    setSelectedId(
                      isSelected ? null : entry.node_id,
                    )
                  }
                  onMouseEnter={(e) =>
                    setTooltip({
                      entry,
                      x: e.clientX,
                      y: e.clientY,
                    })
                  }
                  onMouseLeave={() => setTooltip(null)}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 bg-slate-800 border border-slate-600 rounded-lg shadow-xl px-3 py-2 text-xs pointer-events-none"
          style={{
            left: tooltip.x + 12,
            top: tooltip.y - 10,
          }}
        >
          <p className="font-mono font-bold text-slate-200">
            {tooltip.entry.node_id}
          </p>
          <div className="mt-1 space-y-0.5 text-slate-400">
            <p>
              Status: <span className="text-slate-200">{tooltip.entry.status}</span>
            </p>
            <p>
              Duration:{' '}
              <span className="text-slate-200">
                {tooltip.entry.duration_s?.toFixed(3) ?? '-'}s
              </span>
            </p>
            <p>
              Offset:{' '}
              <span className="text-slate-200">
                {tooltip.entry.offset_s?.toFixed(3) ?? '-'}s
              </span>
            </p>
            {tooltip.entry.error && (
              <p className="text-red-400 mt-1">{tooltip.entry.error}</p>
            )}
          </div>
        </div>
      )}

      {/* Selected detail */}
      {selectedId && (
        <div className="mt-4 p-3 rounded-lg border border-slate-700 bg-slate-800/50 text-sm">
          {(() => {
            const entry = sorted.find((e) => e.node_id === selectedId);
            if (!entry) return null;
            return (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <span className="text-slate-500 text-xs">Node</span>
                  <p className="font-mono text-xs mt-0.5">{entry.node_id}</p>
                </div>
                <div>
                  <span className="text-slate-500 text-xs">Status</span>
                  <p className="capitalize mt-0.5">{entry.status}</p>
                </div>
                <div>
                  <span className="text-slate-500 text-xs">Duration</span>
                  <p className="font-mono mt-0.5">
                    {entry.duration_s?.toFixed(3) ?? '-'}s
                  </p>
                </div>
                <div>
                  <span className="text-slate-500 text-xs">Started</span>
                  <p className="font-mono text-xs mt-0.5 text-slate-400">
                    {entry.started_at ?? '-'}
                  </p>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

export default function TracePage() {
  const { runId } = useParams<{ runId: string }>();
  const { data, isLoading, error } = useTrace(runId);

  const anomalyNodeIds = useMemo(
    () => new Set(data?.anomalies.map((a) => a.node_id) ?? []),
    [data?.anomalies],
  );

  if (!runId) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        Select a run first to view trace timeline.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="h-64 bg-slate-800 rounded animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">
          Failed to load trace: {(error as Error).message}
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 flex flex-col gap-4">
      {/* Breadcrumb */}
      <div className="text-sm text-slate-500">
        <Link to="/" className="hover:text-slate-300">
          Dashboard
        </Link>{' '}
        /{' '}
        <Link to={`/runs/${runId}`} className="hover:text-slate-300">
          {runId?.slice(0, 8)}...
        </Link>{' '}
        / <span className="text-slate-200">Trace</span>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Trace Timeline</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Total duration: {data?.total_duration_s.toFixed(3)}s |{' '}
            Status: {data?.status}
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

      {/* Gantt chart */}
      <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-4">
        <h2 className="text-sm font-medium text-slate-300 mb-3">
          Execution Timeline
        </h2>
        {data && data.timeline.length > 0 ? (
          <GanttChart
            timeline={data.timeline}
            totalDuration={data.total_duration_s}
            anomalyNodeIds={anomalyNodeIds}
          />
        ) : (
          <p className="text-slate-500 text-sm">No timeline entries</p>
        )}
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
      {data && data.anomalies.length > 0 && (
        <div className="border border-orange-700/50 rounded-lg bg-orange-900/10 p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={16} className="text-orange-400" />
            <h2 className="text-sm font-medium text-orange-300">
              Latency Anomalies ({data.anomalies.length})
            </h2>
          </div>
          <div className="space-y-2">
            {data.anomalies.map((a) => (
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
    </div>
  );
}
