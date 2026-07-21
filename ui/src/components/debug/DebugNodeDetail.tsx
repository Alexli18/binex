import { useState } from 'react';
import { CheckCircle2, XCircle, Clock, SkipForward, RotateCcw, ChevronDown, ChevronRight, Terminal } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { DebugArtifactViewer } from './DebugArtifactViewer';
import { DebugErrorPanel } from './DebugErrorPanel';
import type { DebugNode, DebugArtifact } from '@/hooks/useAnalysis';
import { getStatusColors } from '@/lib/design-tokens';

/** Returns border + bg classes for the node detail card header chip. */
const statusColor = (status: string): string => {
  const t = getStatusColors(status);
  return `${t.border} ${t.bg}`;
};

export interface DebugNodeDetailProps {
  node: DebugNode | null;
  onReplay: (nodeId: string) => void;
  // Observed runs (#73): the node is a captured LLM call; Replay does a
  // stateless single-call replay (#74) instead of a from-step node replay.
  observed?: boolean;
  onReplayCall?: (callId: string) => void;
}

export function DebugNodeDetail({
  node,
  onReplay,
  observed = false,
  onReplayCall,
}: DebugNodeDetailProps) {
  const isCallReplay = observed && !!onReplayCall;
  if (!node) {
    return (
      <div className="flex-1 border border-[#252528] rounded-lg bg-[#1a1a1d]/50 overflow-y-auto">
        <div className="flex items-center justify-center h-full text-[#4a4a52] text-sm">
          Select a node to view details
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 border border-[#252528] rounded-lg bg-[#1a1a1d]/50 overflow-y-auto">
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold font-mono text-sm">{node.node_id}</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() =>
                isCallReplay ? onReplayCall!(node.node_id) : onReplay(node.node_id)
              }
              className="flex items-center gap-1 px-2 py-0.5 rounded text-xs border border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-400/20 transition-colors"
              title={isCallReplay ? 'Replay this captured call' : 'Replay from this node'}
            >
              <RotateCcw size={12} />
              {isCallReplay ? 'Replay call' : 'Replay'}
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
          <span className="text-[#4a4a52]">Status</span>
          <div className="flex items-center gap-2 mt-1">
            <StatusIcon status={node.status} />
            <span className="capitalize">{node.status}</span>
          </div>
        </div>
        <div>
          <span className="text-[#4a4a52]">Duration</span>
          <p className="mt-1 font-mono">
            {node.duration_s !== null ? `${node.duration_s.toFixed(3)}s` : '-'}
          </p>
        </div>
        <div>
          <span className="text-[#4a4a52]">Started</span>
          <p className="mt-1 text-xs font-mono text-[#80808a]">
            {node.started_at ?? '-'}
          </p>
        </div>
        <div>
          <span className="text-[#4a4a52]">Completed</span>
          <p className="mt-1 text-xs font-mono text-[#80808a]">
            {node.completed_at ?? '-'}
          </p>
        </div>
      </div>

      {/* Agent / Model / Prompt */}
      {(node.agent || node.model || node.system_prompt) && (
        <div className="space-y-2 border-t border-[#252528] pt-3">
          {node.agent && (
            <div>
              <span className="text-sm text-[#4a4a52]">Agent</span>
              <p className="mt-0.5 text-xs font-mono text-[#80808a]">{node.agent}</p>
            </div>
          )}
          {node.model && (
            <div>
              <span className="text-sm text-[#4a4a52]">Model</span>
              <p className="mt-0.5 text-xs font-mono text-amber-400">{node.model}</p>
            </div>
          )}
          {node.system_prompt && (
            <div>
              <span className="text-sm text-[#4a4a52]">System Prompt</span>
              <pre className="mt-1 text-xs text-[#80808a] bg-[#131315] border border-[#252528] rounded-lg p-3 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed">
                {node.system_prompt}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* CAO Debug Section */}
      {node.agent?.startsWith('cao://') && (
        <CaoDebugSection artifacts={node.artifacts} duration_s={node.duration_s} />
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
      return <CheckCircle2 size={16} className="text-emerald-400" />;
    case 'failed':
      return <XCircle size={16} className="text-red-400" />;
    case 'running':
      return <Clock size={16} className="text-amber-400 animate-pulse" />;
    case 'skipped':
      return <SkipForward size={16} className="text-[#4a4a52]" />;
    default:
      return <Clock size={16} className="text-[#4a4a52]" />;
  }
}

/** CAO adapter debug section — shows raw/parsed output, elapsed time, terminal ID. */
function CaoDebugSection({
  artifacts,
  duration_s,
}: {
  artifacts: DebugArtifact[];
  duration_s: number | null;
}) {
  const [rawExpanded, setRawExpanded] = useState(false);

  const rawOutput = artifacts.find((a) => a.type === 'cao_raw_output');
  const parsedOutput = artifacts.find((a) => a.type === 'cao_output');

  const asText = (c: DebugArtifact['content']): string =>
    typeof c === 'string' ? c : JSON.stringify(c ?? '');

  // Extract terminal_id from parsed output JSON (best-effort)
  let terminalId: string | null = null;
  if (parsedOutput) {
    try {
      const parsed = JSON.parse(asText(parsedOutput.content));
      terminalId = parsed.terminal_id ?? parsed.session_id ?? null;
    } catch {
      // not JSON — ignore
    }
  }

  if (!rawOutput && !parsedOutput) return null;

  return (
    <div className="border-t border-[#252528] pt-3 space-y-3">
      <div className="flex items-center gap-2">
        <Terminal size={14} className="text-orange-400" />
        <span className="text-sm font-semibold text-orange-400">CAO Adapter</span>
      </div>

      {/* Elapsed time */}
      {duration_s !== null && (
        <div className="text-sm">
          <span className="text-[#4a4a52]">Elapsed</span>
          <p className="mt-0.5 font-mono text-[#80808a]">
            {duration_s >= 60
              ? `${Math.floor(duration_s / 60)}m ${(duration_s % 60).toFixed(1)}s`
              : `${duration_s.toFixed(3)}s`}
          </p>
        </div>
      )}

      {/* Terminal ID */}
      {terminalId && (
        <div className="text-sm">
          <span className="text-[#4a4a52]">Terminal ID</span>
          <p className="mt-0.5 font-mono text-xs text-[#80808a] break-all">{terminalId}</p>
        </div>
      )}

      {/* Parsed output */}
      {parsedOutput && (
        <div className="text-sm">
          <span className="text-[#4a4a52]">Parsed Output</span>
          <pre className="mt-1 text-xs text-[#80808a] bg-[#131315] border border-[#252528] rounded-lg p-3 whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed">
            {asText(parsedOutput.content)}
          </pre>
        </div>
      )}

      {/* Collapsible raw output */}
      {rawOutput && (
        <div className="text-sm">
          <button
            onClick={() => setRawExpanded((v) => !v)}
            className="flex items-center gap-1 text-[#4a4a52] hover:text-[#80808a] transition-colors"
          >
            {rawExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            Raw Output
          </button>
          {rawExpanded && (
            <pre className="mt-1 text-xs text-[#80808a] bg-[#131315] border border-[#252528] rounded-lg p-3 whitespace-pre-wrap max-h-64 overflow-y-auto leading-relaxed font-mono">
              {asText(rawOutput.content)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function DebugNodeDetailSkeleton() {
  return (
    <div className="flex-1 border border-[#252528] rounded-lg bg-[#1a1a1d]/50 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-32 bg-[#252528]" />
        <Skeleton className="h-6 w-20 bg-[#252528]" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-1">
            <Skeleton className="h-3 w-16 bg-[#252528]" />
            <Skeleton className="h-5 w-24 bg-[#252528]" />
          </div>
        ))}
      </div>
      <Skeleton className="h-24 w-full bg-[#252528]" />
    </div>
  );
}
