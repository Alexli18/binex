import { HeartPulse, RefreshCw, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { useDoctor } from '../hooks/useUtilities';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { ErrorState } from '@/components/layout/ErrorState';
import { LoadingState } from '@/components/layout/LoadingState';
import { Button } from '@/components/ui/button';

const statusConfig: Record<string, { icon: typeof CheckCircle2; color: string; bg: string }> = {
  ok: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-900/20 border-emerald-700/30' },
  pass: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-900/20 border-emerald-700/30' },
  error: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-900/20 border-red-700/30' },
  fail: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-900/20 border-red-700/30' },
  warning: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-900/20 border-amber-700/30' },
  warn: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-900/20 border-amber-700/30' },
};

const defaultConfig = { icon: AlertTriangle, color: 'text-slate-400', bg: 'bg-slate-800/50 border-slate-700' };

export default function DoctorPage() {
  const { data, isLoading, error, refetch, isFetching } = useDoctor();

  if (isLoading) {
    return (
      <PageShell>
        <LoadingState message="Running health checks..." variant="skeleton" />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <Breadcrumb items={[{ label: 'System', href: '/system/doctor' }, { label: 'Doctor' }]} className="mb-4" />
        <ErrorState
          title="Failed to run health checks"
          message={(error as Error).message}
          onRetry={() => refetch()}
        />
      </PageShell>
    );
  }

  const checks = data?.checks ?? [];
  const allOk = checks.length > 0 && checks.every((c) => c.status === 'ok' || c.status === 'pass');

  return (
    <PageShell className="max-w-4xl">
      <Breadcrumb items={[{ label: 'System', href: '/system/doctor' }, { label: 'Doctor' }]} className="mb-4" />

      <PageHeader
        title="System Health"
        description={
          checks.length > 0
            ? allOk
              ? `All ${checks.length} checks passed`
              : `${checks.filter((c) => c.status === 'ok' || c.status === 'pass').length} of ${checks.length} checks passed`
            : undefined
        }
        actions={
          <Button
            onClick={() => refetch()}
            disabled={isFetching}
            variant="outline"
            size="sm"
          >
            <RefreshCw size={14} className={isFetching ? 'animate-spin mr-1.5' : 'mr-1.5'} />
            Refresh
          </Button>
        }
      />

      <div className="mt-6">
        {/* Summary banner */}
        {checks.length > 0 && (
          <div
            className={`rounded-card border p-3 text-sm mb-6 ${
              allOk
                ? 'bg-emerald-900/20 border-emerald-700/30 text-emerald-300'
                : 'bg-amber-900/20 border-amber-700/30 text-amber-300'
            }`}
          >
            {allOk
              ? `All ${checks.length} checks passed.`
              : `${checks.filter((c) => c.status === 'ok' || c.status === 'pass').length} of ${checks.length} checks passed.`}
          </div>
        )}

        {/* Health check grid */}
        {checks.length === 0 ? (
          <div className="border border-slate-700 rounded-card bg-slate-800/50 p-8 text-center">
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
                  className={`rounded-card border p-4 ${cfg.bg}`}
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
    </PageShell>
  );
}
