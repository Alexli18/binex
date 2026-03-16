import { Handle, Position, type NodeProps } from 'reactflow';
import { Bot, Monitor, Globe, User, Cog } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface BisectNodeData {
  label: string;
  type: string;
  bisectStatus: 'match' | 'divergence' | 'downstream' | 'missing';
  similarity: number | null;
}

const typeIcons: Record<string, React.ElementType> = {
  llm: Bot,
  local: Monitor,
  a2a: Globe,
  human: User,
};

const bisectStyles = {
  match: {
    border: 'border-emerald-500',
    bg: 'bg-slate-800',
    glow: '',
    animate: '',
  },
  divergence: {
    border: 'border-red-500',
    bg: 'bg-red-500/5',
    glow: 'shadow-[0_0_12px_rgba(239,68,68,0.3)]',
    animate: 'animate-pulse',
  },
  downstream: {
    border: 'border-orange-500',
    bg: 'bg-orange-500/5',
    glow: '',
    animate: '',
  },
  missing: {
    border: 'border-slate-600 border-dashed',
    bg: 'bg-slate-800/50',
    glow: '',
    animate: '',
  },
} as const;

export function BisectNode({ data }: NodeProps<BisectNodeData>) {
  const Icon = typeIcons[data.type] || Cog;
  const style = bisectStyles[data.bisectStatus] || bisectStyles.missing;
  const similarityPct = data.similarity !== null ? Math.round(data.similarity * 100) : null;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          className={`${style.bg} rounded-lg border-2 ${style.border} ${style.glow} ${style.animate} px-4 py-2.5 shadow-lg shadow-black/20 min-w-[140px] max-w-[180px]`}
        >
          <Handle type="target" position={Position.Top} className="!bg-slate-500 !border-slate-400" />
          <div className="flex items-center gap-2">
            <Icon size={14} className="shrink-0 text-slate-400" />
            <span className="text-sm font-medium text-slate-100 truncate">{data.label}</span>
          </div>
          <Handle type="source" position={Position.Bottom} className="!bg-slate-500 !border-slate-400" />
        </div>
      </TooltipTrigger>
      <TooltipContent side="right" className="text-xs">
        <p className="font-mono">{data.label}</p>
        <p className="text-slate-400 capitalize">{data.bisectStatus.replace('_', ' ')}</p>
        {similarityPct !== null && <p>Similarity: {similarityPct}%</p>}
      </TooltipContent>
    </Tooltip>
  );
}
