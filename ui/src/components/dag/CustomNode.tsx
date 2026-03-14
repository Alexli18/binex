import { Handle, Position, type NodeProps } from 'reactflow';
import { Bot, Monitor, Globe, User, Cog } from 'lucide-react';
import type { WorkflowNode } from '../../lib/yaml-to-graph';

const typeIcons: Record<string, React.ElementType> = {
  llm: Bot,
  local: Monitor,
  a2a: Globe,
  human: User,
};

const typeColors: Record<string, string> = {
  llm: 'text-blue-400',
  local: 'text-green-400',
  a2a: 'text-cyan-400',
  human: 'text-purple-400',
};

const statusBorders: Record<string, string> = {
  completed: 'border-green-500',
  running: 'border-blue-500 animate-pulse',
  failed: 'border-red-500',
  pending: 'border-slate-600',
  skipped: 'border-slate-700',
};

export function CustomNode({ data }: NodeProps<WorkflowNode>) {
  const Icon = typeIcons[data.type] || Cog;
  const iconColor = typeColors[data.type] || 'text-slate-400';
  const border = statusBorders[data.status || 'pending'] || 'border-slate-600';

  return (
    <div
      className={`bg-slate-800 rounded-lg border-2 ${border} px-4 py-2.5 shadow-lg shadow-black/20 min-w-[180px] max-w-[220px]`}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-500 !border-slate-400" />
      <div className="flex items-center gap-2">
        <Icon size={16} className={`shrink-0 ${iconColor}`} />
        <span className="text-sm font-medium text-slate-100 truncate">{data.label}</span>
      </div>
      {data.status && (
        <div className="text-xs text-slate-500 mt-1 capitalize">{data.status}</div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-slate-500 !border-slate-400" />
    </div>
  );
}
