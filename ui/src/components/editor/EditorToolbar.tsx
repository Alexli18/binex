import { FolderOpen } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export type EditorMode = 'visual' | 'yaml';

export interface EditorToolbarProps {
  selectedPath: string | null;
  isDirty: boolean;
  mode: EditorMode;
  isSaving: boolean;
  isRunning: boolean;
  hasContent: boolean;
  onOpenFiles: () => void;
  onSwitchToVisual: () => void;
  onSwitchToYaml: () => void;
  onSave: () => void;
  onRun: () => void;
}

export function EditorToolbar({
  selectedPath,
  isDirty,
  mode,
  isSaving,
  isRunning,
  hasContent,
  onOpenFiles,
  onSwitchToVisual,
  onSwitchToYaml,
  onSave,
  onRun,
}: EditorToolbarProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-slate-900 border-b border-slate-700/50">
      {/* Open file button + current filename */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onOpenFiles}
        className="gap-2 text-slate-400 hover:text-slate-200"
      >
        <FolderOpen size={15} />
        Open
      </Button>

      <span className="text-sm font-medium text-slate-200 truncate max-w-[300px]">
        {selectedPath ?? (hasContent ? '(new workflow)' : '')}
      </span>

      {isDirty && (
        <span className="text-xs text-amber-400 font-medium">(unsaved)</span>
      )}

      <div className="flex-1" />

      {/* Mode toggle pill */}
      <div className="flex rounded-lg overflow-hidden border border-slate-600/50 bg-slate-800/50" role="group" aria-label="Editor mode">
        <button
          onClick={onSwitchToYaml}
          aria-label="Switch to YAML editor"
          aria-pressed={mode === 'yaml'}
          className={cn(
            'px-3.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-900',
            mode === 'yaml'
              ? 'bg-blue-600 text-white'
              : 'text-slate-400 hover:text-slate-200',
          )}
        >
          YAML
        </button>
        <button
          onClick={onSwitchToVisual}
          aria-label="Switch to visual editor"
          aria-pressed={mode === 'visual'}
          className={cn(
            'px-3.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 focus-visible:ring-offset-slate-900',
            mode === 'visual'
              ? 'bg-blue-600 text-white'
              : 'text-slate-400 hover:text-slate-200',
          )}
        >
          Visual
        </button>
      </div>

      <Button
        variant="outline"
        size="sm"
        onClick={onSave}
        disabled={
          (!selectedPath && !hasContent) ||
          (!!selectedPath && !isDirty) ||
          isSaving
        }
      >
        {isSaving ? 'Saving...' : 'Save'}
      </Button>
      <Button
        size="sm"
        onClick={onRun}
        disabled={!hasContent || isRunning}
        className="bg-blue-600 hover:bg-blue-500"
      >
        {isRunning ? 'Starting...' : 'Run'}
      </Button>
    </div>
  );
}
