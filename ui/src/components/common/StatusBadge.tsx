import { cn } from '@/lib/utils';
import { getStatusColors } from '../../lib/design-tokens';

interface StatusBadgeProps {
  status: string;
  /** Optional size variant */
  size?: 'sm' | 'md';
  /** Show a small colored dot before the label */
  dot?: boolean;
  className?: string;
}

export function StatusBadge({
  status,
  size = 'sm',
  dot = true,
  className,
}: StatusBadgeProps) {
  const tokens = getStatusColors(status);
  const isRunning = status === 'running';

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-badge border font-medium select-none',
        tokens.bg,
        tokens.text,
        tokens.border,
        size === 'sm' && 'px-2 py-0.5 text-xs',
        size === 'md' && 'px-2.5 py-1 text-body-sm',
        className,
      )}
    >
      {dot && (
        <span
          className={cn(
            'inline-block h-1.5 w-1.5 rounded-full shrink-0',
            tokens.dot,
            isRunning && 'animate-pulse-status',
          )}
        />
      )}
      {status}
    </span>
  );
}
