import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Trash2, Eye } from 'lucide-react';
import { getCaoSessions, deleteCaoSession, type CaoSession } from '@/lib/api';

export function OrphanedSessionsBanner() {
  const queryClient = useQueryClient();
  const [cleaning, setCleaning] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const { data } = useQuery({
    queryKey: ['cao-sessions'],
    queryFn: getCaoSessions,
    retry: 1,
    staleTime: 30_000,
    // Silently fail — banner just won't show if server unavailable
    meta: { suppressError: true },
  });

  const orphaned = (data?.sessions ?? []).filter(
    (s: CaoSession) => s.status === 'orphaned',
  );

  if (orphaned.length === 0) return null;

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      for (const session of orphaned) {
        await deleteCaoSession(session.terminal_id);
      }
      await queryClient.invalidateQueries({ queryKey: ['cao-sessions'] });
    } finally {
      setCleaning(false);
    }
  };

  return (
    <div className="bg-amber-900/20 border border-amber-700/50 rounded-lg px-4 py-3 mb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-amber-400 text-sm">
          <AlertTriangle size={16} className="shrink-0" />
          <span>
            {orphaned.length} orphaned CAO session{orphaned.length > 1 ? 's' : ''} found.
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDetails((v) => !v)}
            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-amber-700/50 text-amber-400 hover:bg-amber-900/30 transition-colors"
          >
            <Eye size={12} />
            {showDetails ? 'Hide' : 'View'}
          </button>
          <button
            onClick={handleCleanup}
            disabled={cleaning}
            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-red-700/50 text-red-400 hover:bg-red-900/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Trash2 size={12} />
            {cleaning ? 'Cleaning...' : 'Clean up'}
          </button>
        </div>
      </div>

      {showDetails && (
        <div className="mt-3 space-y-1">
          {orphaned.map((s) => (
            <div
              key={s.terminal_id}
              className="flex items-center gap-3 text-xs text-[#80808a] font-mono bg-[#1a1a1d]/50 rounded px-3 py-1.5"
            >
              <span className="text-[#80808a]">{s.terminal_id.slice(0, 12)}</span>
              <span>{s.node_name}</span>
              <span className="text-[#4a4a52]">{s.run_id.slice(0, 8)}</span>
              <span className="ml-auto text-[#4a4a52]">
                {new Date(s.started_at).toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
