import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import { StatusBadge } from '../components/common/StatusBadge';
import { NewRunModal } from '../components/common/NewRunModal';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { ErrorState } from '@/components/layout/ErrorState';
import { LoadingState } from '@/components/layout/LoadingState';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  FileCode, Bug, Plus, Download, DollarSign, Search, Workflow,
} from 'lucide-react';
import { OrphanedSessionsBanner } from '@/components/cao/OrphanedSessionsBanner';
import { CaoServerStatus } from '@/components/cao/CaoServerStatus';

const STATUS_OPTIONS = ['all', 'completed', 'running', 'failed', 'cancelled'] as const;

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: runs, isLoading, error, refetch } = useRuns();
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [showNewRun, setShowNewRun] = useState(false);

  const filteredRuns = useMemo(() => {
    if (!runs) return [];
    const q = search.toLowerCase();
    return runs.filter((r) => {
      if (statusFilter !== 'all' && r.status !== statusFilter) return false;
      if (q && !r.run_id.toLowerCase().includes(q) && !r.workflow_name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [runs, statusFilter, search]);

  // Derived stats
  const stats = useMemo(() => {
    if (!runs) return { total: 0, running: 0, failed: 0 };
    return {
      total:   runs.length,
      running: runs.filter(r => r.status === 'running').length,
      failed:  runs.filter(r => r.status === 'failed').length,
    };
  }, [runs]);

  if (isLoading) {
    return (
      <PageShell>
        <LoadingState message="Loading runs..." />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <Breadcrumb items={[{ label: 'Dashboard' }]} className="mb-4" />
        <ErrorState
          title="Failed to load runs"
          message={error instanceof Error ? error.message : String(error)}
          onRetry={() => refetch()}
        />
      </PageShell>
    );
  }

  const hasRuns = runs && runs.length > 0;

  return (
    <PageShell>
      <Breadcrumb items={[{ label: 'Dashboard' }]} className="mb-4" />

      <PageHeader
        title="Dashboard"
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/costs')}
              className="text-[#80808a] border-[#252528] hover:border-[#333338] hover:text-[#80808a]"
            >
              <DollarSign className="w-3.5 h-3.5 mr-1.5" />
              Costs
            </Button>
            <Button data-testid="dashboard-new-run-btn" data-tour="new-run" onClick={() => setShowNewRun(true)} size="sm" className="bg-amber-500 hover:bg-amber-400 text-black border-0">
              <Plus className="w-3.5 h-3.5 mr-1.5" />
              New Run
            </Button>
          </div>
        }
      />

      <NewRunModal open={showNewRun} onClose={() => setShowNewRun(false)} />

      <div className="flex items-center justify-between mb-4">
        <OrphanedSessionsBanner />
        <CaoServerStatus />
      </div>

      {/* Stats strip */}
      {hasRuns && (
        <div className="grid grid-cols-3 gap-px bg-[#1a1a1d]/50 rounded-lg overflow-hidden mb-5 border border-[#252528]">
          <div className="bg-[#131315] px-4 py-3">
            <div className="text-xs text-[#4a4a52] mb-0.5">Total runs</div>
            <div className="text-lg font-semibold text-[#f0f0f0] font-mono">{stats.total}</div>
          </div>
          <div className="bg-[#131315] px-4 py-3">
            <div className="text-xs text-[#4a4a52] mb-0.5">Running</div>
            <div className={`text-lg font-semibold font-mono ${stats.running > 0 ? 'text-amber-400' : 'text-[#4a4a52]'}`}>{stats.running}</div>
          </div>
          <div className="bg-[#131315] px-4 py-3">
            <div className="text-xs text-[#4a4a52] mb-0.5">Failed</div>
            <div className={`text-lg font-semibold font-mono ${stats.failed > 0 ? 'text-red-400' : 'text-[#4a4a52]'}`}>{stats.failed}</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-5">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[148px] h-8 text-xs border-[#252528] bg-[#131315]" aria-label="Filter by status" data-testid="dashboard-status-filter">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s} value={s} className="text-xs">
                {s === 'all' ? 'All statuses' : s.charAt(0).toUpperCase() + s.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#4a4a52] pointer-events-none" />
          <Input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search runs or workflows..."
            className="pl-8 h-8 text-xs border-[#252528] bg-[#131315] placeholder:text-[#4a4a52]"
            aria-label="Search by run ID or workflow name"
            data-testid="dashboard-search-input"
          />
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate('/export')}
          className="h-8 text-xs text-[#80808a] border-[#252528] hover:border-[#333338] hover:text-[#80808a] ml-auto"
          data-testid="dashboard-export-btn"
        >
          <Download className="w-3.5 h-3.5 mr-1.5" />
          Export
        </Button>
      </div>

      {/* Empty state */}
      {!hasRuns ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-14 h-14 rounded-2xl bg-[#1a1a1d]/80 border border-[#252528] flex items-center justify-center mb-5">
            <Workflow className="w-6 h-6 text-[#4a4a52]" />
          </div>
          <h3 className="text-base font-semibold text-[#f0f0f0] mb-2">No runs yet</h3>
          <p className="text-sm text-[#4a4a52] max-w-[30ch] mb-7 leading-relaxed">
            Create a workflow in the editor or run an example to get started.
          </p>
          <div className="flex gap-2.5">
            <Button
              onClick={() => navigate('/editor')}
              className="bg-amber-500 hover:bg-amber-400 text-black border-0 h-8 text-xs"
            >
              <FileCode className="w-3.5 h-3.5 mr-1.5" />
              Open Editor
            </Button>
            <Button
              variant="outline"
              onClick={() => setShowNewRun(true)}
              className="h-8 text-xs text-[#80808a] border-[#252528] hover:border-[#333338]"
            >
              Run a File
            </Button>
          </div>
        </div>
      ) : filteredRuns.length === 0 ? (
        <div className="py-12 text-center">
          <p className="text-sm text-[#4a4a52]">No runs match your filters.</p>
          <button
            onClick={() => { setSearch(''); setStatusFilter('all'); }}
            className="text-xs text-amber-400 hover:text-amber-300 mt-2 transition-colors"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="rounded-lg border border-[#252528] overflow-hidden">
          <table className="min-w-full text-xs" data-testid="dashboard-runs-table">
            <thead>
              <tr className="border-b border-[#252528]">
                <th className="text-left px-4 py-2.5 font-medium text-[#4a4a52]">Run ID</th>
                <th className="text-left px-4 py-2.5 font-medium text-[#4a4a52]">Workflow</th>
                <th className="text-left px-4 py-2.5 font-medium text-[#4a4a52]">Status</th>
                <th className="text-center px-4 py-2.5 font-medium text-[#4a4a52]">Nodes</th>
                <th className="text-right px-4 py-2.5 font-medium text-[#4a4a52]">Cost</th>
                <th className="text-left px-4 py-2.5 font-medium text-[#4a4a52]">Started</th>
                <th className="text-right px-4 py-2.5 font-medium text-[#4a4a52] sr-only">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#252528]/70">
              {filteredRuns.map((run) => (
                <tr
                  key={run.run_id}
                  data-testid="dashboard-run-row"
                  className="hover:bg-[#1a1a1d]/30 transition-colors cursor-pointer"
                  onClick={() => navigate(`/runs/${run.run_id}`)}
                >
                  <td className="px-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <Link
                      to={`/runs/${run.run_id}`}
                      data-testid={`dashboard-run-link-${run.run_id}`}
                      className="text-amber-400 hover:text-amber-300 font-mono transition-colors"
                    >
                      {run.run_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-[#80808a] max-w-[200px] truncate">{run.workflow_name}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-2.5 text-center font-mono text-[#80808a]">
                    {run.completed_nodes}/{run.total_nodes}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-[#80808a]">
                    ${(run.total_cost ?? 0).toFixed(4)}
                  </td>
                  <td className="px-4 py-2.5 text-[#4a4a52]">
                    {new Date(run.started_at).toLocaleString(undefined, {
                      month: 'short', day: 'numeric',
                      hour: '2-digit', minute: '2-digit',
                    })}
                  </td>
                  <td className="px-4 py-2.5 text-right" onClick={(e) => e.stopPropagation()}>
                    {run.status === 'failed' && (
                      <Link
                        to={`/runs/${run.run_id}/debug`}
                        data-testid={`dashboard-debug-link-${run.run_id}`}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-red-800/60 text-red-400 hover:bg-red-900/20 transition-colors"
                      >
                        <Bug size={11} />
                        Debug
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}
