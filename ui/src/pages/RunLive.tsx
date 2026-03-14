import { useEffect, useMemo, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { HumanPromptModal } from '../components/HumanPromptModal';
import { StatusBadge } from '../components/common/StatusBadge';
import { useRun, useCancelRun } from '../hooks/useRuns';
import { useSSE } from '../hooks/useSSE';
import type { RunEvent } from '../lib/types';

function EventLogItem({ event }: { event: RunEvent }) {
  const time = new Date(event.timestamp).toLocaleTimeString();
  return (
    <div className="flex items-start gap-3 py-2 px-3 border-b border-gray-100 text-sm">
      <span className="text-gray-400 font-mono text-xs shrink-0">{time}</span>
      <StatusBadge status={event.type.split(':')[1] || event.type} />
      {event.node_id && (
        <span className="font-mono text-xs text-gray-700">{event.node_id}</span>
      )}
      {event.error && <span className="text-red-600 text-xs">{event.error}</span>}
      {event.cost !== undefined && event.cost > 0 && (
        <span className="text-gray-500 text-xs ml-auto">${event.cost.toFixed(4)}</span>
      )}
    </div>
  );
}

export default function RunLive() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run, isLoading } = useRun(runId);
  const { events, connected, pendingPrompt, clearPrompt } = useSSE(runId);
  const cancelRun = useCancelRun();
  const logRef = useRef<HTMLDivElement>(null);

  // Auto-scroll event log to bottom
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  // Auto-redirect when run completes or is cancelled
  useEffect(() => {
    const lastEvent = events[events.length - 1];
    if (lastEvent && (lastEvent.type === 'run:completed' || lastEvent.type === 'run:cancelled')) {
      const timer = setTimeout(() => navigate(`/runs/${runId}`), 1500);
      return () => clearTimeout(timer);
    }
  }, [events, navigate, runId]);

  // Build node status map from events
  const nodeStatuses = useMemo(() => {
    const statuses: Record<string, string> = {};
    for (const event of events) {
      if (event.node_id) {
        if (event.type === 'node:started') statuses[event.node_id] = 'running';
        else if (event.type === 'node:completed') statuses[event.node_id] = 'completed';
        else if (event.type === 'node:failed') statuses[event.node_id] = 'failed';
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
        <p className="text-gray-500">Loading run...</p>
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
          <p className="text-slate-300 bg-red-900/30 border border-red-700 rounded p-3 text-sm font-mono whitespace-pre-wrap">
            {failEvent.error || 'Unknown error'}
          </p>
          <button
            onClick={() => navigate('/editor')}
            className="mt-4 px-4 py-2 text-sm bg-slate-700 text-slate-200 rounded hover:bg-slate-600"
          >
            Back to Editor
          </button>
        </div>
      );
    }
    return (
      <div className="p-6">
        <p className="text-slate-400">Waiting for run to start...</p>
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
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Node Status</h3>
            {Object.keys(nodeStatuses).length === 0 ? (
              <p className="text-gray-400 text-sm">Waiting for events...</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(nodeStatuses).map(([nodeId, status]) => (
                  <div
                    key={nodeId}
                    className="flex items-center gap-2 bg-gray-50 rounded px-3 py-2"
                  >
                    <StatusBadge status={status} />
                    <span className="font-mono text-xs truncate">{nodeId}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Event log */}
        <div className="lg:col-span-1">
          <div className="bg-white border border-gray-200 rounded-lg">
            <div className="px-4 py-3 border-b border-gray-200">
              <h3 className="text-sm font-semibold text-gray-700">
                Event Log ({events.length})
              </h3>
            </div>
            <div ref={logRef} className="max-h-[500px] overflow-y-auto">
              {events.length === 0 ? (
                <p className="text-gray-400 text-sm p-4">No events yet...</p>
              ) : (
                events.map((event, i) => <EventLogItem key={i} event={event} />)
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
    </div>
  );
}
