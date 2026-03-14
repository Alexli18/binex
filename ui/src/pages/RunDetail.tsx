import { useState, useMemo, useEffect, Fragment } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useRun, useRecords } from '../hooks/useRuns';
import { useArtifacts, useCosts } from '../hooks/useArtifacts';
import { StatusBadge } from '../components/common/StatusBadge';
import { WorkflowGraph } from '../components/dag/WorkflowGraph';
import type { WorkflowNode, WorkflowEdge } from '../lib/yaml-to-graph';

type Tab = 'artifacts' | 'costs';

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run, isLoading: runLoading, error: runError } = useRun(runId);

  // Auto-redirect to live view if run is still running
  useEffect(() => {
    if (run && run.status === 'running') {
      navigate(`/runs/${runId}/live`, { replace: true });
    }
  }, [run, runId, navigate]);
  const { data: records } = useRecords(runId);
  const { data: artifacts } = useArtifacts(runId);
  const { data: costSummary } = useCosts(runId);

  const [activeTab, setActiveTab] = useState<Tab>('artifacts');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expandedArtifact, setExpandedArtifact] = useState<number | null>(null);

  const graphNodes: WorkflowNode[] = useMemo(() => {
    if (!records) return [];
    return records.map((r) => ({
      id: r.task_id,
      label: r.task_id,
      type: 'local',
      status: r.status,
    }));
  }, [records]);

  const graphEdges: WorkflowEdge[] = useMemo(() => [], []);

  const selectedRecord = useMemo(
    () => records?.find((r) => r.task_id === selectedNodeId) ?? null,
    [records, selectedNodeId],
  );

  const selectedArtifacts = useMemo(
    () =>
      artifacts?.filter((a) => a.lineage.produced_by === selectedNodeId) ?? [],
    [artifacts, selectedNodeId],
  );

  const selectedCost = useMemo(
    () =>
      costSummary?.records.find((c) => c.node_id === selectedNodeId) ?? null,
    [costSummary, selectedNodeId],
  );

  if (runLoading) {
    return (
      <div className="p-6">
        <p className="text-gray-500">Loading run...</p>
      </div>
    );
  }

  if (runError) {
    return (
      <div className="p-6">
        <p className="text-red-600">
          Failed to load run: {(runError as Error).message}
        </p>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="p-6">
        <p className="text-gray-500">Run not found.</p>
      </div>
    );
  }

  const duration =
    run.started_at && run.completed_at
      ? Math.round(
          (new Date(run.completed_at).getTime() -
            new Date(run.started_at).getTime()) /
            1000,
        )
      : null;

  return (
    <div className="p-6 flex flex-col gap-6">
      {/* Breadcrumb */}
      <div className="text-sm text-gray-500">
        <Link to="/" className="hover:text-gray-900">
          Dashboard
        </Link>{' '}
        / <span className="text-gray-900">{run.run_id}</span>
      </div>

      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-bold">{run.workflow_name}</h2>
          <StatusBadge status={run.status} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-600">
          <div>
            <span className="font-medium text-gray-900">Run ID</span>
            <p className="font-mono text-xs mt-0.5 break-all">{run.run_id}</p>
          </div>
          <div>
            <span className="font-medium text-gray-900">Nodes</span>
            <p className="mt-0.5">
              {run.completed_nodes}/{run.total_nodes} completed
              {run.failed_nodes > 0 && (
                <span className="text-red-600">
                  {' '}
                  ({run.failed_nodes} failed)
                </span>
              )}
            </p>
          </div>
          <div>
            <span className="font-medium text-gray-900">Duration</span>
            <p className="mt-0.5">
              {duration !== null ? `${duration}s` : 'In progress...'}
            </p>
          </div>
          <div>
            <span className="font-medium text-gray-900">Total Cost</span>
            <p className="mt-0.5 font-mono">${run.total_cost.toFixed(4)}</p>
          </div>
        </div>
      </div>

      {/* DAG Graph + Side Panel */}
      <div className="flex gap-4" style={{ minHeight: 450 }}>
        <div className="flex-1 bg-white border border-gray-200 rounded-lg overflow-hidden">
          {graphNodes.length > 0 ? (
            <WorkflowGraph
              nodes={graphNodes}
              edges={graphEdges}
              onNodeClick={(nodeId) =>
                setSelectedNodeId((prev) =>
                  prev === nodeId ? null : nodeId,
                )
              }
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400 text-sm">
              No execution records yet
            </div>
          )}
        </div>

        {/* Node Side Panel */}
        {selectedNodeId && (
          <div className="w-80 bg-white border border-gray-200 rounded-lg p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-sm">{selectedNodeId}</h3>
              <button
                onClick={() => setSelectedNodeId(null)}
                className="text-gray-400 hover:text-gray-600 text-lg leading-none"
                aria-label="Close panel"
              >
                x
              </button>
            </div>
            {selectedRecord && (
              <div className="space-y-2 text-sm mb-4">
                <div className="flex justify-between">
                  <span className="text-gray-500">Status</span>
                  <StatusBadge status={selectedRecord.status} />
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Latency</span>
                  <span>{selectedRecord.latency_ms}ms</span>
                </div>
                {selectedRecord.error && (
                  <div>
                    <span className="text-gray-500">Error</span>
                    <p className="text-red-600 text-xs mt-1 bg-red-50 p-2 rounded">
                      {selectedRecord.error}
                    </p>
                  </div>
                )}
              </div>
            )}
            {selectedCost && (
              <div className="text-sm border-t pt-2 mb-4">
                <span className="text-gray-500">Cost</span>
                <p className="font-mono">${selectedCost.cost.toFixed(6)}</p>
                {selectedCost.model && (
                  <p className="text-xs text-gray-400">{selectedCost.model}</p>
                )}
              </div>
            )}
            {selectedArtifacts.length > 0 && (
              <div className="text-sm border-t pt-2">
                <span className="text-gray-500">
                  Artifacts ({selectedArtifacts.length})
                </span>
                <div className="mt-1 space-y-2">
                  {selectedArtifacts.map((a, i) => {
                    const content = typeof a.content === 'string' ? a.content : JSON.stringify(a.content, null, 2);
                    return (
                      <div
                        key={i}
                        className="bg-gray-50 rounded p-2 text-xs break-all"
                      >
                        <span className="font-medium">{a.type}</span>
                        <pre className="text-gray-600 mt-0.5 whitespace-pre-wrap max-h-60 overflow-y-auto">
                          {content}
                        </pre>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Tabs: Artifacts & Costs */}
      <div className="bg-white border border-gray-200 rounded-lg">
        <div className="border-b border-gray-200 flex">
          <button
            onClick={() => setActiveTab('artifacts')}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              activeTab === 'artifacts'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Artifacts
          </button>
          <button
            onClick={() => setActiveTab('costs')}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              activeTab === 'costs'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Costs
          </button>
        </div>

        <div className="p-4">
          {activeTab === 'artifacts' && (
            <div>
              {!artifacts || artifacts.length === 0 ? (
                <p className="text-gray-400 text-sm">No artifacts</p>
              ) : (
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500">
                      <th className="pb-2 font-medium">Producer</th>
                      <th className="pb-2 font-medium">Type</th>
                      <th className="pb-2 font-medium">Step</th>
                      <th className="pb-2 font-medium">Content</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {artifacts.map((a, i) => {
                      const content = typeof a.content === 'string' ? a.content : JSON.stringify(a.content, null, 2);
                      const isLong = content.length > 120;
                      const isExpanded = expandedArtifact === i;
                      return (
                        <Fragment key={i}>
                          <tr
                            className={isLong ? 'cursor-pointer hover:bg-gray-50' : ''}
                            onClick={() => isLong && setExpandedArtifact(isExpanded ? null : i)}
                          >
                            <td className="py-2 font-mono text-xs">
                              {a.lineage.produced_by}
                            </td>
                            <td className="py-2">{a.type}</td>
                            <td className="py-2">{a.lineage.step}</td>
                            <td className="py-2 text-gray-600 max-w-md">
                              {isExpanded ? null : (
                                <span className="block truncate">
                                  {content.slice(0, 120)}
                                  {isLong && '...'}
                                </span>
                              )}
                              {isLong && (
                                <span className="text-blue-500 text-xs ml-1">
                                  {isExpanded ? 'collapse' : 'expand'}
                                </span>
                              )}
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr>
                              <td colSpan={4} className="p-0">
                                <pre className="bg-gray-50 p-4 text-xs text-gray-700 whitespace-pre-wrap break-words max-h-96 overflow-y-auto border-t border-b border-gray-200">
                                  {content}
                                </pre>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === 'costs' && (
            <div>
              {!costSummary || costSummary.records.length === 0 ? (
                <p className="text-gray-400 text-sm">No cost records</p>
              ) : (
                <>
                  <p className="text-sm text-gray-600 mb-3">
                    Total:{' '}
                    <span className="font-mono font-bold">
                      ${costSummary.total_cost.toFixed(4)}
                    </span>
                  </p>
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500">
                        <th className="pb-2 font-medium">Node</th>
                        <th className="pb-2 font-medium">Model</th>
                        <th className="pb-2 font-medium">Source</th>
                        <th className="pb-2 font-medium text-right">Cost</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {costSummary.records.map((c, i) => (
                        <tr key={i}>
                          <td className="py-2 font-mono text-xs">
                            {c.node_id}
                          </td>
                          <td className="py-2">{c.model ?? '-'}</td>
                          <td className="py-2">{c.source}</td>
                          <td className="py-2 text-right font-mono">
                            ${c.cost.toFixed(6)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
