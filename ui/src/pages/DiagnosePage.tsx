import { useParams, Link } from 'react-router-dom';
import { AlertTriangle, Clock, Lightbulb, DollarSign } from 'lucide-react';
import { useDiagnose } from '../hooks/useAnalysis';

const severityColors: Record<string, { badge: string; border: string }> = {
  HIGH: {
    badge: 'bg-red-500/20 text-red-300 border-red-500/50',
    border: 'border-red-500/30',
  },
  MEDIUM: {
    badge: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/50',
    border: 'border-yellow-500/30',
  },
  LOW: {
    badge: 'bg-blue-500/20 text-blue-300 border-blue-500/50',
    border: 'border-blue-500/30',
  },
  NONE: {
    badge: 'bg-green-500/20 text-green-300 border-green-500/50',
    border: 'border-green-500/30',
  },
};

export default function DiagnosePage() {
  const { runId } = useParams<{ runId: string }>();
  const { data, isLoading, error } = useDiagnose(runId);

  if (!runId) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        Select a run first to view diagnosis.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-40 bg-slate-800 rounded animate-pulse" />
          <div className="h-40 bg-slate-800 rounded animate-pulse" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">
          Failed to load diagnosis: {(error as Error).message}
        </p>
      </div>
    );
  }

  const severity = data?.severity?.toUpperCase() ?? 'NONE';
  const colors = severityColors[severity] ?? severityColors.NONE;

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
        / <span className="text-slate-200">Diagnose</span>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold">Diagnosis</h1>
          <span
            className={`px-2.5 py-0.5 rounded text-xs font-medium border ${colors.badge}`}
          >
            {severity}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to={`/runs/${runId}/debug`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Debug
          </Link>
          <Link
            to={`/runs/${runId}/trace`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Trace
          </Link>
        </div>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-3">
          <span className="text-xs text-slate-500">Status</span>
          <p className="mt-1 font-medium capitalize">{data?.status}</p>
        </div>
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-3">
          <span className="text-xs text-slate-500">Root Causes</span>
          <p className="mt-1 font-medium text-red-400">
            {data?.root_causes.length ?? 0}
          </p>
        </div>
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-3">
          <span className="text-xs text-slate-500">Latency Anomalies</span>
          <p className="mt-1 font-medium text-yellow-400">
            {data?.latency_anomalies.length ?? 0}
          </p>
        </div>
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-3 flex items-center gap-2">
          <DollarSign size={14} className="text-green-400" />
          <div>
            <span className="text-xs text-slate-500">Total Cost</span>
            <p className="mt-0.5 font-mono font-medium">
              ${data?.total_cost.toFixed(4)}
            </p>
          </div>
        </div>
      </div>

      {/* Root Causes */}
      {data && data.root_causes.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={16} className="text-red-400" />
            <h2 className="text-sm font-medium text-red-300">
              Root Causes ({data.root_causes.length})
            </h2>
          </div>
          <div className="space-y-2">
            {data.root_causes.map((rc) => (
              <div
                key={rc.node_id}
                className="border border-red-700/50 rounded-lg bg-red-900/10 p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-sm text-slate-200">
                    {rc.node_id}
                  </span>
                  <span className="text-xs text-red-400 capitalize">
                    {rc.status}
                  </span>
                </div>
                <p className="text-sm text-red-300 font-mono whitespace-pre-wrap break-words bg-red-900/30 rounded p-2">
                  {rc.error}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Latency Anomalies */}
      {data && data.latency_anomalies.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Clock size={16} className="text-yellow-400" />
            <h2 className="text-sm font-medium text-yellow-300">
              Latency Anomalies ({data.latency_anomalies.length})
            </h2>
          </div>
          <div className="space-y-2">
            {data.latency_anomalies.map((la) => (
              <div
                key={la.node_id}
                className="border border-yellow-700/50 rounded-lg bg-yellow-900/10 p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-sm text-slate-200">
                    {la.node_id}
                  </span>
                  <span className="text-xs text-yellow-400">
                    {la.ratio.toFixed(1)}x expected
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-xs text-slate-500">Actual</span>
                    <p className="font-mono text-yellow-300">
                      {la.duration_s.toFixed(3)}s
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500">Expected</span>
                    <p className="font-mono text-slate-400">
                      {la.expected_s.toFixed(3)}s
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {data && data.recommendations.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb size={16} className="text-blue-400" />
            <h2 className="text-sm font-medium text-blue-300">
              Recommendations ({data.recommendations.length})
            </h2>
          </div>
          <div className="border border-blue-700/50 rounded-lg bg-blue-900/10 p-4">
            <ol className="space-y-2">
              {data.recommendations.map((rec, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-slate-300"
                >
                  <span className="text-blue-400 font-medium shrink-0">
                    {i + 1}.
                  </span>
                  <span>{rec}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}

      {/* No issues */}
      {data &&
        data.root_causes.length === 0 &&
        data.latency_anomalies.length === 0 &&
        data.recommendations.length === 0 && (
          <div className="border border-green-700/50 rounded-lg bg-green-900/10 p-6 text-center">
            <p className="text-green-300">
              No issues detected. The run completed normally.
            </p>
          </div>
        )}
    </div>
  );
}
