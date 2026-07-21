import { useState } from 'react';
import { RotateCcw, Loader2, X } from 'lucide-react';
import { ModelSelect } from './editor/ModelSelect';
import { replayCall, type ReplayCallResult } from '../lib/api';

interface CallReplayModalProps {
  runId: string;
  callId: string;
  originalModel: string;
  onClose: () => void;
}

/** Stateless replay of one captured LLM call from an observed run (#74). */
export function CallReplayModal({ runId, callId, originalModel, onClose }: CallReplayModalProps) {
  const [model, setModel] = useState(originalModel);
  const [prompt, setPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReplayCallResult | null>(null);

  const handleReplay = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await replayCall(runId, callId, {
        model: model !== originalModel ? model : undefined,
        prompt: prompt.trim() ? prompt : undefined,
      });
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={submitting ? undefined : onClose}
    >
      <div
        className="bg-[#131315] rounded-modal shadow-xl border border-[#252528]/60 w-full max-w-3xl max-h-[85vh] overflow-y-auto p-6 relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold flex items-center gap-2">
            <RotateCcw size={14} className="text-amber-400" />
            Replay call <span className="font-mono text-[#80808a]">{callId}</span>
          </h2>
          <button onClick={onClose} className="text-[#4a4a52] hover:text-[#80808a]">
            <X size={16} />
          </button>
        </div>

        {/* Overrides */}
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-[#80808a] mb-1">Model</label>
            <ModelSelect value={model} onChange={setModel} />
          </div>
          <div>
            <label className="block text-xs text-[#80808a] mb-1">
              Replace user prompt (optional)
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Leave empty to reuse the captured messages as-is"
              rows={3}
              className="w-full rounded bg-[#252528] border border-[#333338] text-[#f0f0f0] text-xs p-2 font-mono"
            />
          </div>
          <button
            onClick={handleReplay}
            disabled={submitting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm border border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-400/20 disabled:opacity-50 transition-colors"
          >
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
            {submitting ? 'Replaying…' : 'Replay'}
          </button>
        </div>

        {error && <p className="mt-3 text-xs text-red-400">{error}</p>}

        {/* Comparison */}
        {result && (
          <div className="mt-5 space-y-3">
            <div className="flex items-center gap-3 text-xs">
              <span
                className={
                  result.changed
                    ? 'rounded bg-amber-400/10 px-2 py-0.5 text-amber-400'
                    : 'rounded bg-emerald-400/10 px-2 py-0.5 text-emerald-400'
                }
              >
                {result.changed ? 'CHANGED' : 'identical'}
              </span>
              {result.original_model !== result.replay_model && (
                <span className="font-mono text-[#80808a]">
                  {result.original_model} → {result.replay_model}
                </span>
              )}
              {result.cost != null && (
                <span className="text-[#4a4a52]">
                  replay cost ${result.cost.toFixed(4)} (experimentation)
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-[#4a4a52] mb-1">original</div>
                <pre className="text-xs text-[#80808a] bg-[#1a1a1d] border border-[#252528] rounded p-2 whitespace-pre-wrap break-words max-h-64 overflow-y-auto">
                  {result.original_response}
                </pre>
              </div>
              <div>
                <div className="text-xs text-amber-400 mb-1">replay</div>
                <pre className="text-xs text-[#80808a] bg-[#1a1a1d] border border-amber-500/20 rounded p-2 whitespace-pre-wrap break-words max-h-64 overflow-y-auto">
                  {result.replay_response}
                </pre>
              </div>
            </div>

            {result.tool_requests.length > 0 && (
              <div className="text-xs">
                <div className="text-[#4a4a52] mb-1">
                  Replay requested tool calls (not executed):
                </div>
                <ul className="space-y-0.5 font-mono text-[#80808a]">
                  {result.tool_requests.map((t, i) => (
                    <li key={i}>
                      {t.name}({t.arguments})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
