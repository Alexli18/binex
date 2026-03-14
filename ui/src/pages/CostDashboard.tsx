import { useState } from 'react';
import { useCostDashboard } from '../hooks/useCostDashboard';
import { DollarSign, TrendingUp, Play, Wallet } from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const PERIODS = ['24h', '7d', '30d', 'all'] as const;

export default function CostDashboard() {
  const [period, setPeriod] = useState<string>('7d');
  const { data, isLoading, error } = useCostDashboard(period);

  if (isLoading) {
    return (
      <div className="p-6">
        <p className="text-slate-400">Loading cost dashboard...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">
          Failed to load dashboard: {(error as Error).message}
        </p>
      </div>
    );
  }

  const budgetUsed = data ? Math.min((data.total_cost / Math.max(data.avg_per_run * data.run_count, 0.01)) * 100, 100) : 0;
  const budgetColor = budgetUsed < 70 ? 'bg-green-500' : budgetUsed < 90 ? 'bg-amber-500' : 'bg-red-500';

  return (
    <div className="p-6 space-y-6 bg-slate-900 min-h-screen">
      {/* Header + Period selector */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Cost Dashboard</h1>
        <div className="flex gap-1 bg-slate-800 rounded-lg p-1">
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
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
          <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
            <DollarSign className="w-4 h-4" />
            Total Cost
          </div>
          <p className="text-2xl font-bold text-white font-mono">
            ${data?.total_cost.toFixed(2) ?? '0.00'}
          </p>
        </div>

        <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
          <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
            <TrendingUp className="w-4 h-4" />
            Avg per Run
          </div>
          <p className="text-2xl font-bold text-white font-mono">
            ${data?.avg_per_run.toFixed(4) ?? '0.00'}
          </p>
        </div>

        <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
          <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
            <Play className="w-4 h-4" />
            Total Runs
          </div>
          <p className="text-2xl font-bold text-white">
            {data?.run_count ?? 0}
          </p>
        </div>

        <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
          <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
            <Wallet className="w-4 h-4" />
            Budget Used
          </div>
          <p className="text-2xl font-bold text-white">
            {budgetUsed.toFixed(0)}%
          </p>
          <div className="mt-2 w-full bg-slate-700 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${budgetColor} transition-all`}
              style={{ width: `${budgetUsed}%` }}
            />
          </div>
        </div>
      </div>

      {/* Cost Trend Chart */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
        <h2 className="text-lg font-semibold text-white mb-4">Cost Trend</h2>
        {data && data.cost_trend.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data.cost_trend}>
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
        {/* Cost by Model */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
          <h2 className="text-lg font-semibold text-white mb-4">Cost by Model</h2>
          {data && data.cost_by_model.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={data.cost_by_model} layout="vertical">
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
            <p className="text-slate-500 text-sm text-center py-12">
              No model cost data
            </p>
          )}
        </div>

        {/* Cost by Node */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
          <h2 className="text-lg font-semibold text-white mb-4">Cost by Node</h2>
          {data && data.cost_by_node.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={data.cost_by_node} layout="vertical">
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
            <p className="text-slate-500 text-sm text-center py-12">
              No node cost data
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
