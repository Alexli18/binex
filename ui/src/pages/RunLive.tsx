import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { HumanPromptModal } from '../components/HumanPromptModal';
import { CaoInputModal } from '../components/cao/CaoInputModal';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingState } from '@/components/layout/LoadingState';
import { useRun, useCancelRun } from '../hooks/useRuns';
import { useSSE } from '../hooks/useSSE';
import type { RunEvent } from '../lib/types';
import { X } from 'lucide-react';
import { toast } from 'sonner';

function EventLogItem({ event }: { event: RunEvent }) {
  const time = new Date(event.timestamp).toLocaleTimeString();
  return (
    <div className="flex items-start gap-3 py-2 px-3 border-b border-[#252528] text-sm">
      <span className="text-[#80808a] font-mono text-xs shrink-0">{time}</span>
      <StatusBadge status={event.type.split(':')[1] || event.type} />
      {event.node_id && (
        <span className="font-mono text-xs text-[#f0f0f0]">{event.node_id}</span>
      )}
      {event.error && <span className="text-red-400 text-xs">{event.error}</span>}
      {event.cost !== undefined && event.cost > 0 && (
        <span className="text-[#80808a] text-xs ml-auto">${event.cost.toFixed(4)}</span>
      )}
    </div>
  );
}

/** Live elapsed timer for running CAO nodes — updates every second. */
function CaoLiveTimer({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = new Date(startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;

  return (
    <span className="text-xs font-mono text-amber-400 ml-auto shrink-0">
      {mins}m {secs}s
    </span>
  );
}

export default function RunLive() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run, isLoading } = useRun(runId);
  const { events, connected, pendingPrompt, clearPrompt, pendingCaoPrompt, clearCaoPrompt, outputResult, clearOutput } = useSSE(runId);
  const cancelRun = useCancelRun();
  const logRef = useRef<HTMLDivElement>(null);

  // Auto-scroll event log to bottom
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  // Auto-redirect when run completes or is cancelled (but not if output modal is showing)
  useEffect(() => {
    const lastEvent = events[events.length - 1];
    if (lastEvent && (lastEvent.type === 'run:completed' || lastEvent.type === 'run:cancelled')) {
      if (lastEvent.status === 'failed') {
        toast.error('Run failed');
      } else if (lastEvent.type === 'run:cancelled') {
        toast.warning('Run cancelled');
      } else {
        toast.success('Run completed');
      }
      if (outputResult) return; // Don't redirect while user is viewing output
      const timer = setTimeout(() => navigate(`/runs/${runId}`), 1500);
      return () => clearTimeout(timer);
    }
  }, [events, navigate, runId, outputResult]);

  // Build node status map from events (with start timestamps and agent info)
  const nodeStatuses = useMemo(() => {
    const statuses: Record<string, { status: string; startedAt?: string; agent?: string }> = {};
    for (const event of events) {
      if (event.node_id) {
        if (event.type === 'node:started') {
          statuses[event.node_id] = {
            status: 'running',
            startedAt: event.timestamp,
            agent: (event as RunEvent & { agent?: string }).agent,
          };
        } else if (event.type === 'node:completed') {
          statuses[event.node_id] = { ...statuses[event.node_id], status: 'completed' };
        } else if (event.type === 'node:failed') {
          statuses[event.node_id] = { ...statuses[event.node_id], status: 'failed' };
        }
      }
    }
    return statuses;
  }, [events]);

  const handleCancel = () => {
    if (runId) cancelRun.mutate(runId);
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <LoadingState message="Loading run..." />
      </div>
    );
  }

  if (!run) {
    // Check if we received an error event via SSE before run was created
    const failEvent = events.find(
      (e) => e.type === 'run:completed' && e.status === 'failed',
    );
    if (failEvent) {
      return (
        <div className="p-6">
          <h2 className="text-xl font-bold text-red-400 mb-2">Run Failed</h2>
          <p className="text-[#80808a] bg-red-900/30 border border-red-700 rounded p-3 text-sm font-mono whitespace-pre-wrap">
            {failEvent.error || 'Unknown error'}
          </p>
          <button
            onClick={() => navigate('/editor')}
            className="mt-4 px-4 py-2 text-sm bg-[#252528] text-[#f0f0f0] rounded hover:bg-[#333338]"
          >
            Back to Editor
          </button>
        </div>
      );
    }
    return (
      <div className="p-6">
        <p className="text-[#80808a]">Waiting for run to start...</p>
      </div>
    );
  }

  const isTerminal = events.some(
    (e) => e.type === 'run:completed' || e.type === 'run:cancelled',
  );

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold">Live: {runId}</h2>
          <StatusBadge status={run.status} />
          <span
            className={`inline-flex items-center gap-1 text-xs ${connected ? 'text-green-600' : 'text-red-500'}`}
          >
            <span
              className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}
            />
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <button
          onClick={handleCancel}
          disabled={isTerminal || cancelRun.isPending}
          className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {cancelRun.isPending ? 'Cancelling...' : 'Cancel Run'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Node status summary */}
        <div className="lg:col-span-2">
          <div className="bg-[#1a1a1d] border border-[#252528] rounded-card p-4">
            <h3 className="text-sm font-semibold text-[#f0f0f0] mb-3">Node Status</h3>
            {Object.keys(nodeStatuses).length === 0 ? (
              <p className="text-[#80808a] text-sm">Waiting for events...</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(nodeStatuses).map(([nodeId, info]) => (
                  <div
                    key={nodeId}
                    className="flex items-center gap-2 bg-[#252528] rounded px-3 py-2"
                  >
                    <StatusBadge status={info.status} />
                    <span className="font-mono text-xs truncate">{nodeId}</span>
                    {info.status === 'running' && info.agent?.startsWith('cao://') && info.startedAt && (
                      <CaoLiveTimer startedAt={info.startedAt} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Event log */}
        <div className="lg:col-span-1">
          <div className="bg-[#1a1a1d] border border-[#252528] rounded-card">
            <div className="px-4 py-3 border-b border-[#252528]">
              <h3 className="text-sm font-semibold text-[#f0f0f0]">
                Event Log ({events.length})
              </h3>
            </div>
            <div ref={logRef} className="max-h-[500px] overflow-y-auto">
              {events.length === 0 ? (
                <p className="text-[#80808a] text-sm p-4">No events yet...</p>
              ) : (
                events.map((event, i) => (
                  <EventLogItem
                    key={`${event.timestamp}-${event.node_id ?? event.type}-${i}`}
                    event={event}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Human-in-the-loop prompt modal */}
      {pendingPrompt && runId && (
        <HumanPromptModal
          prompt={pendingPrompt}
          runId={runId}
          onDone={clearPrompt}
        />
      )}

      {/* CAO agent waiting-for-input modal */}
      {pendingCaoPrompt && (
        <CaoInputModal
          prompt={pendingCaoPrompt}
          onDone={clearCaoPrompt}
        />
      )}

      {/* Workflow output display */}
      {outputResult && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={clearOutput}>
          <div
            className="bg-[#131315] rounded-modal shadow-xl border border-[#252528]/60 w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#252528]/60">
              <h3 className="text-lg font-semibold text-amber-400">{outputResult.label}</h3>
              <button
                onClick={clearOutput}
                className="p-1 rounded text-[#80808a] hover:text-[#f0f0f0] hover:bg-[#252528] transition-colors"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-6 overflow-y-auto space-y-4">
              {outputResult.artifacts.map((art, i) => (
                <div key={i} className="bg-[#131315] rounded-lg p-4 border border-[#252528]">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs text-[#4a4a52]">{art.type}</span>
                    {art.produced_by && (
                      <span className="text-xs text-[#4a4a52]">from {art.produced_by}</span>
                    )}
                  </div>
                  <pre className="text-sm text-[#f0f0f0] whitespace-pre-wrap break-words font-mono">
                    {art.content}
                  </pre>
                </div>
              ))}
            </div>
            <div className="px-6 py-4 border-t border-[#252528]/60 flex justify-end">
              <button
                onClick={clearOutput}
                className="px-4 py-1.5 text-sm bg-amber-500 text-black rounded hover:bg-amber-400"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
