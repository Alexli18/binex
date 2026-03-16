import { Info } from 'lucide-react';

export function BudgetStatus({ budgetLimit }: { budgetLimit?: number }) {
  return (
    <div className="bg-slate-900 rounded-card border border-slate-700/60 p-6">
      <h2 className="text-sm font-semibold text-slate-100 mb-4">Budget Configuration</h2>

      <div className="flex items-start gap-3 bg-slate-800/50 rounded-card p-4">
        <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
        <div className="text-sm text-slate-300 space-y-2">
          {budgetLimit && budgetLimit > 0 ? (
            <p>
              Current budget limit: <span className="font-mono text-slate-100">${budgetLimit.toFixed(2)}</span>
            </p>
          ) : (
            <p>No budget limit configured for recent workflows.</p>
          )}
          <p>
            Budget limits are configured per workflow in the YAML file via the{' '}
            <code className="text-blue-300 bg-slate-700 px-1.5 py-0.5 rounded">budget</code> section:
          </p>
          <pre className="bg-slate-950 rounded-lg p-3 text-xs text-slate-400 font-mono overflow-x-auto">
{`budget:
  max_cost: 1.00      # Maximum cost in USD
  policy: stop        # "stop" or "warn"`}
          </pre>
          <p className="text-slate-400">
            <strong className="text-slate-300">stop</strong> — skips remaining nodes when budget exceeded.{' '}
            <strong className="text-slate-300">warn</strong> — logs a warning but continues execution.
          </p>
        </div>
      </div>
    </div>
  );
}
