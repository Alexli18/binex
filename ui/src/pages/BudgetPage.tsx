import { useState } from 'react';
import { useRuns } from '../hooks/useRuns';
import { Wallet, AlertTriangle, Info } from 'lucide-react';

export default function BudgetPage() {
  const { data: runs, isLoading } = useRuns();
  const [maxCost, setMaxCost] = useState<string>('1.00');
  const [policy, setPolicy] = useState<'stop' | 'warn'>('stop');

  return (
    <div className="p-6 space-y-6 bg-slate-900 min-h-screen">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Wallet className="w-6 h-6 text-blue-400" />
        <h1 className="text-2xl font-bold text-white">Budget Management</h1>
      </div>

      {/* Config Section */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Budget Configuration</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Max cost per run ($)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={maxCost}
              onChange={(e) => setMaxCost(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Over-budget policy
            </label>
            <select
              value={policy}
              onChange={(e) => setPolicy(e.target.value as 'stop' | 'warn')}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            >
              <option value="stop">Stop execution</option>
              <option value="warn">Warn and continue</option>
            </select>
          </div>
        </div>

        <div className="mt-4 flex items-start gap-2 bg-slate-700/50 rounded-lg p-3">
          <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-slate-400">
            Budget settings are configured in workflow YAML files via the{' '}
            <code className="text-blue-300 bg-slate-700 px-1 rounded">budget</code> section.
            The values above are for reference only.
          </p>
        </div>
      </div>

      {/* Recent Runs Table */}
      <div className="bg-slate-800 rounded-lg border border-slate-700">
        <div className="px-6 py-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-white">Recent Runs</h2>
        </div>

        {isLoading ? (
          <div className="p-6 text-slate-400 text-sm">Loading runs...</div>
        ) : !runs || runs.length === 0 ? (
          <div className="p-6 text-slate-500 text-sm">No runs found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="px-6 py-3 font-medium">Run ID</th>
                  <th className="px-6 py-3 font-medium">Workflow</th>
                  <th className="px-6 py-3 font-medium">Cost</th>
                  <th className="px-6 py-3 font-medium">Budget</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Usage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {runs.map((run) => {
                  const budget = parseFloat(maxCost) || 1;
                  const usage = (run.total_cost / budget) * 100;
                  const isOverBudget = run.status === 'over_budget';
                  const barColor =
                    usage < 70
                      ? 'bg-green-500'
                      : usage < 90
                        ? 'bg-amber-500'
                        : 'bg-red-500';

                  return (
                    <tr
                      key={run.run_id}
                      className={
                        isOverBudget
                          ? 'border-l-2 border-l-red-500 bg-red-500/5'
                          : ''
                      }
                    >
                      <td className="px-6 py-3 font-mono text-xs text-slate-300">
                        {run.run_id.slice(0, 12)}...
                      </td>
                      <td className="px-6 py-3 text-white">{run.workflow_name}</td>
                      <td className="px-6 py-3 font-mono text-slate-300">
                        ${run.total_cost.toFixed(4)}
                      </td>
                      <td className="px-6 py-3 font-mono text-slate-400">
                        ${budget.toFixed(2)}
                      </td>
                      <td className="px-6 py-3">
                        {isOverBudget ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400">
                            <AlertTriangle className="w-3 h-3" />
                            over_budget
                          </span>
                        ) : (
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                              run.status === 'completed'
                                ? 'bg-green-500/20 text-green-400'
                                : run.status === 'running'
                                  ? 'bg-blue-500/20 text-blue-400'
                                  : run.status === 'failed'
                                    ? 'bg-red-500/20 text-red-400'
                                    : 'bg-slate-500/20 text-slate-400'
                            }`}
                          >
                            {run.status}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-slate-700 rounded-full h-2 max-w-[100px]">
                            <div
                              className={`h-2 rounded-full ${barColor} transition-all`}
                              style={{ width: `${Math.min(usage, 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-400 w-12 text-right">
                            {usage.toFixed(0)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
