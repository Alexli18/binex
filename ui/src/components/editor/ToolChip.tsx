import { Wrench, Server, Code, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ToolChipProps {
  uri: string;
  onRemove?: () => void;
}

function chipStyle(uri: string) {
  if (uri.startsWith('builtin://')) return { icon: Wrench, bg: 'bg-amber-500/15 text-amber-300 border-amber-500/30' };
  if (uri.startsWith('mcp://')) return { icon: Server, bg: 'bg-purple-500/15 text-purple-300 border-purple-500/30' };
  return { icon: Code, bg: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' };
}

function chipLabel(uri: string) {
  if (uri.startsWith('builtin://')) return uri.slice('builtin://'.length);
  if (uri.startsWith('mcp://')) return uri.slice('mcp://'.length);
  if (uri.startsWith('python://')) return uri.slice('python://'.length);
  return uri;
}

export function ToolChip({ uri, onRemove }: ToolChipProps) {
  const { icon: Icon, bg } = chipStyle(uri);
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium border',
        bg,
      )}
    >
      <Icon size={9} className="shrink-0" />
      <span className="truncate max-w-[120px]">{chipLabel(uri)}</span>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="ml-0.5 hover:text-white transition-colors"
        >
          <X size={9} />
        </button>
      )}
    </span>
  );
}
