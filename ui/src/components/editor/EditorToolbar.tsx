import { FolderOpen, DollarSign } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export type EditorMode = 'visual' | 'yaml';

export interface EditorToolbarProps {
  selectedPath: string | null;
  isDirty: boolean;
  mode: EditorMode;
  showFiles: boolean;
  showCost: boolean;
  isSaving: boolean;
  isRunning: boolean;
  hasContent: boolean;
  onToggleFiles: () => void;
  onToggleCost: () => void;
  onSwitchToVisual: () => void;
  onSwitchToYaml: () => void;
  onSave: () => void;
  onRun: () => void;
}

export function EditorToolbar({
  selectedPath,
  isDirty,
  mode,
  showFiles,
  showCost,
  isSaving,
  isRunning,
  hasContent,
  onToggleFiles,
  onToggleCost,
  onSwitchToVisual,
  onSwitchToYaml,
  onSave,
  onRun,
}: EditorToolbarProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-slate-900 border-b border-slate-700">
      <span className="text-sm font-medium text-slate-200">
        {selectedPath ?? (hasContent ? '(new workflow)' : 'No file selected')}
      </span>
      {isDirty && (
        <span className="text-xs text-amber-400 font-medium">(unsaved changes)</span>
      )}
      <div className="flex-1" />

      {/* Panel toggles */}
      <div className="flex items-center gap-1">
        <button
          onClick={onToggleFiles}
          className={cn(
            'p-1.5 rounded text-xs',
            showFiles ? 'text-blue-400 bg-slate-700' : 'text-slate-500 hover:text-slate-300',
          )}
          title="Toggle file browser"
        >
          <FolderOpen size={14} />
        </button>
        <button
          onClick={onToggleCost}
          className={cn(
            'p-1.5 rounded text-xs',
            showCost ? 'text-blue-400 bg-slate-700' : 'text-slate-500 hover:text-slate-300',
          )}
          title="Toggle cost estimate"
        >
          <DollarSign size={14} />
        </button>
      </div>

      {/* Mode toggle */}
      <div className="flex rounded overflow-hidden border border-slate-600">
        <button
          onClick={onSwitchToVisual}
          className={cn(
            'px-3 py-1 text-xs font-medium transition-colors',
            mode === 'visual'
              ? 'bg-blue-600 text-white'
              : 'bg-slate-800 text-slate-400 hover:text-slate-200',
          )}
        >
          Visual
        </button>
        <button
          onClick={onSwitchToYaml}
          className={cn(
            'px-3 py-1 text-xs font-medium transition-colors',
            mode === 'yaml'
              ? 'bg-blue-600 text-white'
              : 'bg-slate-800 text-slate-400 hover:text-slate-200',
          )}
        >
          YAML
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
      >
        {isRunning ? 'Starting...' : 'Run'}
      </Button>
    </div>
  );
}
