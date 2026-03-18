import { Check, AlertTriangle } from 'lucide-react';
import type { ExitCondition } from '@/lib/loop-types';
import { cn } from '@/lib/utils';

interface LoopFooterBadgeProps {
  exitCondition: ExitCondition | null;
  maxIterations: number;
  childCount: number;
}

export function LoopFooterBadge({ exitCondition, maxIterations, childCount }: LoopFooterBadgeProps) {
  const hasCondition = exitCondition && exitCondition.field.trim() && String(exitCondition.value).trim();

  if (childCount === 0) {
    return (
      <div className={cn(
        'mx-3 mb-2 px-3 py-1.5 rounded-md',
        'bg-amber-500/10 border border-amber-500/30',
        'text-[11px] text-amber-400 flex items-center gap-1.5',
      )}>
        <AlertTriangle size={11} />
        empty loop
      </div>
    );
  }

  if (!hasCondition) {
    return (
      <div className={cn(
        'mx-3 mb-2 px-3 py-1.5 rounded-md',
        'bg-red-500/10 border border-red-500/30',
        'text-[11px] text-red-400 flex items-center gap-1.5',
      )}>
        <AlertTriangle size={11} />
        no exit condition | max: {maxIterations}
      </div>
    );
  }

  const fieldName = exitCondition.field.replace('$.', '');
  return (
    <div className={cn(
      'mx-3 mb-2 px-3 py-1.5 rounded-md',
      'bg-emerald-500/10 border border-emerald-500/30',
      'text-[11px] text-emerald-400 flex items-center gap-1.5',
    )}>
      <Check size={11} />
      exit: {fieldName} {exitCondition.operator} {exitCondition.value} | max: {maxIterations}
    </div>
  );
}
