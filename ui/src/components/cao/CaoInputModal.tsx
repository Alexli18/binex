import { useState } from 'react';
import { sendCaoTerminalInput } from '@/lib/api';

export interface CaoPromptEvent {
  terminal_id: string;
  node_id?: string;
  prompt_number: number;
}

interface Props {
  prompt: CaoPromptEvent;
  onDone: () => void;
}

export function CaoInputModal({ prompt, onDone }: Props) {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await sendCaoTerminalInput(prompt.terminal_id, text);
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-900 rounded-lg shadow-xl border border-slate-700/60 max-w-lg w-full mx-4">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-700">
          <h3 className="font-bold text-slate-100">CAO Agent Waiting for Input</h3>
          <p className="text-sm text-slate-400 mt-1">
            Terminal: <span className="font-mono">{prompt.terminal_id}</span>
            {prompt.node_id && (
              <> &middot; Node: <span className="font-mono">{prompt.node_id}</span></>
            )}
          </p>
        </div>

        {/* Content */}
        <div className="px-6 py-4 space-y-4">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type your response..."
            rows={4}
            className="w-full bg-slate-800 border border-slate-600 rounded-md px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit();
            }}
          />

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-700 flex justify-end gap-2">
          <button
            onClick={submit}
            disabled={submitting || !text.trim()}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 rounded-md text-sm font-medium text-white"
          >
            {submitting ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
