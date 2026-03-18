import { ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ExitCondition } from '@/lib/loop-types';

interface LoopOutputZoneProps {
  exitLabels: string[];
  exitCondition: ExitCondition | null;
  onClick?: () => void;
}

export function LoopOutputZone({ exitLabels, exitCondition, onClick }: LoopOutputZoneProps) {
  const label = exitLabels.length > 0
    ? exitLabels.join(', ')
    : 'no exit node';

  const conditionText = exitCondition?.field
    ? `${exitCondition.field.replace('$.', '')} ${exitCondition.operator} ${exitCondition.value}`
    : null;

  return (
    <div
      className={cn(
        'mx-3 mb-1 mt-0',
        'flex items-center gap-2',
        'h-6',
        'cursor-pointer',
        'group',
      )}
      onClick={onClick}
      title={conditionText
        ? `Exit when: ${exitCondition!.field} ${exitCondition!.operator} ${exitCondition!.value}`
        : 'No exit condition set'}
    >
      <div className="flex items-center gap-1 shrink-0">
        <span className={cn(
          'text-[10px] text-slate-500 group-hover:text-slate-400',
          'transition-colors font-mono',
          exitLabels.length === 0 && 'text-amber-500/60',
        )}>
          {label}
        </span>
        <ArrowRight size={10} className="text-teal-500/40" />
      </div>

      <div className="flex-1 border-t border-dashed border-teal-500/25 group-hover:border-teal-500/40 transition-colors" />

      <div className="flex items-center gap-1.5 shrink-0">
        <span className={cn(
          'text-[10px] font-semibold tracking-wider uppercase',
          'text-teal-500/70 group-hover:text-teal-400',
          'transition-colors',
          'select-none',
        )}>
          output &#x25C2;
        </span>
        {conditionText && (
          <span className="text-[9px] text-emerald-500/60 font-mono">
            {conditionText}
          </span>
        )}
      </div>
    </div>
  );
}
