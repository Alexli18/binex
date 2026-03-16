import { useState, useMemo } from 'react';
import type { TraceEntry } from '@/hooks/useAnalysis';
import { getStatusColors } from '@/lib/design-tokens';

/**
 * Returns a solid Tailwind bg class for the Gantt bar.
 * Uses the `dot` token from design-tokens (solid, full-opacity colour)
 * so bars remain visually distinct at narrow widths.
 */
const statusBarColor = (status: string): string => {
  const tokens = getStatusColors(status);
  const isRunning = status === 'running';
  return `${tokens.dot}${isRunning ? ' animate-pulse' : ''}`;
};

interface TooltipInfo {
  entry: TraceEntry;
  x: number;
  y: number;
}

export interface TraceGanttProps {
  timeline: TraceEntry[];
  totalDuration: number;
  anomalyNodeIds: Set<string>;
}

export function TraceGantt({
  timeline,
  totalDuration,
  anomalyNodeIds,
}: TraceGanttProps) {
  const [tooltip, setTooltip] = useState<TooltipInfo | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const barHeight = 32;
  const labelWidth = 160;
  const chartPadding = 16;

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
                  role="button"
                  tabIndex={0}
                  aria-label={`${entry.node_id} — ${entry.status}${entry.duration_s != null ? `, ${entry.duration_s.toFixed(3)}s` : ''}${isAnomaly ? ', anomaly detected' : ''}`}
                  aria-pressed={isSelected}
                  className={`absolute top-0 h-full rounded cursor-pointer transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-900 ${statusBarColor(entry.status)} ${
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
                    setSelectedId(isSelected ? null : entry.node_id)
                  }
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setSelectedId(isSelected ? null : entry.node_id);
                    }
                  }}
                  onMouseEnter={(e) =>
                    setTooltip({ entry, x: e.clientX, y: e.clientY })
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
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
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
