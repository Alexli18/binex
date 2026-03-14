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
      <div className="bg-slate-800 rounded-lg shadow-xl border border-slate-700 w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-slate-100 mb-4">Save Workflow</h3>
        <label className="block text-sm font-medium text-slate-300 mb-1">Filename</label>
        <input
          type="text"
          value={filename}
          onChange={(e) => setFilename(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          className="w-full border border-slate-600 rounded px-3 py-1.5 text-sm bg-slate-700 text-slate-200 mb-4 focus:outline-none focus:border-blue-500"
          autoFocus
        />
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-1.5 text-sm border border-slate-600 rounded text-slate-300 hover:bg-slate-700">Cancel</button>
          <button onClick={handleSubmit} disabled={!filename.trim() || isPending} className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50">
            {isPending ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
