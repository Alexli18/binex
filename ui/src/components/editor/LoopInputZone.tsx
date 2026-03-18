import { ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LoopInputZoneProps {
  entryLabels: string[];
  connectedFrom?: string;
  onClick?: () => void;
}

export function LoopInputZone({ entryLabels, connectedFrom, onClick }: LoopInputZoneProps) {
  const label = entryLabels.length > 0
    ? entryLabels.join(', ')
    : 'no entry node';

  return (
    <div
      className={cn(
        'mx-3 mt-1 mb-0',
        'flex items-center gap-2',
        'h-6',
        'cursor-pointer',
        'group',
      )}
      onClick={onClick}
      title={connectedFrom
        ? `Receives data from: ${connectedFrom}`
        : 'No external input connected'}
    >
      <span className={cn(
        'text-[10px] font-semibold tracking-wider uppercase',
        'text-teal-500/70 group-hover:text-teal-400',
        'transition-colors',
        'shrink-0',
        'select-none',
      )}>
        &#x25B8; input
      </span>

      <div className="flex-1 border-t border-dashed border-teal-500/25 group-hover:border-teal-500/40 transition-colors" />

      <div className="flex items-center gap-1 shrink-0">
        <ArrowRight size={10} className="text-teal-500/40" />
        <span className={cn(
          'text-[10px] text-slate-500 group-hover:text-slate-400',
          'transition-colors font-mono',
          entryLabels.length === 0 && 'text-amber-500/60',
        )}>
          {label}
        </span>
      </div>
    </div>
  );
}
