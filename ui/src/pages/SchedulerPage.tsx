import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Clock, Play, Square, RefreshCw, Calendar, Activity, AlertTriangle, DollarSign } from 'lucide-react';
import { useScheduler, useSchedulerStart, useSchedulerStop } from '../hooks/useScheduler';
import type { HistoryEntry } from '../hooks/useScheduler';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { LoadingState } from '@/components/layout/LoadingState';
import { ErrorState } from '@/components/layout/ErrorState';
import { EmptyState } from '@/components/layout/EmptyState';
import { StatusBadge } from '@/components/common/StatusBadge';
import { KPICard } from '@/components/cost/KPICard';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';

/** Convert cron expression to human-readable text */
function describeCron(cron: string): string {
  const parts = cron.split(/\s+/);
  if (parts.length !== 5) return cron;
  const [min, hour, dom, mon, dow] = parts;

  if (min === '*' && hour === '*') return 'Every minute';
  if (min.startsWith('*/')) return `Every ${min.slice(2)} minutes`;
  if (hour.startsWith('*/')) return `Every ${hour.slice(2)} hours`;
  if (dom === '*' && mon === '*' && dow === '*') {
    return `Daily at ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
  }
  if (dow === '1-5' && dom === '*' && mon === '*') {
    return `Weekdays at ${hour.padStart(2, '0')}:${min.padStart(2, '0')}`;
  }
  return cron;
}

export default function SchedulerPage() {
  const { data, isLoading, error, refetch, isFetching } = useScheduler();
  const startMut = useSchedulerStart();
  const stopMut = useSchedulerStop();
  const [historyFilter, setHistoryFilter] = useState<string>('all');

  if (isLoading) {
    return (
      <PageShell>
        <LoadingState message="Loading scheduler..." />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <Breadcrumb items={[{ label: 'System' }, { label: 'Scheduler' }]} className="mb-4" />
        <ErrorState
          title="Failed to load scheduler"
          message={(error as Error).message}
          onRetry={() => refetch()}
        />
      </PageShell>
    );
  }

  const isRunning = data?.running ?? false;
  const workflows = data?.workflows ?? [];
  const history = data?.history ?? [];
  const stats = data?.stats ?? { active_workflows: 0, runs_today: 0, skipped_today: 0, cost_today: 0 };

  const workflowNames = [...new Set(history.map(h => h.workflow_name))];
  const filteredHistory = historyFilter === 'all'
    ? history
    : history.filter(h => h.workflow_name === historyFilter);

  return (
    <PageShell>
      <Breadcrumb items={[{ label: 'System' }, { label: 'Scheduler' }]} className="mb-4" />

      {/* FIX 2: Only Refresh in PageHeader */}
      <PageHeader
        title="Scheduler"
        description="Cron-based workflow scheduling and execution"
        actions={
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw size={14} className={isFetching ? 'animate-spin mr-1.5' : 'mr-1.5'} />
            Refresh
          </Button>
        }
      />

      {/* FIX 4: max-w-5xl for table readability */}
      <div className="mt-6 flex flex-col gap-6 max-w-5xl">
        {/* FIX 1: Status Banner with inline Start/Stop + CLI guidance */}
        {isRunning ? (
          <div className="rounded-lg border p-4 flex items-center justify-between bg-green-900/20 border-green-700/30">
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-green-400 shadow-lg shadow-green-400/50 animate-pulse" />
              <div>
                <span className="text-sm font-medium text-[#f0f0f0]">Scheduler Running</span>
                <span className="text-xs text-[#4a4a52] ml-2">Auto-refreshes every 10s</span>
              </div>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => stopMut.mutate()}
              disabled={stopMut.isPending}
            >
              <Square className="w-3.5 h-3.5 mr-1.5" />
              Stop Scheduler
            </Button>
          </div>
        ) : (
          <div className="rounded-lg border p-6 bg-[#1a1a1d]/50 border-[#252528]">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-4 h-4 rounded-full bg-[#4a4a52]" />
              <h2 className="text-lg font-semibold text-[#f0f0f0]">Scheduler Stopped</h2>
            </div>
            <div className="flex items-center gap-3">
              <Button
                size="sm"
                onClick={() => startMut.mutate()}
                disabled={startMut.isPending}
              >
                <Play className="w-3.5 h-3.5 mr-1.5" />
                Start Scheduler
              </Button>
              <span className="text-sm text-[#4a4a52]">or run from CLI:</span>
              <code className="text-sm font-mono text-cyan-400 bg-[#131315] rounded px-3 py-1.5">
                binex scheduler start
              </code>
            </div>
          </div>
        )}

        {/* FIX 3: KPI Cards only when running */}
        {isRunning && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KPICard icon={Calendar} label="Active Workflows" value={String(stats.active_workflows)} />
            <KPICard icon={Activity} label="Runs Today" value={String(stats.runs_today)} />
            <KPICard icon={AlertTriangle} label="Skipped Today" value={String(stats.skipped_today)} />
            <KPICard icon={DollarSign} label="Cost Today" value={`$${(stats.cost_today ?? 0).toFixed(4)}`} />
          </div>
        )}

        {/* Workflows Table — FIX 5: describeCron, FIX 7: no Path column, title on Name */}
        {workflows.length === 0 ? (
          <EmptyState
            icon={Clock}
            title="No scheduled workflows"
            description="Add a schedule field to your workflow YAML to see it here."
          />
        ) : (
          <div className="border border-[#252528] rounded-lg bg-[#1a1a1d]/50 overflow-hidden">
            <div className="px-4 py-3 border-b border-[#252528]">
              <h3 className="text-sm font-medium text-[#80808a]">
                Scheduled Workflows ({workflows.length})
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-[#252528]">
                    <th className="text-left px-4 py-3 font-medium text-[#80808a]">Name</th>
                    <th className="text-left px-4 py-3 font-medium text-[#80808a]">Schedule</th>
                    <th className="text-left px-4 py-3 font-medium text-[#80808a]">Status</th>
                    <th className="text-left px-4 py-3 font-medium text-[#80808a]">Last Run</th>
                    <th className="text-left px-4 py-3 font-medium text-[#80808a]">Next Run</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#252528]/50">
                  {workflows.map((wf) => (
                    <tr key={wf.file_path} className="hover:bg-[#1a1a1d]/30 transition-colors">
                      <td className="px-4 py-3 font-medium text-[#f0f0f0]" title={wf.file_path}>
                        {wf.name}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-[#80808a]">{describeCron(wf.schedule)}</span>
                        <span className="text-xs font-mono text-[#4a4a52] ml-2" title="Cron expression">
                          {wf.schedule}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {wf.last_status ? (
                          <StatusBadge status={wf.last_status} dot />
                        ) : (
                          <span className="text-xs text-[#4a4a52]">pending</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-[#4a4a52]">
                        {wf.last_run ? new Date(wf.last_run).toLocaleString() : '\u2014'}
                      </td>
                      <td className="px-4 py-3 text-xs text-[#80808a]">
                        {wf.next_run ? new Date(wf.next_run).toLocaleString() : '\u2014'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* History Log with filter + run_id links */}
        <div className="border border-[#252528] rounded-lg bg-[#1a1a1d]/50 overflow-hidden">
          <div className="px-4 py-3 border-b border-[#252528] flex items-center justify-between">
            <h3 className="text-sm font-medium text-[#80808a]">Run History</h3>
            {workflowNames.length > 1 && (
              <Select value={historyFilter} onValueChange={setHistoryFilter}>
                <SelectTrigger className="w-[180px] h-8" aria-label="Filter by workflow">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All workflows</SelectItem>
                  {workflowNames.map(name => (
                    <SelectItem key={name} value={name}>{name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
          {filteredHistory.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <p className="text-sm text-[#4a4a52]">
                {historyFilter === 'all' ? 'No scheduler runs yet.' : `No runs for "${historyFilter}".`}
              </p>
              <p className="text-xs text-[#4a4a52] mt-1">
                History will appear here once workflows are executed by the scheduler.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-[#252528]">
                    <th className="text-left px-4 py-3 font-medium text-[#80808a]">Time</th>
                    <th className="text-left px-4 py-3 font-medium text-[#80808a]">Workflow</th>
                    <th className="text-left px-4 py-3 font-medium text-[#80808a]">Run</th>
                    <th className="text-left px-4 py-3 font-medium text-[#80808a]">Status</th>
                    <th className="text-right px-4 py-3 font-medium text-[#80808a]">Duration</th>
                    <th className="text-right px-4 py-3 font-medium text-[#80808a]">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#252528]/50">
                  {filteredHistory.map((entry: HistoryEntry, i: number) => (
                    <tr key={`${entry.timestamp}-${i}`} className="hover:bg-[#1a1a1d]/30 transition-colors">
                      <td className="px-4 py-3 text-xs text-[#4a4a52]">
                        {new Date(entry.timestamp).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-[#f0f0f0]">{entry.workflow_name}</td>
                      <td className="px-4 py-3">
                        {entry.run_id ? (
                          <Link
                            to={`/runs/${entry.run_id}`}
                            className="text-amber-400 hover:text-amber-300 hover:underline font-mono text-xs"
                          >
                            {entry.run_id}
                          </Link>
                        ) : (
                          <span className="text-xs text-[#4a4a52]">{'\u2014'}</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={entry.status} dot />
                        {entry.skip_reason && (
                          <span className="text-xs text-[#4a4a52] ml-2">({entry.skip_reason})</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-[#80808a]">
                        {entry.duration != null ? `${entry.duration.toFixed(1)}s` : '\u2014'}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-[#80808a]">
                        {entry.cost != null ? `$${entry.cost.toFixed(4)}` : '\u2014'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </PageShell>
  );
}
