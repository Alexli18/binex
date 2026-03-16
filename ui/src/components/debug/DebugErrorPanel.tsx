import { AlertTriangle } from 'lucide-react';
import { statusColors } from '@/lib/design-tokens';

export interface DebugErrorPanelProps {
  error: string;
}

export function DebugErrorPanel({ error }: DebugErrorPanelProps) {
  // Try to detect if it looks like a stack trace
  const isStackTrace = error.includes('\n') && (error.includes('Traceback') || error.includes('at ') || error.includes('File '));

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1">
        <AlertTriangle size={14} className={statusColors.failed.text} />
        <span className="text-sm text-slate-500">Error</span>
      </div>
      <div className={`mt-1 rounded-md ${statusColors.failed.bg} border ${statusColors.failed.border} p-3 text-sm ${statusColors.failed.text} font-mono whitespace-pre-wrap break-words`}>
        {error}
      </div>
      {isStackTrace && (
        <p className="mt-1.5 text-xs text-slate-500">
          Tip: Check the stack trace above for the root cause. The last line usually contains the error message.
        </p>
      )}
    </div>
  );
}
