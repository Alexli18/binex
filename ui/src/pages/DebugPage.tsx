import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useDebug } from '../hooks/useAnalysis';
import { ReplayModal } from '../components/ReplayModal';
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

  const { data, isLoading, error } = useDebug(runId, errorsOnly);

  const selectedNode = useMemo(
    () => data?.nodes.find((n) => n.node_id === selectedNodeId) ?? null,
    [data?.nodes, selectedNodeId],
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
      <div className="p-6 flex flex-col gap-4 h-full">
        <Skeleton className="h-4 w-48 bg-slate-800" />
        <Skeleton className="h-8 w-32 bg-slate-800" />
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
      <div className="text-sm text-slate-500">
        <Link to="/" className="hover:text-slate-300">Dashboard</Link>{' '}
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
            <p className="text-sm text-slate-400 mt-0.5">{data.workflow_name}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400">{data?.status}</span>
          <Link to={`/runs/${runId}/trace`} className="text-xs text-blue-400 hover:text-blue-300">
            View Trace
          </Link>
          <Link to={`/runs/${runId}/diagnose`} className="text-xs text-blue-400 hover:text-blue-300">
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
    </div>
  );
}
