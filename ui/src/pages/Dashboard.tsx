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
  Rocket, FileCode, Bug, Plus, Download, DollarSign,
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

  return (
    <PageShell>
      <Breadcrumb items={[{ label: 'Dashboard' }]} className="mb-4" />

      <PageHeader
        title="Dashboard"
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/costs')}
            >
              <DollarSign className="w-3.5 h-3.5 mr-1.5" />
              View Costs
            </Button>
            <Button onClick={() => setShowNewRun(true)} size="sm">
              <Plus className="w-4 h-4 mr-1.5" />
              New Run
            </Button>
          </div>
        }
      />

      <NewRunModal open={showNewRun} onClose={() => setShowNewRun(false)} />

      <div className="flex items-center justify-between mb-2">
        <OrphanedSessionsBanner />
        <CaoServerStatus />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mt-4 mb-4">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[160px]" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s} value={s}>
                {s === 'all' ? 'All statuses' : s.charAt(0).toUpperCase() + s.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by run ID or workflow..."
          className="w-64"
          aria-label="Search by run ID or workflow name"
        />

        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate('/export')}
        >
          <Download className="w-3.5 h-3.5 mr-1.5" />
          Export
        </Button>
      </div>

      {/* Runs Table */}
      {filteredRuns.length === 0 && (!runs || runs.length === 0) ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="rounded-full bg-slate-800 p-5 mb-5">
            <Rocket className="h-10 w-10 text-blue-400" />
          </div>
          <h3 className="text-xl font-semibold text-slate-100 mb-2">Welcome to Binex</h3>
          <p className="text-sm text-slate-400 max-w-sm mb-6">
            Create your first workflow or run an example to get started.
          </p>
          <div className="flex gap-3">
            <Button onClick={() => navigate('/editor')} variant="default">
              <FileCode className="w-4 h-4 mr-2" />
              Create Workflow
            </Button>
          </div>
        </div>
      ) : filteredRuns.length === 0 ? (
        <p className="text-slate-500">No runs match your filters</p>
      ) : (
        <div className="overflow-x-auto rounded-card border border-slate-700">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-800">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-slate-400">Run ID</th>
                <th className="text-left px-4 py-2.5 font-medium text-slate-400">Workflow</th>
                <th className="text-left px-4 py-2.5 font-medium text-slate-400">Status</th>
                <th className="text-center px-4 py-2.5 font-medium text-slate-400">Nodes</th>
                <th className="text-right px-4 py-2.5 font-medium text-slate-400">Cost</th>
                <th className="text-left px-4 py-2.5 font-medium text-slate-400">Created</th>
                <th className="text-right px-4 py-2.5 font-medium text-slate-400">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredRuns.map((run) => (
                <tr key={run.run_id} className="hover:bg-slate-800/60 transition-colors">
                  <td className="px-4 py-2.5">
                    <Link
                      to={`/runs/${run.run_id}`}
                      className="text-blue-400 hover:text-blue-300 hover:underline font-mono text-xs"
                    >
                      {run.run_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-slate-200">{run.workflow_name}</td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-2.5 text-center text-slate-300">
                    {run.completed_nodes}/{run.total_nodes}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-300">
                    ${(run.total_cost ?? 0).toFixed(4)}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 text-xs">
                    {new Date(run.started_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {run.status === 'failed' && (
                      <Link
                        to={`/runs/${run.run_id}/debug`}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-red-800 text-red-400 hover:bg-red-900/30 transition-colors"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Bug size={12} />
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
