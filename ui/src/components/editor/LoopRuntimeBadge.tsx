import { RefreshCw } from 'lucide-react';
import type { ExitCondition } from '@/lib/loop-types';
import { cn } from '@/lib/utils';

interface LoopRuntimeBadgeProps {
  currentIteration: number;
  maxIterations: number;
  exitCondition: ExitCondition | null;
  currentValue?: string;
  totalCost?: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export function LoopRuntimeBadge({
  currentIteration,
  maxIterations,
  exitCondition,
  currentValue,
  totalCost,
  status,
}: LoopRuntimeBadgeProps) {
  const progress = (currentIteration / maxIterations) * 100;

  return (
    <div
      className={cn(
        'mx-3 mb-2 px-3 py-2 rounded-md space-y-1.5',
        status === 'running' && 'bg-blue-500/10 border border-blue-500/20',
        status === 'completed' && 'bg-emerald-500/10 border border-emerald-500/20',
        status === 'failed' && 'bg-red-500/10 border border-red-500/20',
        status === 'pending' && 'bg-slate-500/10 border border-slate-500/20',
      )}
    >
      {/* Iteration counter */}
      <div className="flex items-center justify-between text-[11px]">
        <span
          className={cn(
            'flex items-center gap-1 font-medium',
            status === 'running' && 'text-blue-400',
            status === 'completed' && 'text-emerald-400',
            status === 'failed' && 'text-red-400',
            status === 'pending' && 'text-slate-400',
          )}
        >
          <RefreshCw
            size={11}
            className={status === 'running' ? 'animate-spin' : ''}
          />
          iteration {currentIteration} / {maxIterations}
        </span>
        {totalCost != null && (
          <span className="text-slate-500 font-mono">
            ${(totalCost ?? 0).toFixed(4)}
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            status === 'running' && 'bg-blue-500',
            status === 'completed' && 'bg-emerald-500',
            status === 'failed' && 'bg-red-500',
            status === 'pending' && 'bg-slate-500',
          )}
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>

      {/* Current value vs target */}
      {currentValue && exitCondition && (
        <div className="text-[10px] text-slate-400 font-mono">
          {exitCondition.jsonpath.replace('$.', '')}: {currentValue} →{' '}
          <span className="text-slate-300">
            {exitCondition.operator} {exitCondition.value}
          </span>
        </div>
      )}
    </div>
  );
}
