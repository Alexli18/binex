import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RotateCcw, Loader2 } from 'lucide-react';
import { ModelSelect } from './editor/ModelSelect';
import { api } from '../lib/api';
import type { DebugArtifact } from '../hooks/useAnalysis';

interface ReplayModalProps {
  runId: string;
  nodeId: string;
  currentAgent: string;
  currentPrompt?: string;
  workflowPath: string | null;
  artifacts?: DebugArtifact[];
  onClose: () => void;
}

export function ReplayModal({
  runId, nodeId, currentAgent, currentPrompt, workflowPath, artifacts, onClose,
}: ReplayModalProps) {
  const navigate = useNavigate();
  const currentModel = currentAgent.includes('://') ? currentAgent.split('://')[1] : currentAgent;
  const isLLM = currentAgent.startsWith('llm://');

  const [newModel, setNewModel] = useState(currentModel);
  const [newPrompt, setNewPrompt] = useState(currentPrompt || '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleReplay = async () => {
    if (!workflowPath) {
      setError('Workflow path not available');
      return;
    }
    setSubmitting(true);
    setError(null);

    const agentSwaps: Record<string, string> = {};
    if (newModel !== currentModel) {
      const prefix = currentAgent.split('://')[0] || 'llm';
      agentSwaps[nodeId] = `${prefix}://${newModel}`;
    }

    // TODO: prompt swaps require backend support — for now just swap model
    try {
      const result = await api.post<{ run_id: string; status: string }>('/runs/replay', {
        run_id: runId,
        from_step: nodeId,
        workflow_path: workflowPath,
        agent_swaps: agentSwaps,
      });
      onClose();
      navigate(`/runs/${result.run_id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={submitting ? undefined : onClose}>
      <div
        className="bg-[#131315] rounded-modal shadow-xl border border-[#252528]/60 w-full max-w-lg max-h-[85vh] overflow-y-auto p-6 relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Loading overlay */}
        {submitting && (
          <div className="absolute inset-0 bg-[#131315]/80 rounded-lg flex flex-col items-center justify-center z-10 gap-3">
            <Loader2 size={32} className="text-amber-400 animate-spin" />
            <p className="text-sm text-[#80808a]">Replaying node...</p>
            <p className="text-xs text-[#4a4a52]">This may take a few seconds</p>
          </div>
        )}

        <div className="flex items-center gap-2 mb-4">
          <RotateCcw size={18} className="text-amber-400" />
          <h3 className="text-lg font-semibold text-[#f0f0f0]">Replay Node</h3>
        </div>

        <div className="space-y-4">
          {/* Node name */}
          <div>
            <label className="block text-sm text-[#80808a] mb-1">Node</label>
            <p className="text-sm font-mono text-[#f0f0f0] bg-[#131315] rounded px-3 py-1.5">{nodeId}</p>
          </div>

          {/* Input artifacts */}
          {artifacts && artifacts.length > 0 && (
            <div>
              <label className="block text-sm text-[#80808a] mb-1">Input Artifacts ({artifacts.length})</label>
              <div className="space-y-1.5 max-h-32 overflow-y-auto">
                {artifacts.map((art) => {
                  const text =
                    typeof art.content === 'string'
                      ? art.content
                      : JSON.stringify(art.content ?? '');
                  return (
                    <div key={art.id} className="bg-[#131315] rounded px-3 py-2 text-xs">
                      <span className="text-[#4a4a52]">{art.type}</span>
                      <p className="text-[#80808a] mt-0.5 truncate">
                        {text.slice(0, 150)}
                        {text.length > 150 ? '...' : ''}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Model selection */}
          <div>
            <label className="block text-sm text-[#80808a] mb-1">Model</label>
            <div className="flex items-center gap-2">
              <span className="text-xs text-[#4a4a52] shrink-0">current: {currentModel}</span>
            </div>
            <div className="mt-1">
              <ModelSelect value={newModel} onChange={setNewModel} />
            </div>
          </div>

          {/* System prompt (for LLM nodes) */}
          {isLLM && (
            <div>
              <label className="block text-sm text-[#80808a] mb-1">System Prompt</label>
              <textarea
                value={newPrompt}
                onChange={(e) => setNewPrompt(e.target.value)}
                placeholder="Enter new system prompt..."
                rows={4}
                className="w-full bg-[#252528] border border-[#333338] rounded px-3 py-2 text-sm text-[#f0f0f0] resize-none focus:outline-none focus:border-amber-500"
              />
              {currentPrompt && (
                <button
                  onClick={() => setNewPrompt(currentPrompt)}
                  className="text-xs text-amber-400 hover:text-amber-300 mt-1"
                >
                  Reset to original
                </button>
              )}
            </div>
          )}

          {error && (
            <p className="text-red-400 text-sm bg-red-900/30 rounded p-2">{error}</p>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onClose} className="px-4 py-1.5 text-sm border border-[#333338] rounded text-[#80808a] hover:bg-[#252528]">
            Cancel
          </button>
          <button
            onClick={handleReplay}
            disabled={submitting}
            className="px-4 py-1.5 text-sm bg-amber-500 text-white rounded hover:bg-amber-400 disabled:opacity-50 flex items-center gap-1.5"
          >
            <RotateCcw size={14} />
            {submitting ? 'Replaying...' : 'Replay from this node'}
          </button>
        </div>
      </div>
    </div>
  );
}
