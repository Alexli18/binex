import { CheckCircle2, XCircle, Clock, SkipForward, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { DebugArtifactViewer } from './DebugArtifactViewer';
import { DebugErrorPanel } from './DebugErrorPanel';
import type { DebugNode } from '@/hooks/useAnalysis';

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

export interface DebugNodeDetailProps {
  node: DebugNode | null;
  onReplay: (nodeId: string) => void;
}

export function DebugNodeDetail({ node, onReplay }: DebugNodeDetailProps) {
  if (!node) {
    return (
      <div className="flex-1 border border-slate-700 rounded-lg bg-slate-800/50 overflow-y-auto">
        <div className="flex items-center justify-center h-full text-slate-500 text-sm">
          Select a node to view details
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 border border-slate-700 rounded-lg bg-slate-800/50 overflow-y-auto">
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold font-mono text-sm">{node.node_id}</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onReplay(node.node_id)}
              className="flex items-center gap-1 px-2 py-0.5 rounded text-xs border border-blue-500/40 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition-colors"
              title="Replay from this node"
            >
              <RotateCcw size={12} />
              Replay
            </button>
            <div
              className={cn('px-2 py-0.5 rounded text-xs border', statusColor(node.status))}
            >
              {node.status}
            </div>
          </div>
        </div>
        <NodeDetailContent node={node} />
      </div>
    </div>
  );
}

function NodeDetailContent({ node }: { node: DebugNode }) {
  return (
    <div className="space-y-4">
      {/* Status & timing */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <span className="text-slate-500">Status</span>
          <div className="flex items-center gap-2 mt-1">
            <StatusIcon status={node.status} />
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
              <pre className="mt-1 text-xs text-slate-300 bg-slate-900 border border-slate-700 rounded-lg p-3 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed">
                {node.system_prompt}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {node.error && <DebugErrorPanel error={node.error} />}

      {/* Input Artifacts */}
      {node.input_artifacts && node.input_artifacts.length > 0 && (
        <DebugArtifactViewer
          title="Input Artifacts"
          artifacts={node.input_artifacts}
          defaultExpanded={false}
        />
      )}

      {/* Output Artifacts */}
      {node.artifacts.length > 0 && (
        <DebugArtifactViewer
          title="Output Artifacts"
          artifacts={node.artifacts}
          defaultExpanded={false}
        />
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
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
}

export function DebugNodeDetailSkeleton() {
  return (
    <div className="flex-1 border border-slate-700 rounded-lg bg-slate-800/50 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-32 bg-slate-700" />
        <Skeleton className="h-6 w-20 bg-slate-700" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-1">
            <Skeleton className="h-3 w-16 bg-slate-700" />
            <Skeleton className="h-5 w-24 bg-slate-700" />
          </div>
        ))}
      </div>
      <Skeleton className="h-24 w-full bg-slate-700" />
    </div>
  );
}
