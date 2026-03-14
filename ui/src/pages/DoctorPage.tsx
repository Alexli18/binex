import { HeartPulse, RefreshCw, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { useDoctor } from '../hooks/useUtilities';

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; bg: string }> = {
  ok: { icon: CheckCircle2, color: 'text-green-400', bg: 'bg-green-900/20 border-green-700/30' },
  pass: { icon: CheckCircle2, color: 'text-green-400', bg: 'bg-green-900/20 border-green-700/30' },
  error: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-900/20 border-red-700/30' },
  fail: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-900/20 border-red-700/30' },
  warning: { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-900/20 border-yellow-700/30' },
  warn: { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-900/20 border-yellow-700/30' },
};

const defaultConfig = { icon: AlertTriangle, color: 'text-slate-400', bg: 'bg-slate-800/50 border-slate-700' };

export default function DoctorPage() {
  const { data, isLoading, error, refetch, isFetching } = useDoctor();

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-slate-800 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">
          Failed to run health checks: {(error as Error).message}
        </p>
      </div>
    );
  }

  const checks = data?.checks ?? [];
  const allOk = checks.length > 0 && checks.every((c) => c.status === 'ok' || c.status === 'pass');

  return (
    <div className="p-6 flex flex-col gap-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <HeartPulse size={24} className={allOk ? 'text-green-400' : 'text-red-400'} />
          <h1 className="text-xl font-bold">System Health</h1>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded border border-slate-600 text-slate-300 hover:bg-slate-700 disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Summary */}
      {checks.length > 0 && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            allOk
              ? 'bg-green-900/20 border-green-700/30 text-green-300'
              : 'bg-yellow-900/20 border-yellow-700/30 text-yellow-300'
          }`}
        >
          {allOk
            ? `All ${checks.length} checks passed.`
            : `${checks.filter((c) => c.status === 'ok' || c.status === 'pass').length} of ${checks.length} checks passed.`}
        </div>
      )}

      {/* Health check grid */}
      {checks.length === 0 ? (
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-8 text-center">
          <HeartPulse size={40} className="mx-auto text-slate-600 mb-3" />
          <p className="text-slate-400">No health checks returned.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {checks.map((check) => {
            const cfg = statusConfig[check.status] ?? defaultConfig;
            const Icon = cfg.icon;
            return (
              <div
                key={check.name}
                className={`rounded-lg border p-4 ${cfg.bg}`}
              >
                <div className="flex items-start gap-3">
                  <Icon size={20} className={`${cfg.color} shrink-0 mt-0.5`} />
                  <div className="min-w-0 flex-1">
                    <h3 className="font-medium text-slate-200">{check.name}</h3>
                    <p className="text-sm text-slate-400 mt-1 break-words">
                      {check.message}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
