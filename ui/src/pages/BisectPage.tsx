import { useState, useMemo } from 'react';
import { useRuns } from '../hooks/useRuns';
import { useBisect } from '../hooks/useComparison';
import { StatusBadge } from '../components/common/StatusBadge';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { AlertCircle, AlertTriangle, CheckCircle2, XCircle, HelpCircle, Loader2, ChevronDown } from 'lucide-react';
import { ArtifactDiff } from '@/components/common/ArtifactDiff';
import { statusColors, colors as tokenColors, chartColors } from '@/lib/design-tokens';
import ReactFlow, { type Node, type Edge } from 'reactflow';
import { BisectNode } from '../components/dag/BisectNode';
import 'reactflow/dist/style.css';
import type { BisectNodeStatus, BisectDetails } from '../hooks/useComparison';

const nodeStatusConfig = {
  match: {
    icon: CheckCircle2,
    label: 'Match',
    dotClass: statusColors.completed.dot,
    bgClass: statusColors.completed.bg,
    textClass: statusColors.completed.text,
    borderClass: statusColors.completed.border,
  },
  content_diff: {
    icon: AlertTriangle,
    label: 'Content differs',
    dotClass: statusColors.over_budget.dot,
    bgClass: statusColors.over_budget.bg,
    textClass: statusColors.over_budget.text,
    borderClass: statusColors.over_budget.border,
  },
  status_diff: {
    icon: XCircle,
    label: 'Status differs',
    dotClass: statusColors.failed.dot,
    bgClass: statusColors.failed.bg,
    textClass: statusColors.failed.text,
    borderClass: statusColors.failed.border,
  },
  missing_in_good: {
    icon: HelpCircle,
    label: 'Missing in good run',
    dotClass: statusColors.pending.dot,
    bgClass: statusColors.pending.bg,
    textClass: statusColors.pending.text,
    borderClass: statusColors.pending.border,
  },
  missing_in_bad: {
    icon: HelpCircle,
    label: 'Missing in bad run',
    dotClass: statusColors.pending.dot,
    bgClass: statusColors.pending.bg,
    textClass: statusColors.pending.text,
    borderClass: statusColors.pending.border,
  },
};

function NodeMap({
  nodes,
  divergenceNode,
  downstreamImpact,
}: {
  nodes: BisectNodeStatus[];
  divergenceNode: string | null;
  downstreamImpact: string[];
}) {
  const [expandedNode, setExpandedNode] = useState<string | null>(null);
  const downstreamSet = useMemo(() => new Set(downstreamImpact), [downstreamImpact]);

  if (nodes.length === 0) return null;

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-card p-4">
      <h4 className="text-sm font-bold text-slate-300 mb-4">Node Map</h4>
      <div className="space-y-0">
        {nodes.map((node, i) => {
          const config = nodeStatusConfig[node.status] || nodeStatusConfig.missing_in_bad;
          const Icon = config.icon;
          const isDivergence = node.node_id === divergenceNode;
          const isDownstream = downstreamSet.has(node.node_id);
          const isExpanded = expandedNode === node.node_id;
          const isLast = i === nodes.length - 1;

          return (
            <div key={node.node_id}>
              <button
                onClick={() => setExpandedNode(isExpanded ? null : node.node_id)}
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-md text-left transition-colors hover:bg-slate-700/30 ${
                  isDivergence ? 'ring-2 ring-red-400/60 bg-red-500/5' : ''
                } ${isDownstream ? 'border-l-2 border-orange-400' : ''}`}
                aria-expanded={isExpanded}
              >
                {/* Vertical connector line */}
                <div className="flex flex-col items-center w-5 shrink-0">
                  <div className={`w-3 h-3 rounded-full ${config.dotClass} ${isDivergence ? 'animate-pulse' : ''}`} />
                  {!isLast && <div className="w-px h-6 bg-slate-600 mt-1" />}
                </div>

                {/* Node info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-slate-200 truncate">{node.node_id}</span>
                    {isDivergence && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-900/50 text-red-300 border border-red-700 font-medium uppercase">
                        Divergence
                      </span>
                    )}
                    {isDownstream && !isDivergence && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-900/50 text-orange-300 border border-orange-700 font-medium">
                        Downstream
                      </span>
                    )}
                  </div>
                </div>

                {/* Status + similarity */}
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`flex items-center gap-1 text-xs ${config.textClass}`}>
                    <Icon size={14} />
                    {config.label}
                  </span>
                  {node.similarity !== null && (
                    <span className="text-xs font-mono text-slate-500">{Math.round(node.similarity * 100)}%</span>
                  )}
                  <ChevronDown size={14} className={`text-slate-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </div>
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className={`ml-11 mb-2 p-3 rounded-md ${config.bgClass} border ${config.borderClass} text-sm`}>
                  <div className="grid grid-cols-2 gap-3">
                    {node.good_status !== null && (
                      <div>
                        <span className="text-slate-500 text-xs">Good Status</span>
                        <p className="text-slate-200 text-xs mt-0.5">{node.good_status}</p>
                      </div>
                    )}
                    {node.bad_status !== null && (
                      <div>
                        <span className="text-slate-500 text-xs">Bad Status</span>
                        <p className="text-slate-200 text-xs mt-0.5">{node.bad_status}</p>
                      </div>
                    )}
                    {node.latency_good_ms !== null && (
                      <div>
                        <span className="text-slate-500 text-xs">Latency Good</span>
                        <p className="font-mono text-xs text-slate-300 mt-0.5">{node.latency_good_ms}ms</p>
                      </div>
                    )}
                    {node.latency_bad_ms !== null && (
                      <div>
                        <span className="text-slate-500 text-xs">Latency Bad</span>
                        <p className="font-mono text-xs text-slate-300 mt-0.5">{node.latency_bad_ms}ms</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DivergenceMetrics({ details }: { details: BisectDetails }) {
  const { latency_good_ms, latency_bad_ms, cost_good, cost_bad } = details;
  const hasLatency = latency_good_ms != null && latency_bad_ms != null;
  const hasCost = cost_good != null && cost_bad != null;

  if (!hasLatency && !hasCost) return null;

  const latencyDelta = hasLatency ? latency_bad_ms - latency_good_ms : 0;
  const latencyPct = hasLatency && latency_good_ms > 0
    ? Math.round((latencyDelta / latency_good_ms) * 100)
    : null;

  const costDelta = hasCost ? cost_bad - cost_good : 0;
  const costWarning = hasCost && cost_good > 0 && cost_bad / cost_good > 2;

  return (
    <div className="bg-slate-800/50 rounded-md p-3 my-3 border border-slate-700/50">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        {hasLatency && (
          <div className="flex items-center justify-between">
            <span className="text-slate-400">Latency</span>
            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="text-slate-300">{details.latency_good_ms}ms</span>
              <span className="text-slate-600">&rarr;</span>
              <span className="text-slate-300">{details.latency_bad_ms}ms</span>
              {latencyPct !== null && (
                <span className={`font-medium ${latencyDelta > 0 ? statusColors.failed.text : statusColors.completed.text}`}>
                  {latencyDelta > 0 ? '+' : ''}{latencyPct}%
                </span>
              )}
            </div>
          </div>
        )}
        {hasCost && (
          <div className="flex items-center justify-between">
            <span className="text-slate-400 flex items-center gap-1">
              Cost
              {costWarning && <AlertTriangle size={12} className="text-amber-400" />}
            </span>
            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="text-slate-300">${cost_good.toFixed(4)}</span>
              <span className="text-slate-600">&rarr;</span>
              <span className="text-slate-300">${cost_bad.toFixed(4)}</span>
              <span className={`font-medium ${costDelta > 0 ? statusColors.failed.text : statusColors.completed.text}`}>
                {costDelta > 0 ? '+' : ''}${costDelta.toFixed(4)}
              </span>
              {costWarning && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/50 text-amber-300 border border-amber-700">
                  &gt;2x
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const bisectNodeTypes = { bisect: BisectNode };

function BisectDAG({
  nodeMap,
  divergenceNode,
  downstreamImpact,
}: {
  nodeMap: BisectNodeStatus[];
  divergenceNode: string | null;
  downstreamImpact: string[];
}) {
  const downstreamSet = useMemo(() => new Set(downstreamImpact), [downstreamImpact]);

  const { nodes, edges } = useMemo(() => {
    const dagNodes: Node[] = nodeMap.map((n, i) => {
      let bisectStatus: 'match' | 'divergence' | 'downstream' | 'missing' = 'match';
      if (n.node_id === divergenceNode) bisectStatus = 'divergence';
      else if (downstreamSet.has(n.node_id)) bisectStatus = 'downstream';
      else if (n.status === 'missing_in_good' || n.status === 'missing_in_bad') bisectStatus = 'missing';
      else if (n.status !== 'match') bisectStatus = 'downstream';

      return {
        id: n.node_id,
        type: 'bisect',
        position: { x: 200, y: i * 100 + 30 },
        data: {
          label: n.node_id,
          type: 'local',
          bisectStatus,
          similarity: n.similarity,
        },
      };
    });

    // Connect nodes sequentially based on topological order from bisect report
    const dagEdges: Edge[] = nodeMap.slice(0, -1).map((n, i) => ({
      id: `${n.node_id}-${nodeMap[i + 1].node_id}`,
      source: n.node_id,
      target: nodeMap[i + 1].node_id,
      style: { stroke: chartColors.tooltipBorder },
    }));

    return { nodes: dagNodes, edges: dagEdges };
  }, [nodeMap, divergenceNode, downstreamSet]);

  if (nodes.length === 0) return null;

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-card overflow-hidden" style={{ height: 300 }}>
      <div className="px-4 py-2 border-b border-slate-700/50">
        <h4 className="text-sm font-bold text-slate-300">Workflow DAG</h4>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={bisectNodeTypes}
        fitView
        panOnDrag={false}
        zoomOnScroll={false}
        preventScrolling={false}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
        className="bg-slate-900"
      />
    </div>
  );
}

export default function BisectPage() {
  const { data: runs, isLoading: runsLoading } = useRuns();
  const bisect = useBisect();

  const [goodRun, setGoodRun] = useState('');
  const [badRun, setBadRun] = useState('');
  const [threshold, setThreshold] = useState(0.9);

  const handleBisect = () => {
    if (goodRun && badRun) {
      bisect.mutate({ good_run: goodRun, bad_run: badRun, threshold });
    }
  };

  const similarityPercent = bisect.data?.similarity != null
    ? Math.round(bisect.data.similarity * 100)
    : null;

  return (
    <PageShell>
      <Breadcrumb
        items={[
          { label: 'Dashboard', href: '/' },
          { label: 'Bisect' },
        ]}
        className="mb-4"
      />
      <PageHeader title="Bisect — Find Divergence" description="Compare two runs to find where they diverge" />

      {/* Selectors */}
      <div className="bg-slate-800 border border-slate-700 rounded-card p-4 mt-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-400 mb-1">Good Run</label>
              <Select value={goodRun} onValueChange={setGoodRun}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a run..." />
                </SelectTrigger>
                <SelectContent>
                  {runsLoading && (
                    <SelectItem value="__loading" disabled>Loading...</SelectItem>
                  )}
                  {runs?.map((r) => (
                    <SelectItem key={r.run_id} value={r.run_id}>
                      {r.workflow_name} — {r.run_id.slice(0, 8)} ({r.status})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-400 mb-1">Bad Run</label>
              <Select value={badRun} onValueChange={setBadRun}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a run..." />
                </SelectTrigger>
                <SelectContent>
                  {runsLoading && (
                    <SelectItem value="__loading" disabled>Loading...</SelectItem>
                  )}
                  {runs?.map((r) => (
                    <SelectItem key={r.run_id} value={r.run_id}>
                      {r.workflow_name} — {r.run_id.slice(0, 8)} ({r.status})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Threshold slider */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">
              Similarity Threshold: <span className="text-slate-200 font-mono">{threshold.toFixed(2)}</span>
            </label>
            <input
              type="range"
              min="0.1"
              max="1.0"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-full accent-purple-500"
            />
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>0.10</span>
              <span>1.00</span>
            </div>
          </div>

          <Button
            onClick={handleBisect}
            disabled={!goodRun || !badRun || bisect.isPending}
            size="sm"
            className="self-start"
          >
            {bisect.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {bisect.isPending ? 'Finding Divergence...' : 'Find Divergence'}
          </Button>
        </div>
      </div>

      {/* Error */}
      {bisect.isError && (
        <div className={`${statusColors.failed.bg} border ${statusColors.failed.border} rounded-card p-4 flex items-center gap-2`}>
          <AlertCircle className={`w-5 h-5 ${statusColors.failed.text} flex-shrink-0`} />
          <p className={`${statusColors.failed.text} text-sm`}>{bisect.error.message}</p>
        </div>
      )}

      {/* Results */}
      {bisect.data && (
        <div className="flex flex-col gap-4">
          {/* Divergence status */}
          {bisect.data.divergence_node ? (
            <>
              {/* Divergence found */}
              <div className="bg-slate-800 border border-slate-700 rounded-card p-4">
                <div className="flex items-center gap-3 mb-4">
                  <AlertCircle className="w-5 h-5 text-red-400" />
                  <span className="text-sm font-bold text-slate-200">
                    Divergence at node:{' '}
                    <span className="font-mono text-red-400">{bisect.data.divergence_node}</span>
                  </span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-900/50 text-red-300 border border-red-700">
                    index #{bisect.data.divergence_index}
                  </span>
                </div>

                {/* Similarity bar */}
                {similarityPercent !== null && (
                  <div className="mb-4">
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-slate-400">Similarity</span>
                      <span className="font-mono text-slate-200">{similarityPercent}%</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full transition-all ${
                          similarityPercent >= 80
                            ? tokenColors.success.bg
                            : similarityPercent >= 50
                              ? tokenColors.warning.bg
                              : tokenColors.danger.bg
                        }`}
                        style={{ width: `${similarityPercent}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Details card */}
                {bisect.data.details && (
                  <div className="bg-slate-900 border border-slate-700 rounded-card p-4">
                    <h4 className="text-sm font-bold text-slate-300 mb-3">Divergence Details</h4>
                    <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                      <div>
                        <span className="text-slate-500 block mb-1">Good Run Status</span>
                        <StatusBadge status={bisect.data.details.good_status} />
                      </div>
                      <div>
                        <span className="text-slate-500 block mb-1">Bad Run Status</span>
                        <StatusBadge status={bisect.data.details.bad_status} />
                      </div>
                    </div>

                    {/* Cost/Latency Metrics */}
                    <DivergenceMetrics details={bisect.data.details} />

                    <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                      {bisect.data.details.good_output !== null && (
                        <div>
                          <span className="text-slate-500 block mb-1">Good Output</span>
                          <pre className="text-xs font-mono text-slate-300 bg-slate-950 p-2 rounded max-h-40 overflow-y-auto whitespace-pre-wrap break-all">
                            {bisect.data.details.good_output}
                          </pre>
                        </div>
                      )}
                      {bisect.data.details.bad_output !== null && (
                        <div>
                          <span className="text-slate-500 block mb-1">Bad Output</span>
                          <pre className="text-xs font-mono text-slate-300 bg-slate-950 p-2 rounded max-h-40 overflow-y-auto whitespace-pre-wrap break-all">
                            {bisect.data.details.bad_output}
                          </pre>
                        </div>
                      )}
                    </div>

                    {bisect.data.details.diff && (
                      <div>
                        <span className="text-slate-500 text-sm block mb-2">Output Diff</span>
                        <ArtifactDiff diff={bisect.data.details.diff} />
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Node Map */}
              {bisect.data.node_map && bisect.data.node_map.length > 0 && (
                <NodeMap
                  nodes={bisect.data.node_map}
                  divergenceNode={bisect.data.divergence_node}
                  downstreamImpact={bisect.data.downstream_impact ?? []}
                />
              )}

              {/* DAG Visualization */}
              {bisect.data.node_map && bisect.data.node_map.length > 0 && (
                <BisectDAG
                  nodeMap={bisect.data.node_map}
                  divergenceNode={bisect.data.divergence_node}
                  downstreamImpact={bisect.data.downstream_impact ?? []}
                />
              )}
            </>
          ) : (
            /* No divergence found */
            <div className="bg-slate-800 border border-slate-700 rounded-card p-4 flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-green-400" />
              <span className="inline-flex items-center px-2.5 py-1 rounded text-sm font-medium bg-green-900/50 text-green-300 border border-green-700">
                No divergence found
              </span>
              <span className="text-slate-400 text-sm">
                The runs are similar above the threshold.
              </span>
            </div>
          )}
        </div>
      )}
    </PageShell>
  );
}
