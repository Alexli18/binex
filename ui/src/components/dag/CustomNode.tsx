import { Handle, Position, type NodeProps } from 'reactflow';
import { Bot, Monitor, Globe, User, Cog } from 'lucide-react';
import type { WorkflowNode } from '../../lib/yaml-to-graph';
import { getNodeTypeColors, getStatusColors } from '../../lib/design-tokens';

const typeIcons: Record<string, React.ElementType> = {
  llm: Bot,
  local: Monitor,
  a2a: Globe,
  human: User,
};

export function CustomNode({ data }: NodeProps<WorkflowNode>) {
  const Icon = typeIcons[data.type] || Cog;
  const typeTokens = getNodeTypeColors(data.type);
  const statusTokens = getStatusColors(data.status || 'pending');
  const isRunning = data.status === 'running';
  const border = `${statusTokens.border}${isRunning ? ' animate-pulse' : ''}`;

  return (
    <div
      className={`bg-slate-800 rounded-lg border-2 ${border} px-4 py-2.5 shadow-lg shadow-black/20 min-w-[180px] max-w-[220px]`}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-500 !border-slate-400" />
      <div className="flex items-center gap-2">
        <Icon size={16} className={`shrink-0 ${typeTokens.icon}`} />
        <span className="text-sm font-medium text-slate-100 truncate">{data.label}</span>
      </div>
      {data.status && (
        <div className={`text-xs mt-1 capitalize ${statusTokens.text}`}>{data.status}</div>
      )}
      {data.patternGroup && (
        <div className="text-[9px] text-pink-400 mt-0.5 truncate">
          ⬡ {data.patternType ?? 'pattern'}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-slate-500 !border-slate-400" />
    </div>
  );
}
