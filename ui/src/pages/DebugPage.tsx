import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useDebug, useFilesChanged } from '../hooks/useAnalysis';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { HelpTooltip } from '@/components/common/HelpTooltip';
import { ReplayModal } from '../components/ReplayModal';
import { CallReplayModal } from '../components/CallReplayModal';
import {
  DebugNodeList,
  DebugNodeListSkeleton,
  DebugNodeDetail,
  DebugNodeDetailSkeleton,
} from '@/components/debug';
import { Skeleton } from '@/components/ui/skeleton';

export default function DebugPage() {
  const { runId } = useParams<{ runId: string }>();
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [replayNode, setReplayNode] = useState<string | null>(null);
  const [replayCallNode, setReplayCallNode] = useState<string | null>(null);

  const { data, isLoading, error } = useDebug(runId, errorsOnly);
  const { data: filesChanged } = useFilesChanged(runId);

  const selectedNode = useMemo(
    () => data?.nodes.find((n) => n.node_id === selectedNodeId) ?? null,
    [data?.nodes, selectedNodeId],
  );

  if (!runId) {
    return (
      <div className="flex items-center justify-center h-full text-[#4a4a52]">
        Select a run first to view debug information.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 flex flex-col gap-4 h-full">
        <Skeleton className="h-4 w-48 bg-[#1a1a1d]" />
        <Skeleton className="h-8 w-32 bg-[#1a1a1d]" />
        <div className="flex gap-4 flex-1 min-h-0">
          <DebugNodeListSkeleton />
          <DebugNodeDetailSkeleton />
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
      <Breadcrumb items={[
        { label: 'Home', href: '/' },
        { label: 'Runs', href: '/' },
        { label: (runId?.slice(0, 8) ?? '') + '...', href: `/runs/${runId}` },
        { label: 'Debug' },
      ]} />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold inline-flex items-center gap-2">
            Debug
            <HelpTooltip
              side="right"
              content="Inspect each node's inputs, outputs, timing, and errors. Click a node to see details, or use Replay to re-run with modified parameters."
            />
          </h1>
          {data?.workflow_name && (
            <p className="text-sm text-[#80808a] mt-0.5">{data.workflow_name}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-[#80808a]">{data?.status}</span>
          <Link to={`/runs/${runId}/trace`} className="text-xs text-amber-400 hover:text-amber-300">
            View Trace
          </Link>
          <Link to={`/runs/${runId}/diagnose`} className="text-xs text-amber-400 hover:text-amber-300">
            Diagnose
          </Link>
        </div>
      </div>

      {/* Main layout */}
      <div className="flex gap-4 flex-1 min-h-0">
        <DebugNodeList
          nodes={data?.nodes ?? []}
          selectedNodeId={selectedNodeId}
          errorsOnly={errorsOnly}
          onSelectNode={setSelectedNodeId}
          onErrorsOnlyChange={setErrorsOnly}
        />
        <DebugNodeDetail
          node={selectedNode}
          onReplay={setReplayNode}
          observed={data?.observed}
          onReplayCall={setReplayCallNode}
          filesChanged={selectedNodeId ? filesChanged?.nodes[selectedNodeId] : undefined}
        />
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

      {replayCallNode && data && (() => {
        const nodeData = data.nodes.find((n) => n.node_id === replayCallNode);
        return (
          <CallReplayModal
            runId={runId!}
            callId={replayCallNode}
            originalModel={nodeData?.model || 'gpt-4o'}
            onClose={() => setReplayCallNode(null)}
          />
        );
      })()}
    </div>
  );
}
