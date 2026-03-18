import { useState, useEffect, useRef } from 'react';

interface SaveAsModalProps {
  onSave: (path: string) => void;
  onClose: () => void;
  isPending: boolean;
  initialFilename?: string;
}

export function SaveAsModal({ onSave, onClose, isPending, initialFilename }: SaveAsModalProps) {
  const [filename, setFilename] = useState(initialFilename ?? 'my-workflow.yaml');
  const modalRef = useRef<HTMLDivElement>(null);

  const handleSubmit = () => {
    const path = filename.endsWith('.yaml') ? filename : `${filename}.yaml`;
    onSave(path);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    const modal = modalRef.current;
    if (!modal) return;
    const focusable = modal.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    first?.focus();
    const trap = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last?.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
    };
    modal.addEventListener('keydown', trap);
    return () => modal.removeEventListener('keydown', trap);
  }, []);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="save-as-modal-title"
        className="bg-slate-800 rounded-lg shadow-xl border border-slate-700 w-full max-w-sm p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="save-as-modal-title" className="text-lg font-semibold text-slate-100 mb-4">Save Workflow</h3>
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
