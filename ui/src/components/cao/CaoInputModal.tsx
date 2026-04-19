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
      <div className="bg-[#131315] rounded-lg shadow-xl border border-[#252528]/60 max-w-lg w-full mx-4">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#252528]">
          <h3 className="font-bold text-[#f0f0f0]">CAO Agent Waiting for Input</h3>
          <p className="text-sm text-[#80808a] mt-1">
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
            className="w-full bg-[#1a1a1d] border border-[#333338] rounded-md px-3 py-2 text-sm text-[#f0f0f0] placeholder:text-[#4a4a52] focus:outline-none focus:ring-2 focus:ring-amber-500/50"
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
        <div className="px-6 py-3 border-t border-[#252528] flex justify-end gap-2">
          <button
            onClick={submit}
            disabled={submitting || !text.trim()}
            className="px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 rounded-md text-sm font-medium text-black"
          >
            {submitting ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
