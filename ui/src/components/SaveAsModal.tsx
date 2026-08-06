import { useState } from 'react';

interface SaveAsModalProps {
  onSave: (path: string) => void;
  onClose: () => void;
  isPending: boolean;
}

export function SaveAsModal({ onSave, onClose, isPending }: SaveAsModalProps) {
  const [filename, setFilename] = useState('my-workflow.yaml');

  const handleSubmit = () => {
    const path = filename.endsWith('.yaml') ? filename : `${filename}.yaml`;
    onSave(path);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div data-testid="save-as-modal" className="bg-[#131315] rounded-modal shadow-xl border border-[#252528]/60 w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-[#f0f0f0] mb-4">Save Workflow</h3>
        <label className="block text-sm font-medium text-[#80808a] mb-1">Filename</label>
        <input
          type="text"
          value={filename}
          data-testid="save-as-filename-input"
          onChange={(e) => setFilename(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          className="w-full border border-[#333338] rounded px-3 py-1.5 text-sm bg-[#252528] text-[#f0f0f0] mb-4 focus:outline-none focus:border-amber-500"
          autoFocus
        />
        <div className="flex justify-end gap-2">
          <button onClick={onClose} data-testid="save-as-cancel-btn" className="px-4 py-1.5 text-sm border border-[#333338] rounded text-[#80808a] hover:bg-[#252528]">Cancel</button>
          <button onClick={handleSubmit} data-testid="save-as-save-btn" disabled={!filename.trim() || isPending} className="px-4 py-1.5 text-sm bg-amber-500 text-black rounded hover:bg-amber-400 disabled:opacity-50">
            {isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
