import { useState } from 'react';
import { api } from '../lib/api';
import type { HumanPromptEvent } from '../lib/types';

interface Props {
  prompt: HumanPromptEvent;
  runId: string;
  onDone: () => void;
}

export function HumanPromptModal({ prompt, runId, onDone }: Props) {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (action: string) => {
    setSubmitting(true);
    setError(null);
    try {
      await api.post(`/runs/${runId}/respond`, {
        prompt_id: prompt.prompt_id,
        action,
        text,
      });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <span className="text-2xl">👤</span>
            <div>
              <h3 className="font-bold text-slate-100">
                {prompt.prompt_type === 'approval' ? 'Approval Required' : 'Input Required'}
              </h3>
              <p className="text-sm text-slate-400">
                Node: <span className="font-mono">{prompt.node_id}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-4 space-y-4">
          <p className="text-sm text-slate-200">{prompt.message}</p>

          {/* Show input artifacts as context */}
          {prompt.artifacts.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-slate-400 uppercase">Context</p>
              {prompt.artifacts.map((a) => (
                <div key={a.id} className="bg-slate-900 rounded p-3 text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium text-slate-500">{a.produced_by}</span>
                    <span className="text-xs bg-slate-700 rounded px-1.5 py-0.5">{a.type}</span>
                  </div>
                  <p className="text-slate-200 whitespace-pre-wrap text-xs leading-relaxed max-h-40 overflow-y-auto">
                    {a.content}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* Text input — always shown for input type, shown as feedback for approval */}
          <div>
            <label className="block text-sm font-medium text-slate-200 mb-1">
              {prompt.prompt_type === 'approval' ? 'Feedback (optional, used on reject)' : prompt.message}
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={
                prompt.prompt_type === 'approval'
                  ? 'Add feedback if rejecting...'
                  : 'Type your response...'
              }
              rows={3}
              className="w-full border border-slate-600 rounded-md px-3 py-2 text-sm bg-slate-700 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm bg-red-900/30 rounded p-2">{error}</p>
          )}
        </div>

        {/* Actions */}
        <div className="px-6 py-4 border-t border-slate-700 flex justify-end gap-3">
          {prompt.prompt_type === 'approval' ? (
            <>
              <button
                onClick={() => submit('reject')}
                disabled={submitting}
                className="px-4 py-2 text-sm font-medium text-red-300 bg-red-900/30 border border-red-700 rounded-md hover:bg-red-800/40 disabled:opacity-50"
              >
                Reject
              </button>
              <button
                onClick={() => submit('approve')}
                disabled={submitting}
                className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {submitting ? 'Submitting...' : 'Approve'}
              </button>
            </>
          ) : (
            <button
              onClick={() => submit('input')}
              disabled={submitting || !text.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? 'Submitting...' : 'Submit'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
