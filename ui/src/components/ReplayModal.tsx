import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
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
      navigate(`/runs/${result.run_id}/live`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-slate-800 rounded-lg shadow-xl border border-slate-700 w-full max-w-lg max-h-[85vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 mb-4">
          <RotateCcw size={18} className="text-blue-400" />
          <h3 className="text-lg font-semibold text-slate-100">Replay Node</h3>
        </div>

        <div className="space-y-4">
          {/* Node name */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">Node</label>
            <p className="text-sm font-mono text-slate-200 bg-slate-900 rounded px-3 py-1.5">{nodeId}</p>
          </div>

          {/* Input artifacts */}
          {artifacts && artifacts.length > 0 && (
            <div>
              <label className="block text-sm text-slate-400 mb-1">Input Artifacts ({artifacts.length})</label>
              <div className="space-y-1.5 max-h-32 overflow-y-auto">
                {artifacts.map((art) => (
                  <div key={art.id} className="bg-slate-900 rounded px-3 py-2 text-xs">
                    <span className="text-slate-500">{art.type}</span>
                    <p className="text-slate-300 mt-0.5 truncate">{art.content.slice(0, 150)}{art.content.length > 150 ? '...' : ''}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Model selection */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">Model</label>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 shrink-0">current: {currentModel}</span>
            </div>
            <div className="mt-1">
              <ModelSelect value={newModel} onChange={setNewModel} />
            </div>
          </div>

          {/* System prompt (for LLM nodes) */}
          {isLLM && (
            <div>
              <label className="block text-sm text-slate-400 mb-1">System Prompt</label>
              <textarea
                value={newPrompt}
                onChange={(e) => setNewPrompt(e.target.value)}
                placeholder="Enter new system prompt..."
                rows={4}
                className="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 resize-none focus:outline-none focus:border-blue-500"
              />
              {currentPrompt && (
                <button
                  onClick={() => setNewPrompt(currentPrompt)}
                  className="text-xs text-blue-400 hover:text-blue-300 mt-1"
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
          <button onClick={onClose} className="px-4 py-1.5 text-sm border border-slate-600 rounded text-slate-300 hover:bg-slate-700">
            Cancel
          </button>
          <button
            onClick={handleReplay}
            disabled={submitting}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50 flex items-center gap-1.5"
          >
            <RotateCcw size={14} />
            {submitting ? 'Replaying...' : 'Replay from this node'}
          </button>
        </div>
      </div>
    </div>
  );
}
