import { useState } from 'react';
import { ChevronRight, X, BookOpen } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ModelSelect } from './ModelSelect';
import { PromptLibraryPanel } from '../../pages/PromptLibrary';

export interface PatternStepEditorProps {
  stepKey: string;
  label: string;
  model: string;
  prompt: string;
  maxRetries: number | undefined;
  defaultPrompt?: string;
  onChange: (model: string, prompt: string, maxRetries: number | undefined) => void;
}

export function PatternStepEditor({ stepKey: _stepKey, label, model, prompt, maxRetries, defaultPrompt, onChange }: PatternStepEditorProps) {
  const [open, setOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);

  const modelDisplay = model
    ? (model.split('/').pop() ?? model).slice(0, 16)
    : 'inherit';

  return (
    <div className="border border-[#252528] rounded text-[11px]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 w-full px-2 py-1 hover:bg-[#1a1a1d]/50 transition-colors"
      >
        <ChevronRight
          size={10}
          className={cn('transition-transform duration-150 shrink-0 text-[#4a4a52]', open && 'rotate-90')}
        />
        <span className="text-[#80808a] font-medium truncate">{label}</span>
        <span
          className={cn(
            'ml-auto text-[10px] shrink-0',
            model ? 'text-[#80808a]' : 'text-[#4a4a52] italic',
          )}
        >
          {modelDisplay}
        </span>
      </button>

      {open && (
        <div className="px-2 pb-2 space-y-1.5 border-t border-[#252528]">
          <div className="pt-1.5">
            <div className="flex items-center justify-between mb-0.5">
              <label className="text-[10px] text-[#4a4a52]">Model</label>
              {model && (
                <button
                  type="button"
                  title="Inherit from default"
                  onClick={() => onChange('', prompt, maxRetries)}
                  className="text-[#4a4a52] hover:text-[#80808a] transition-colors"
                >
                  <X size={10} />
                </button>
              )}
            </div>
            <ModelSelect
              value={model}
              onChange={(v) => onChange(v, prompt, maxRetries)}
              inheritOption
            />
          </div>
          <div>
            <div className="flex items-center justify-between mb-0.5">
              <label className="text-[10px] text-[#4a4a52]">Prompt override</label>
              <div className="flex items-center gap-2">
                {defaultPrompt && (
                  <button
                    type="button"
                    onClick={() => onChange(model, defaultPrompt, maxRetries)}
                    className="text-[10px] text-[#4a4a52] hover:text-[#80808a] transition-colors"
                    title={`Load default: "${defaultPrompt.slice(0, 60)}..."`}
                  >
                    Default
                  </button>
                )}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setLibraryOpen(true); }}
                  className="flex items-center gap-1 transition-colors text-[10px]"
                  style={{ color: '#e8a020' }}
                  title="Browse prompt library"
                >
                  <BookOpen size={10} />
                  Browse
                </button>
              </div>
            </div>
            <textarea
              value={prompt}
              onChange={(e) => onChange(model, e.target.value, maxRetries)}
              placeholder="Leave empty to use node-level prompt..."
              rows={3}
              className="w-full bg-[#0b0b0c] border border-[#252528] rounded px-1.5 py-1 text-[#80808a] resize-none text-[10px] focus:outline-none focus:border-[#e8a020]/50 placeholder:text-[#333338]"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          <div>
            <label className="flex items-center justify-between gap-2">
              <span className="text-[10px] text-[#4a4a52]">Max retries</span>
              <input
                type="number"
                min={1}
                max={10}
                value={maxRetries ?? ''}
                onChange={(e) => {
                  const v = e.target.value === '' ? undefined : parseInt(e.target.value, 10);
                  onChange(model, prompt, v);
                }}
                placeholder="inherit"
                className="w-16 px-1.5 py-0.5 text-[11px] bg-[#1a1a1d] border border-[#252528] rounded text-[#f0f0f0] text-right placeholder:text-[#4a4a52]"
                onClick={(e) => e.stopPropagation()}
              />
            </label>
          </div>
        </div>
      )}

      {libraryOpen && (
        <PromptLibraryPanel
          open={libraryOpen}
          onClose={() => setLibraryOpen(false)}
          onUse={(content) => {
            onChange(model, content, maxRetries);
            setLibraryOpen(false);
          }}
        />
      )}
    </div>
  );
}
