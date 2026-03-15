import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useTrace } from '../hooks/useAnalysis';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { TraceGantt } from '@/components/trace/TraceGantt';
import { TraceControls } from '@/components/trace/TraceControls';
import { Skeleton } from '@/components/ui/skeleton';

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
      <div className="p-6 flex flex-col gap-4">
        <Skeleton className="h-4 w-48 bg-slate-800" />
        <div className="space-y-1">
          <Skeleton className="h-8 w-40 bg-slate-800" />
          <Skeleton className="h-4 w-64 bg-slate-800" />
        </div>
        <Skeleton className="h-64 w-full bg-slate-800 rounded-lg" />
        <div className="flex gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-20 bg-slate-800" />
          ))}
        </div>
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
      <Breadcrumb items={[
        { label: 'Home', href: '/' },
        { label: 'Runs', href: '/' },
        { label: (runId?.slice(0, 8) ?? '') + '...', href: `/runs/${runId}` },
        { label: 'Trace' },
      ]} />

      <TraceControls
        runId={runId}
        status={data?.status ?? ''}
        totalDuration={data?.total_duration_s ?? 0}
        anomalies={data?.anomalies ?? []}
      />

      {/* Gantt chart */}
      <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-4">
        <h2 className="text-sm font-medium text-slate-300 mb-3">
          Execution Timeline
        </h2>
        {data && data.timeline.length > 0 ? (
          <TraceGantt
            timeline={data.timeline}
            totalDuration={data.total_duration_s}
            anomalyNodeIds={anomalyNodeIds}
          />
        ) : (
          <p className="text-slate-500 text-sm">No timeline entries</p>
        )}
      </div>
    </div>
  );
}
