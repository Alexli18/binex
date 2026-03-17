import { useState, useMemo, useEffect, Fragment } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRun, useRecords, useCreateRun } from '../hooks/useRuns';
import { useArtifacts, useCosts } from '../hooks/useArtifacts';
import { useWorkflow } from '../hooks/useWorkflows';
import { useDebug } from '../hooks/useAnalysis';
import { useTrace } from '../hooks/useAnalysis';
import { usePreviousRun } from '../hooks/usePreviousRun';
import { StatusBadge } from '../components/common/StatusBadge';
import { WorkflowGraph } from '../components/dag/WorkflowGraph';
import { DebugNodeList, DebugNodeDetail } from '@/components/debug';
import { TraceGantt } from '@/components/trace/TraceGantt';
import { TraceControls } from '@/components/trace/TraceControls';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ReplayModal } from '../components/ReplayModal';
import { Pencil, RotateCcw, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import type { WorkflowNode, WorkflowEdge } from '../lib/yaml-to-graph';
import { LoadingState } from '@/components/layout/LoadingState';
import yaml from 'js-yaml';

type Tab = 'overview' | 'graph' | 'trace' | 'debug';

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
  const { data: workflowData } = useWorkflow(run?.workflow_path ?? null);
  const createRun = useCreateRun();

  const { data: previousRun } = usePreviousRun(runId);

  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expandedArtifact, setExpandedArtifact] = useState<number | null>(null);

  // Debug data (lazy — only fetched when debug tab is active)
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [debugSelectedNodeId, setDebugSelectedNodeId] = useState<string | null>(null);
  const [replayNodeId, setReplayNodeId] = useState<string | null>(null);
  const debugQuery = useDebug(activeTab === 'debug' ? runId : undefined, errorsOnly);
  const debugSelectedNode = useMemo(
    () => debugQuery.data?.nodes.find((n) => n.node_id === debugSelectedNodeId) ?? null,
    [debugQuery.data?.nodes, debugSelectedNodeId],
  );

  // Trace data (lazy — only fetched when trace tab is active)
  const traceQuery = useTrace(activeTab === 'trace' ? runId : undefined);
  const anomalyNodeIds = useMemo(
    () => new Set(traceQuery.data?.anomalies.map((a) => a.node_id) ?? []),
    [traceQuery.data?.anomalies],
  );

  const graphNodes: WorkflowNode[] = useMemo(() => {
    if (!records) return [];
    return records.map((r) => ({
      id: r.task_id,
      label: r.task_id,
      type: 'local',
      status: r.status,
    }));
  }, [records]);

  const graphEdges: WorkflowEdge[] = useMemo(() => {
    if (!workflowData?.content) return [];
    try {
      const parsed = yaml.load(workflowData.content) as { nodes?: Record<string, { depends_on?: string[] }> };
      if (!parsed?.nodes) return [];
      const edges: WorkflowEdge[] = [];
      for (const [id, spec] of Object.entries(parsed.nodes)) {
        if (spec.depends_on) {
          for (const dep of spec.depends_on) {
            edges.push({ id: `${dep}-${id}`, source: dep, target: id });
          }
        }
      }
      return edges;
    } catch {
      return [];
    }
  }, [workflowData]);

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
        <LoadingState message="Loading run..." />
      </div>
    );
  }

  if (runError) {
    return (
      <div className="p-6">
        <p className="text-red-400">
          Failed to load run: {(runError as Error).message}
        </p>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="p-6">
        <p className="text-slate-400">Run not found.</p>
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

  const handleRerun = () => {
    if (run.workflow_path) {
      createRun.mutate(
        { workflow_path: run.workflow_path },
        {
          onSuccess: (data) => {
            toast.success('Run started');
            navigate(data.status === 'running' ? `/runs/${data.run_id}/live` : `/runs/${data.run_id}`);
          },
          onError: (err) => toast.error(`Re-run failed: ${err.message}`),
        },
      );
    }
  };

  return (
    <div className="flex flex-col h-screen">
      {/* Header bar */}
      <div className="flex items-center gap-3 px-6 py-3 bg-slate-900 border-b border-slate-700/50">
        <button
          onClick={() => navigate('/')}
          className="text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          ← Dashboard
        </button>
        <span className="text-slate-600">/</span>
        <span className="text-sm font-medium text-slate-200">{run.workflow_name}</span>
        <span className="font-mono text-xs text-slate-500">{run.run_id.slice(0, 8)}</span>
        <StatusBadge status={run.status} />
        <div className="flex-1" />
        {/* Summary stats inline */}
        <span className="text-xs text-slate-400">{run.completed_nodes}/{run.total_nodes} nodes</span>
        <span className="text-xs text-slate-400">·</span>
        <span className="text-xs text-slate-400">{duration !== null ? `${duration}s` : '...'}</span>
        <span className="text-xs text-slate-400">·</span>
        <span className="text-xs font-mono text-slate-400">${(run.total_cost ?? 0).toFixed(4)}</span>
        <div className="flex gap-1.5 ml-2">
          <Button variant="outline" size="sm" onClick={handleRerun} disabled={!run.workflow_path || createRun.isPending}>
            <RotateCcw className="w-3.5 h-3.5 mr-1" />
            Re-run
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate(`/editor?file=${encodeURIComponent(run.workflow_path ?? '')}`)}>
            <Pencil className="w-3.5 h-3.5 mr-1" />
            Edit
          </Button>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-0 px-6 bg-slate-900 border-b border-slate-700/50" role="tablist" aria-label="Run detail tabs">
        {(['overview', 'graph', 'trace', 'debug'] as Tab[]).map((tab) => (
          <button
            key={tab}
            role="tab"
            id={`run-tab-${tab}`}
            aria-selected={activeTab === tab}
            aria-controls={`run-tabpanel-${tab}`}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-4 min-h-[44px] text-sm font-medium border-b-2 transition-colors capitalize',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset',
              activeTab === tab
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200',
            )}
          >
            {tab}
          </button>
        ))}
        {/* More dropdown for Diagnose, Lineage, Diff */}
        <DropdownMenu>
          <DropdownMenuTrigger className="px-4 py-2.5 text-sm font-medium text-slate-400 hover:text-slate-200 border-b-2 border-transparent">
            More ▾
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem
              onClick={() => previousRun && navigate(`/diff?runA=${runId}&runB=${previousRun.run_id}`)}
              disabled={!previousRun}
              className={!previousRun ? 'opacity-50 cursor-not-allowed' : ''}
            >
              Compare with previous
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate(`/diff?runA=${runId}`)}>Compare...</DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate(`/runs/${runId}/diagnose`)}>Diagnose</DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate(`/runs/${runId}/lineage`)}>Lineage</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="p-6 flex flex-col gap-6" role="tabpanel" id="run-tabpanel-overview" aria-labelledby="run-tab-overview">
            {/* Summary card */}
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-slate-300">
                <div>
                  <span className="font-medium text-slate-100">Run ID</span>
                  <p className="font-mono text-xs mt-0.5 break-all">{run.run_id}</p>
                </div>
                <div>
                  <span className="font-medium text-slate-100">Nodes</span>
                  <p className="mt-0.5">
                    {run.completed_nodes}/{run.total_nodes} completed
                    {run.failed_nodes > 0 && (
                      <span className="text-red-400">
                        {' '}({run.failed_nodes} failed)
                      </span>
                    )}
                  </p>
                </div>
                <div>
                  <span className="font-medium text-slate-100">Duration</span>
                  <p className="mt-0.5">
                    {duration !== null ? `${duration}s` : 'In progress...'}
                  </p>
                </div>
                <div>
                  <span className="font-medium text-slate-100">Total Cost</span>
                  <p className="mt-0.5 font-mono">${(run.total_cost ?? 0).toFixed(4)}</p>
                </div>
              </div>
            </div>

            {/* Artifacts table */}
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <h3 className="text-sm font-medium text-slate-200 mb-3">Artifacts</h3>
              {!artifacts || artifacts.length === 0 ? (
                <p className="text-slate-500 text-sm">No artifacts</p>
              ) : (
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-400">
                      <th className="pb-2 font-medium">Producer</th>
                      <th className="pb-2 font-medium">Type</th>
                      <th className="pb-2 font-medium">Step</th>
                      <th className="pb-2 font-medium">Content</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {artifacts.map((a, i) => {
                      const content = typeof a.content === 'string' ? a.content : JSON.stringify(a.content, null, 2);
                      const isLong = content.length > 120;
                      const isExpanded = expandedArtifact === i;
                      return (
                        <Fragment key={i}>
                          <tr
                            className={isLong ? 'cursor-pointer hover:bg-slate-900' : ''}
                            onClick={() => isLong && setExpandedArtifact(isExpanded ? null : i)}
                          >
                            <td className="py-2 font-mono text-xs">{a.lineage.produced_by}</td>
                            <td className="py-2">{a.type}</td>
                            <td className="py-2">{a.lineage.step}</td>
                            <td className="py-2 text-slate-300 max-w-md">
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
                                <pre className="bg-slate-900 p-4 text-xs text-slate-300 whitespace-pre-wrap break-words max-h-96 overflow-y-auto border-t border-b border-slate-700">
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

            {/* Costs table */}
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <h3 className="text-sm font-medium text-slate-200 mb-3">Costs</h3>
              {!costSummary || costSummary.records.length === 0 ? (
                <p className="text-slate-500 text-sm">No cost records</p>
              ) : (
                <>
                  <p className="text-sm text-slate-300 mb-3">
                    Total: <span className="font-mono font-bold">${(costSummary.total_cost ?? 0).toFixed(4)}</span>
                  </p>
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="text-left text-slate-400">
                        <th className="pb-2 font-medium">Node</th>
                        <th className="pb-2 font-medium">Model</th>
                        <th className="pb-2 font-medium">Source</th>
                        <th className="pb-2 font-medium text-right">Cost</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {costSummary.records.map((c, i) => (
                        <tr key={i}>
                          <td className="py-2 font-mono text-xs">{c.node_id}</td>
                          <td className="py-2">{c.model ?? '-'}</td>
                          <td className="py-2">{c.source}</td>
                          <td className="py-2 text-right font-mono">${(c.cost ?? 0).toFixed(6)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          </div>
        )}

        {/* Graph Tab */}
        {activeTab === 'graph' && (
          <div className="flex h-full" role="tabpanel" id="run-tabpanel-graph" aria-labelledby="run-tab-graph" style={{ minHeight: 450 }}>
            <div className="flex-1 overflow-hidden">
              {graphNodes.length > 0 ? (
                <WorkflowGraph
                  nodes={graphNodes}
                  edges={graphEdges}
                  onNodeClick={(nodeId) =>
                    setSelectedNodeId((prev) => (prev === nodeId ? null : nodeId))
                  }
                />
              ) : (
                <div className="flex items-center justify-center h-full text-slate-500 text-sm">
                  No execution records yet
                </div>
              )}
            </div>

            {/* Node Side Panel */}
            {selectedNodeId && (
              <div className="w-80 bg-slate-800 border-l border-slate-700 p-4 overflow-y-auto">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-sm">{selectedNodeId}</h3>
                  <button
                    onClick={() => setSelectedNodeId(null)}
                    className="p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-700 transition-colors"
                    aria-label="Close"
                  >
                    <X size={16} />
                  </button>
                </div>
                {selectedRecord && (
                  <div className="space-y-2 text-sm mb-4">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Status</span>
                      <StatusBadge status={selectedRecord.status} />
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Latency</span>
                      <span>{selectedRecord.latency_ms}ms</span>
                    </div>
                    {selectedRecord.error && (
                      <div>
                        <span className="text-slate-400">Error</span>
                        <p className="text-red-400 text-xs mt-1 bg-red-900/30 p-2 rounded">
                          {selectedRecord.error}
                        </p>
                      </div>
                    )}
                  </div>
                )}
                {selectedCost && (
                  <div className="text-sm border-t pt-2 mb-4">
                    <span className="text-slate-400">Cost</span>
                    <p className="font-mono">${(selectedCost.cost ?? 0).toFixed(6)}</p>
                    {selectedCost.model && (
                      <p className="text-xs text-slate-500">{selectedCost.model}</p>
                    )}
                  </div>
                )}
                {selectedArtifacts.length > 0 && (
                  <div className="text-sm border-t pt-2">
                    <span className="text-slate-400">Artifacts ({selectedArtifacts.length})</span>
                    <div className="mt-1 space-y-2">
                      {selectedArtifacts.map((a, i) => {
                        const content = typeof a.content === 'string' ? a.content : JSON.stringify(a.content, null, 2);
                        return (
                          <div key={i} className="bg-slate-900 rounded p-2 text-xs break-all">
                            <span className="font-medium">{a.type}</span>
                            <pre className="text-slate-300 mt-0.5 whitespace-pre-wrap max-h-60 overflow-y-auto">
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
        )}

        {/* Trace Tab */}
        {activeTab === 'trace' && (
          <div className="p-6 flex flex-col gap-4" role="tabpanel" id="run-tabpanel-trace" aria-labelledby="run-tab-trace">
            {traceQuery.isLoading ? (
              <LoadingState message="Loading trace..." />
            ) : traceQuery.error ? (
              <p className="text-red-400">Failed to load trace: {(traceQuery.error as Error).message}</p>
            ) : !traceQuery.data || traceQuery.data.timeline.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <p className="text-slate-400 text-sm">No trace data available for this run.</p>
                <p className="text-slate-500 text-xs mt-1">Trace data is recorded during workflow execution.</p>
              </div>
            ) : (
              <>
                <TraceControls
                  runId={runId!}
                  status={traceQuery.data?.status ?? ''}
                  totalDuration={traceQuery.data?.total_duration_s ?? 0}
                  anomalies={traceQuery.data?.anomalies ?? []}
                />
                <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-4">
                  <h2 className="text-sm font-medium text-slate-300 mb-3">Execution Timeline</h2>
                  {traceQuery.data && traceQuery.data.timeline.length > 0 ? (
                    <TraceGantt
                      timeline={traceQuery.data.timeline}
                      totalDuration={traceQuery.data.total_duration_s}
                      anomalyNodeIds={anomalyNodeIds}
                    />
                  ) : (
                    <p className="text-slate-500 text-sm">No timeline entries</p>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* Debug Tab */}
        {activeTab === 'debug' && (
          <div className="p-6 flex flex-col gap-4 h-full" role="tabpanel" id="run-tabpanel-debug" aria-labelledby="run-tab-debug">
            {debugQuery.isLoading ? (
              <LoadingState message="Loading debug data..." />
            ) : debugQuery.error ? (
              <p className="text-red-400">Failed to load debug data: {(debugQuery.error as Error).message}</p>
            ) : !debugQuery.data || debugQuery.data.nodes.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <p className="text-slate-400 text-sm">No debug data available for this run.</p>
                <p className="text-slate-500 text-xs mt-1">Debug data includes node inputs, outputs, and errors.</p>
              </div>
            ) : (
              <div className="flex gap-4 flex-1 min-h-0">
                <DebugNodeList
                  nodes={debugQuery.data?.nodes ?? []}
                  selectedNodeId={debugSelectedNodeId}
                  errorsOnly={errorsOnly}
                  onSelectNode={setDebugSelectedNodeId}
                  onErrorsOnlyChange={setErrorsOnly}
                />
                <DebugNodeDetail
                  node={debugSelectedNode}
                  onReplay={setReplayNodeId}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {replayNodeId && debugQuery.data && (() => {
        const nodeData = debugQuery.data.nodes.find((n) => n.node_id === replayNodeId);
        return (
          <ReplayModal
            runId={runId!}
            nodeId={replayNodeId}
            currentAgent={nodeData?.agent || 'llm://unknown'}
            currentPrompt={nodeData?.system_prompt}
            workflowPath={run.workflow_path ?? null}
            artifacts={nodeData?.artifacts}
            onClose={() => setReplayNodeId(null)}
          />
        );
      })()}
    </div>
  );
}
