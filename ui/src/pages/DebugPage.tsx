import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { CheckCircle2, XCircle, Clock, SkipForward, Search, RotateCcw } from 'lucide-react';
import { useDebug } from '../hooks/useAnalysis';
import type { DebugNode } from '../hooks/useAnalysis';
import { ReplayModal } from '../components/ReplayModal';

const statusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <CheckCircle2 size={16} className="text-green-400" />;
    case 'failed':
      return <XCircle size={16} className="text-red-400" />;
    case 'running':
      return <Clock size={16} className="text-blue-400 animate-pulse" />;
    case 'skipped':
      return <SkipForward size={16} className="text-slate-500" />;
    default:
      return <Clock size={16} className="text-slate-500" />;
  }
};

const statusColor = (status: string) => {
  switch (status) {
    case 'completed':
      return 'border-green-500/30 bg-green-500/5';
    case 'failed':
      return 'border-red-500/30 bg-red-500/5';
    case 'running':
      return 'border-blue-500/30 bg-blue-500/5';
    case 'skipped':
      return 'border-slate-600/30 bg-slate-600/5';
    default:
      return 'border-slate-700/30 bg-slate-700/5';
  }
};

function NodeDetail({ node }: { node: DebugNode }) {
  const [expandedArtifact, setExpandedArtifact] = useState<number | null>(null);

  return (
    <div className="space-y-4">
      {/* Status & timing */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <span className="text-slate-500">Status</span>
          <div className="flex items-center gap-2 mt-1">
            {statusIcon(node.status)}
            <span className="capitalize">{node.status}</span>
          </div>
        </div>
        <div>
          <span className="text-slate-500">Duration</span>
          <p className="mt-1 font-mono">
            {node.duration_s !== null ? `${node.duration_s.toFixed(3)}s` : '-'}
          </p>
        </div>
        <div>
          <span className="text-slate-500">Started</span>
          <p className="mt-1 text-xs font-mono text-slate-400">
            {node.started_at ?? '-'}
          </p>
        </div>
        <div>
          <span className="text-slate-500">Completed</span>
          <p className="mt-1 text-xs font-mono text-slate-400">
            {node.completed_at ?? '-'}
          </p>
        </div>
      </div>

      {/* Agent / Model / Prompt */}
      {(node.agent || node.model || node.system_prompt) && (
        <div className="space-y-2 border-t border-slate-700 pt-3">
          {node.agent && (
            <div>
              <span className="text-sm text-slate-500">Agent</span>
              <p className="mt-0.5 text-xs font-mono text-slate-300">{node.agent}</p>
            </div>
          )}
          {node.model && (
            <div>
              <span className="text-sm text-slate-500">Model</span>
              <p className="mt-0.5 text-xs font-mono text-blue-400">{node.model}</p>
            </div>
          )}
          {node.system_prompt && (
            <div>
              <span className="text-sm text-slate-500">System Prompt</span>
              <pre className="mt-0.5 text-xs text-slate-400 bg-slate-900 rounded p-2 whitespace-pre-wrap max-h-24 overflow-y-auto">
                {node.system_prompt}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {node.error && (
        <div>
          <span className="text-sm text-slate-500">Error</span>
          <div className="mt-1 rounded-md bg-red-900/30 border border-red-700/50 p-3 text-sm text-red-300 font-mono whitespace-pre-wrap break-words">
            {node.error}
          </div>
        </div>
      )}

      {/* Artifacts */}
      {node.artifacts.length > 0 && (
        <div>
          <span className="text-sm text-slate-500">
            Artifacts ({node.artifacts.length})
          </span>
          <div className="mt-2 space-y-2">
            {node.artifacts.map((a, i) => {
              const isExpanded = expandedArtifact === i;
              const content =
                typeof a.content === 'string'
                  ? a.content
                  : JSON.stringify(a.content, null, 2);
              return (
                <div
                  key={i}
                  className="rounded-md border border-slate-700 bg-slate-800/50"
                >
                  <button
                    onClick={() => setExpandedArtifact(isExpanded ? null : i)}
                    className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-slate-700/30 transition-colors"
                  >
                    <span className="font-medium text-slate-300">
                      {a.type}
                      <span className="ml-2 text-xs text-slate-500 font-mono">
                        {a.id}
                      </span>
                    </span>
                    <span className="text-xs text-blue-400">
                      {isExpanded ? 'collapse' : 'expand'}
                    </span>
                  </button>
                  {isExpanded && (
                    <pre className="border-t border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 whitespace-pre-wrap break-words max-h-80 overflow-y-auto">
                      {content}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function DebugPage() {
  const { runId } = useParams<{ runId: string }>();
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [filter, setFilter] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [replayNode, setReplayNode] = useState<string | null>(null);

  const { data, isLoading, error } = useDebug(runId, errorsOnly);

  const filteredNodes = useMemo(() => {
    if (!data?.nodes) return [];
    if (!filter) return data.nodes;
    const lower = filter.toLowerCase();
    return data.nodes.filter(
      (n) =>
        n.node_id.toLowerCase().includes(lower) ||
        n.status.toLowerCase().includes(lower),
    );
  }, [data?.nodes, filter]);

  const selectedNode = useMemo(
    () => filteredNodes.find((n) => n.node_id === selectedNodeId) ?? null,
    [filteredNodes, selectedNodeId],
  );

  if (!runId) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        Select a run first to view debug information.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="flex gap-4" style={{ minHeight: 500 }}>
          <div className="w-80 bg-slate-800 rounded animate-pulse" />
          <div className="flex-1 bg-slate-800 rounded animate-pulse" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">
          Failed to load debug data: {(error as Error).message}
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 flex flex-col gap-4 h-full">
      {/* Breadcrumb */}
      <div className="text-sm text-slate-500">
        <Link to="/" className="hover:text-slate-300">
          Dashboard
        </Link>{' '}
        /{' '}
        <Link to={`/runs/${runId}`} className="hover:text-slate-300">
          {runId?.slice(0, 8)}...
        </Link>{' '}
        / <span className="text-slate-200">Debug</span>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Debug</h1>
          {data?.workflow_name && (
            <p className="text-sm text-slate-400 mt-0.5">
              {data.workflow_name}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400">
            {data?.status}
          </span>
          <Link
            to={`/runs/${runId}/trace`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            View Trace
          </Link>
          <Link
            to={`/runs/${runId}/diagnose`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            Diagnose
          </Link>
        </div>
      </div>

      {/* Main layout */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left panel: Node list */}
        <div className="w-80 flex flex-col border border-slate-700 rounded-lg bg-slate-800/50 overflow-hidden">
          {/* Filter */}
          <div className="p-3 border-b border-slate-700 space-y-2">
            <div className="relative">
              <Search
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500"
              />
              <input
                type="text"
                placeholder="Filter nodes..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-1.5 pl-8 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={errorsOnly}
                onChange={(e) => setErrorsOnly(e.target.checked)}
                className="rounded border-slate-600 bg-slate-900 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
              />
              Errors only
            </label>
          </div>

          {/* Node list */}
          <div className="flex-1 overflow-y-auto">
            {filteredNodes.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">No nodes found</p>
            ) : (
              <ul className="divide-y divide-slate-700/50">
                {filteredNodes.map((node) => (
                  <li key={node.node_id}>
                    <button
                      onClick={() =>
                        setSelectedNodeId(
                          selectedNodeId === node.node_id
                            ? null
                            : node.node_id,
                        )
                      }
                      className={`w-full text-left px-3 py-2.5 flex items-center gap-2.5 text-sm transition-colors ${
                        selectedNodeId === node.node_id
                          ? 'bg-blue-600/20 border-l-2 border-blue-500'
                          : 'hover:bg-slate-700/30 border-l-2 border-transparent'
                      }`}
                    >
                      {statusIcon(node.status)}
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-xs truncate">
                          {node.node_id}
                        </p>
                        {node.duration_s !== null && (
                          <p className="text-xs text-slate-500 mt-0.5">
                            {node.duration_s.toFixed(3)}s
                          </p>
                        )}
                      </div>
                      {node.error && (
                        <XCircle size={12} className="text-red-400 shrink-0" />
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Right panel: Node detail */}
        <div className="flex-1 border border-slate-700 rounded-lg bg-slate-800/50 overflow-y-auto">
          {selectedNode ? (
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold font-mono text-sm">
                  {selectedNode.node_id}
                </h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setReplayNode(selectedNode.node_id)}
                    className="flex items-center gap-1 px-2 py-0.5 rounded text-xs border border-blue-500/40 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
                    title="Replay from this node"
                  >
                    <RotateCcw size={12} />
                    Replay
                  </button>
                  <div
                    className={`px-2 py-0.5 rounded text-xs border ${statusColor(selectedNode.status)}`}
                  >
                    {selectedNode.status}
                  </div>
                </div>
              </div>
              <NodeDetail node={selectedNode} />
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">
              Select a node to view details
            </div>
          )}
        </div>
      </div>

      {replayNode && data && (() => {
        const nodeData = data.nodes.find((n) => n.node_id === replayNode);
        return (
          <ReplayModal
            runId={runId!}
            nodeId={replayNode}
            currentAgent={nodeData?.agent || 'llm://unknown'}
            currentPrompt={nodeData?.system_prompt}
            workflowPath={data.workflow_path || data.workflow_name}
            artifacts={nodeData?.artifacts}
            onClose={() => setReplayNode(null)}
          />
        );
      })()}
    </div>
  );
}
