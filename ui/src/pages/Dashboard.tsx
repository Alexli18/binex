import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useRuns, useCreateRun } from '../hooks/useRuns';
import { useWorkflows } from '../hooks/useWorkflows';
import { StatusBadge } from '../components/common/StatusBadge';

const STATUS_OPTIONS = ['all', 'completed', 'running', 'failed', 'cancelled'] as const;

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
        className="bg-slate-800 rounded-lg shadow-xl border border-slate-700 w-full max-w-md p-6"
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
            className="w-full border border-slate-600 rounded px-3 py-1.5 text-sm bg-slate-700 text-slate-200 mb-3"
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
          className="w-full border border-slate-600 rounded px-3 py-1.5 text-sm font-mono bg-slate-700 text-slate-200 mb-3"
          aria-label="Variables"
        />

        {errorMsg && <p className="text-red-400 text-sm mb-3">{errorMsg}</p>}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm border border-slate-600 rounded text-slate-300 hover:bg-slate-700"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={createRun.isPending}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50"
          >
            {createRun.isPending ? 'Starting...' : 'Start Run'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: runs, isLoading, error } = useRuns();
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
      <div className="p-6">
        <p className="text-slate-500">Loading runs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">Failed to load runs: {(error as Error).message}</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-slate-100">Dashboard</h2>
        <button
          onClick={() => setShowNewRun(true)}
          className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-500"
        >
          New Run
        </button>
      </div>

      {showNewRun && <NewRunModal onClose={() => setShowNewRun(false)} />}

      <div className="flex items-center gap-4 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-slate-600 rounded px-3 py-1.5 text-sm bg-slate-800 text-slate-200"
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
          className="border border-slate-600 rounded px-3 py-1.5 text-sm w-64 bg-slate-800 text-slate-200 placeholder:text-slate-500"
          aria-label="Search by run ID"
        />
      </div>

      {filteredRuns.length === 0 ? (
        <p className="text-slate-500">No runs found</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-700">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-800">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-slate-400">Run ID</th>
                <th className="text-left px-4 py-2.5 font-medium text-slate-400">Workflow</th>
                <th className="text-left px-4 py-2.5 font-medium text-slate-400">Status</th>
                <th className="text-center px-4 py-2.5 font-medium text-slate-400">Nodes</th>
                <th className="text-right px-4 py-2.5 font-medium text-slate-400">Cost</th>
                <th className="text-left px-4 py-2.5 font-medium text-slate-400">Created</th>
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
