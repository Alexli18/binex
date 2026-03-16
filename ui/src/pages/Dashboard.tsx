import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import { useCostDashboard, type DashboardData } from '../hooks/useCostDashboard';
import { StatusBadge } from '../components/common/StatusBadge';
import { NewRunModal } from '../components/common/NewRunModal';
import { HelpTooltip } from '@/components/common/HelpTooltip';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { ErrorState } from '@/components/layout/ErrorState';
import { LoadingState } from '@/components/layout/LoadingState';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  Rocket, FileCode, Bug, Plus, Download,
  DollarSign, TrendingUp, Play, Wallet, Info,
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

const STATUS_OPTIONS = ['all', 'completed', 'running', 'failed', 'cancelled'] as const;
const PERIODS = ['24h', '7d', '30d', 'all'] as const;

type DashboardTab = 'runs' | 'costs' | 'budget';

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: runs, isLoading, error, refetch } = useRuns();
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [showNewRun, setShowNewRun] = useState(false);
  const [dashTab, setDashTab] = useState<DashboardTab>('runs');

  // Cost dashboard data
  const [period, setPeriod] = useState<string>('7d');
  const costQuery = useCostDashboard(period);

  // Budget state
  const [maxCost, setMaxCost] = useState<string>('1.00');
  const [policy, setPolicy] = useState<'stop' | 'warn'>('stop');

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
          message={(error as Error).message}
          onRetry={() => refetch()}
        />
      </PageShell>
    );
  }

  const costData = costQuery.data;
  const budgetLimit = (costData as DashboardData & { budget_limit?: number })?.budget_limit;
  const budgetUsed = costData && budgetLimit && budgetLimit > 0
    ? Math.min((costData.total_cost / budgetLimit) * 100, 100)
    : 0;
  const budgetColor = budgetUsed < 70 ? 'bg-emerald-500' : budgetUsed < 90 ? 'bg-amber-500' : 'bg-red-500';

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

      <NewRunModal open={showNewRun} onClose={() => setShowNewRun(false)} />

      {/* Tab bar */}
      <div className="flex items-center gap-0 mt-4 border-b border-slate-700/50" role="tablist" aria-label="Dashboard tabs">
        {(['runs', 'costs', 'budget'] as DashboardTab[]).map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={dashTab === tab}
            onClick={() => setDashTab(tab)}
            className={cn(
              'px-4 min-h-[44px] text-sm font-medium border-b-2 transition-colors capitalize',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset',
              dashTab === tab
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200',
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Runs Tab */}
      {dashTab === 'runs' && (
        <div className="mt-4">
          <div className="flex items-center gap-4 mb-4">
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
              placeholder="Search by run ID or workflow..."
              className="border border-slate-600 rounded-md px-3 py-1.5 text-sm w-64 bg-slate-800 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
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
        </div>
      )}

      {/* Costs Tab */}
      {dashTab === 'costs' && (
        <div className="mt-4 space-y-6">
          {/* Period selector */}
          <div className="flex gap-1 bg-slate-800 rounded-lg p-1 w-fit">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  period === p
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          {costQuery.isLoading ? (
            <LoadingState message="Loading cost dashboard..." />
          ) : costQuery.error ? (
            <ErrorState
              title="Failed to load dashboard"
              message={(costQuery.error as Error).message}
              onRetry={() => costQuery.refetch()}
            />
          ) : (
            <>
              {/* KPI Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-slate-800 rounded-card border border-slate-700 p-4">
                  <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                    <DollarSign className="w-4 h-4" />
                    Total Cost
                    <HelpTooltip content="Sum of all LLM API costs for the selected period." />
                  </div>
                  <p className="text-2xl font-bold text-white font-mono">
                    ${costData?.total_cost.toFixed(2) ?? '0.00'}
                  </p>
                </div>

                <div className="bg-slate-800 rounded-card border border-slate-700 p-4">
                  <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                    <TrendingUp className="w-4 h-4" />
                    Avg per Run
                  </div>
                  <p className="text-2xl font-bold text-white font-mono">
                    ${costData?.avg_per_run.toFixed(4) ?? '0.00'}
                  </p>
                </div>

                <div className="bg-slate-800 rounded-card border border-slate-700 p-4">
                  <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                    <Play className="w-4 h-4" />
                    Total Runs
                  </div>
                  <p className="text-2xl font-bold text-white">
                    {costData?.run_count ?? 0}
                  </p>
                </div>

                <div className="bg-slate-800 rounded-card border border-slate-700 p-4">
                  <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                    <Wallet className="w-4 h-4" />
                    Budget Used
                    <HelpTooltip content="'stop' policy halts execution when exceeded. 'warn' policy logs a warning but continues." />
                  </div>
                  {budgetLimit && budgetLimit > 0 ? (
                    <>
                      <p className="text-2xl font-bold text-white">
                        {budgetUsed.toFixed(0)}%
                      </p>
                      <div className="mt-2 w-full bg-slate-700 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${budgetColor} transition-all`}
                          style={{ width: `${budgetUsed}%` }}
                        />
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-slate-500 mt-1">Not configured</p>
                  )}
                </div>
              </div>

              {/* Cost Trend Chart */}
              <div className="bg-slate-800 rounded-card border border-slate-700 p-4">
                <h2 className="text-lg font-semibold text-white mb-4">Cost Trend</h2>
                {costData && costData.cost_trend.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={costData.cost_trend}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(v) => `$${v}`} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1e293b',
                          border: '1px solid #475569',
                          borderRadius: '8px',
                          color: '#e2e8f0',
                        }}
                        formatter={(value: unknown, name: unknown) => {
                          const v = Number(value);
                          if (name === 'cost') return [`$${v.toFixed(4)}`, 'Cost'];
                          return [v, 'Runs'];
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="cost"
                        stroke="#3b82f6"
                        fill="#3b82f680"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-slate-500 text-sm text-center py-12">
                    No cost data for this period
                  </p>
                )}
              </div>

              {/* Side-by-side charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-slate-800 rounded-card border border-slate-700 p-4">
                  <h2 className="text-lg font-semibold text-white mb-4">Cost by Model</h2>
                  {costData && costData.cost_by_model.length > 0 ? (
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={costData.cost_by_model} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis type="number" stroke="#94a3b8" fontSize={12} tickFormatter={(v) => `$${v}`} />
                        <YAxis type="category" dataKey="model" stroke="#94a3b8" fontSize={12} width={120} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #475569',
                            borderRadius: '8px',
                            color: '#e2e8f0',
                          }}
                          formatter={(value: unknown) => [`$${Number(value).toFixed(6)}`, 'Cost']}
                        />
                        <Bar dataKey="cost" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="text-slate-500 text-sm text-center py-12">No model cost data</p>
                  )}
                </div>

                <div className="bg-slate-800 rounded-card border border-slate-700 p-4">
                  <h2 className="text-lg font-semibold text-white mb-4">Cost by Node</h2>
                  {costData && costData.cost_by_node.length > 0 ? (
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={costData.cost_by_node} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis type="number" stroke="#94a3b8" fontSize={12} tickFormatter={(v) => `$${v}`} />
                        <YAxis type="category" dataKey="node_id" stroke="#94a3b8" fontSize={12} width={120} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #475569',
                            borderRadius: '8px',
                            color: '#e2e8f0',
                          }}
                          formatter={(value: unknown) => [`$${Number(value).toFixed(6)}`, 'Cost']}
                        />
                        <Bar dataKey="cost" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <p className="text-slate-500 text-sm text-center py-12">No node cost data</p>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Budget Tab */}
      {dashTab === 'budget' && (
        <div className="mt-4 space-y-6">
          {/* Config Section */}
          <div className="bg-slate-800 rounded-card border border-slate-700 p-6">
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

            <div className="mt-4 flex items-start gap-2 bg-slate-700/50 rounded-card p-3">
              <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-slate-400">
                Budget settings are configured in workflow YAML files via the{' '}
                <code className="text-blue-300 bg-slate-700 px-1 rounded">budget</code> section.
                The values above are for reference only.
              </p>
            </div>
          </div>

          {/* Recent Runs Table */}
          <div className="bg-slate-800 rounded-card border border-slate-700">
            <div className="px-6 py-4 border-b border-slate-700">
              <h2 className="text-lg font-semibold text-white">Recent Runs</h2>
            </div>

            {!runs || runs.length === 0 ? (
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
                        usage < 70 ? 'bg-green-500' : usage < 90 ? 'bg-amber-500' : 'bg-red-500';

                      return (
                        <tr
                          key={run.run_id}
                          className={isOverBudget ? 'border-l-2 border-l-red-500 bg-red-500/5' : ''}
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
                            <StatusBadge status={run.status} dot />
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
      )}
    </PageShell>
  );
}
