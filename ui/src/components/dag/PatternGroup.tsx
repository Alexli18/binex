import { ChevronDown, ChevronRight } from 'lucide-react';

// Icon map for pattern types
const PATTERN_LABELS: Record<string, string> = {
  critic: 'Critic',
  debate: 'Debate',
  best_of_n: 'Best of N',
  reflexion: 'Reflexion',
  scatter: 'Scatter',
  fsm: 'State Machine',
  constitutional: 'Constitutional',
  chain_of_verification: 'Verify Chain',
  plan_execute: 'Plan & Execute',
};

interface PatternGroupProps {
  groupId: string;
  patternType: string;
  childCount: number;
  collapsed: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

export function PatternGroup({
  groupId,
  patternType,
  childCount,
  collapsed,
  onToggle,
  children,
}: PatternGroupProps) {
  const label = PATTERN_LABELS[patternType] ?? patternType;

  return (
    <div className="relative rounded-lg border-2 border-dashed border-pink-500/40 bg-pink-950/10 p-2">
      {/* Header */}
      <button
        onClick={onToggle}
        className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-pink-900/20 transition-colors text-left w-full"
      >
        {collapsed ? (
          <ChevronRight size={14} className="text-pink-400" />
        ) : (
          <ChevronDown size={14} className="text-pink-400" />
        )}
        <span className="text-xs font-medium text-pink-300">{label}</span>
        <span className="text-[10px] text-pink-500 ml-1">({groupId})</span>
        {collapsed && (
          <span className="text-[10px] text-slate-500 ml-auto">{childCount} nodes</span>
        )}
      </button>

      {/* Children */}
      {!collapsed && <div className="mt-1">{children}</div>}
    </div>
  );
}
