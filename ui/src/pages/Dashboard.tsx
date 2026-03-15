import { useState, useMemo, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useRuns, useCreateRun } from '../hooks/useRuns';
import { useWorkflows } from '../hooks/useWorkflows';
import { StatusBadge } from '../components/common/StatusBadge';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { ErrorState } from '@/components/layout/ErrorState';
import { LoadingState } from '@/components/layout/LoadingState';
import { Button } from '@/components/ui/button';
import { Rocket, FileCode, Bug, Sparkles, X, Plus } from 'lucide-react';

const STATUS_OPTIONS = ['all', 'completed', 'running', 'failed', 'cancelled'] as const;

const WHATS_NEW_VERSION = 'v3';
const WHATS_NEW_ITEMS = [
  'Design system with shadcn/ui components and design tokens',
  'Visual workflow editor with drag-and-drop canvas',
  'Improved debugging tools with node replay',
  'Cost tracking and budget management',
  'Trace timeline with anomaly detection',
  'Contextual help tooltips and help panel',
];

function WhatsNew() {
  const storageKey = `binex-whats-new-dismissed-${WHATS_NEW_VERSION}`;
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(storageKey) === 'true',
  );

  const handleDismiss = useCallback(() => {
    setDismissed(true);
    localStorage.setItem(storageKey, 'true');
  }, [storageKey]);

  if (dismissed) return null;

  return (
    <div className="mb-4 rounded-lg border border-blue-800/50 bg-blue-950/30 p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-blue-400" />
          <h3 className="text-sm font-semibold text-blue-300">What's New</h3>
        </div>
        <button
          onClick={handleDismiss}
          className="p-0.5 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
          aria-label="Dismiss what's new"
        >
          <X size={14} />
        </button>
      </div>
      <ul className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
        {WHATS_NEW_ITEMS.map((item) => (
          <li key={item} className="text-xs text-slate-400 flex items-start gap-1.5">
            <span className="text-blue-500 mt-0.5">&bull;</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function NewRunModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const { data: workflows, isLoading: loadingWorkflows } = useWorkflows();
  const createRun = useCreateRun();
  const [selectedWorkflow, setSelectedWorkflow] = useState('');
  const [variablesText, setVariablesText] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = () => {
    if (!selectedWorkflow) {
      setErrorMsg('Please select a workflow');
      return;
    }
    setErrorMsg('');

    const variables: Record<string, string> = {};
    if (variablesText.trim()) {
      for (const line of variablesText.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        const eqIdx = trimmed.indexOf('=');
        if (eqIdx === -1) {
          setErrorMsg(`Invalid variable format: "${trimmed}". Use key=value.`);
          return;
        }
        variables[trimmed.slice(0, eqIdx).trim()] = trimmed.slice(eqIdx + 1).trim();
      }
    }

    createRun.mutate(
      { workflow_path: selectedWorkflow, variables },
      {
        onSuccess: (data) => {
          onClose();
          navigate(`/runs/${data.run_id}`);
        },
        onError: (err) => {
          setErrorMsg((err as Error).message);
        },
      },
    );
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-slate-800 rounded-modal shadow-modal border border-slate-700 w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-slate-100 mb-4">New Run</h3>

        <label className="block text-sm font-medium text-slate-300 mb-1">Workflow</label>
        {loadingWorkflows ? (
          <p className="text-sm text-slate-500 mb-3">Loading workflows...</p>
        ) : (
          <select
            value={selectedWorkflow}
            onChange={(e) => setSelectedWorkflow(e.target.value)}
            className="w-full border border-slate-600 rounded-md px-3 py-1.5 text-sm bg-slate-700 text-slate-200 mb-3 focus:outline-none focus:border-blue-500"
            aria-label="Select workflow"
          >
            <option value="">-- Select a workflow --</option>
            {(workflows ?? []).map((w) => (
              <option key={w} value={w}>
                {w}
              </option>
            ))}
          </select>
        )}

        <label className="block text-sm font-medium text-slate-300 mb-1">
          Variables (key=value, one per line)
        </label>
        <textarea
          value={variablesText}
          onChange={(e) => setVariablesText(e.target.value)}
          placeholder={"topic=AI\nlanguage=en"}
          rows={3}
          className="w-full border border-slate-600 rounded-md px-3 py-1.5 text-sm font-mono bg-slate-700 text-slate-200 mb-3 focus:outline-none focus:border-blue-500"
          aria-label="Variables"
        />

        {errorMsg && <p className="text-red-400 text-sm mb-3">{errorMsg}</p>}

        <div className="flex justify-end gap-2">
          <Button onClick={onClose} variant="outline" size="sm">
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={createRun.isPending}
            size="sm"
          >
            {createRun.isPending ? 'Starting...' : 'Start Run'}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: runs, isLoading, error, refetch } = useRuns();
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [showNewRun, setShowNewRun] = useState(false);

  const filteredRuns = useMemo(() => {
    if (!runs) return [];
    return runs.filter((r) => {
      if (statusFilter !== 'all' && r.status !== statusFilter) return false;
      if (search && !r.run_id.toLowerCase().includes(search.toLowerCase())) return false;
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
          message={(error as Error).message}
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
          <Button onClick={() => setShowNewRun(true)} size="sm">
            <Plus className="w-4 h-4 mr-1.5" />
            New Run
          </Button>
        }
      />

      {showNewRun && <NewRunModal onClose={() => setShowNewRun(false)} />}

      <div className="mt-6">
        <WhatsNew />
      </div>

      <div className="flex items-center gap-4 mt-4 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-slate-600 rounded-md px-3 py-1.5 text-sm bg-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === 'all' ? 'All statuses' : s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by run ID..."
          className="border border-slate-600 rounded-md px-3 py-1.5 text-sm w-64 bg-slate-800 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
          aria-label="Search by run ID"
        />
      </div>

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
            <Button onClick={() => navigate('/workflows')} variant="outline">
              Browse Examples
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
                    ${run.total_cost.toFixed(4)}
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
