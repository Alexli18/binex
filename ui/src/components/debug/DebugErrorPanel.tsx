import { AlertTriangle } from 'lucide-react';

export interface DebugErrorPanelProps {
  error: string;
}

export function DebugErrorPanel({ error }: DebugErrorPanelProps) {
  // Try to detect if it looks like a stack trace
  const isStackTrace = error.includes('\n') && (error.includes('Traceback') || error.includes('at ') || error.includes('File '));

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1">
        <AlertTriangle size={14} className="text-red-400" />
        <span className="text-sm text-slate-500">Error</span>
      </div>
      <div className="mt-1 rounded-md bg-red-900/30 border border-red-700/50 p-3 text-sm text-red-300 font-mono whitespace-pre-wrap break-words">
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
