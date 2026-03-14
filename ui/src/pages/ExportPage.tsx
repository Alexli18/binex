import { useState, useMemo } from 'react';
import { Download, FileDown, Check } from 'lucide-react';
import { useRuns } from '../hooks/useRuns';
import { useExport } from '../hooks/useUtilities';

type FormatOption = 'csv' | 'json';

export default function ExportPage() {
  const { data: runs, isLoading: loadingRuns, error: runsError } = useRuns();
  const exportMutation = useExport();

  const [selectedRunIds, setSelectedRunIds] = useState<Set<string>>(new Set());
  const [useLastN, setUseLastN] = useState(false);
  const [lastN, setLastN] = useState(10);
  const [format, setFormat] = useState<FormatOption>('json');
  const [includeArtifacts, setIncludeArtifacts] = useState(true);

  const sortedRuns = useMemo(() => {
    if (!runs) return [];
    return [...runs].sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }, [runs]);

  const toggleRun = (runId: string) => {
    setSelectedRunIds((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) {
        next.delete(runId);
      } else {
        next.add(runId);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (!sortedRuns.length) return;
    if (selectedRunIds.size === sortedRuns.length) {
      setSelectedRunIds(new Set());
    } else {
      setSelectedRunIds(new Set(sortedRuns.map((r) => r.run_id)));
    }
  };

  const handleDownload = () => {
    const body = {
      format,
      include_artifacts: includeArtifacts,
      ...(useLastN
        ? { last_n: lastN }
        : { run_ids: Array.from(selectedRunIds) }),
    };

    exportMutation.mutate(body, {
      onSuccess: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `binex-export.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      },
    });
  };

  const canDownload = useLastN ? lastN > 0 : selectedRunIds.size > 0;

  return (
    <div className="p-6 flex flex-col gap-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <FileDown size={24} className="text-emerald-400" />
        <h1 className="text-xl font-bold">Export Run Data</h1>
      </div>

      {/* Selection mode */}
      <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-4 space-y-4">
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
            <input
              type="radio"
              checked={!useLastN}
              onChange={() => setUseLastN(false)}
              className="text-blue-500"
            />
            Select specific runs
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
            <input
              type="radio"
              checked={useLastN}
              onChange={() => setUseLastN(true)}
              className="text-blue-500"
            />
            Last N runs
          </label>
        </div>

        {useLastN ? (
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-400">Number of runs:</label>
            <input
              type="number"
              min={1}
              max={1000}
              value={lastN}
              onChange={(e) => setLastN(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-24 bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>
        ) : (
          <div>
            {loadingRuns ? (
              <div className="h-40 bg-slate-800 rounded animate-pulse" />
            ) : runsError ? (
              <p className="text-red-400 text-sm">
                Failed to load runs: {(runsError as Error).message}
              </p>
            ) : sortedRuns.length === 0 ? (
              <p className="text-slate-500 text-sm">No runs available.</p>
            ) : (
              <div className="border border-slate-700 rounded-lg overflow-hidden max-h-64 overflow-y-auto">
                <table className="min-w-full text-sm">
                  <thead className="sticky top-0 bg-slate-900">
                    <tr className="border-b border-slate-700">
                      <th className="text-left px-3 py-2 w-8">
                        <input
                          type="checkbox"
                          checked={
                            sortedRuns.length > 0 &&
                            selectedRunIds.size === sortedRuns.length
                          }
                          onChange={toggleAll}
                          className="rounded border-slate-600 bg-slate-900 text-blue-500"
                          aria-label="Select all runs"
                        />
                      </th>
                      <th className="text-left px-3 py-2 font-medium text-slate-400">
                        Run ID
                      </th>
                      <th className="text-left px-3 py-2 font-medium text-slate-400">
                        Workflow
                      </th>
                      <th className="text-left px-3 py-2 font-medium text-slate-400">
                        Status
                      </th>
                      <th className="text-left px-3 py-2 font-medium text-slate-400">
                        Created
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {sortedRuns.map((run) => (
                      <tr
                        key={run.run_id}
                        className="hover:bg-slate-700/30 cursor-pointer transition-colors"
                        onClick={() => toggleRun(run.run_id)}
                      >
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={selectedRunIds.has(run.run_id)}
                            onChange={() => toggleRun(run.run_id)}
                            onClick={(e) => e.stopPropagation()}
                            className="rounded border-slate-600 bg-slate-900 text-blue-500"
                            aria-label={`Select run ${run.run_id}`}
                          />
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-slate-300">
                          {run.run_id.slice(0, 12)}...
                        </td>
                        <td className="px-3 py-2 text-slate-300">
                          {run.workflow_name}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded ${
                              run.status === 'completed'
                                ? 'bg-green-500/20 text-green-400'
                                : run.status === 'failed'
                                  ? 'bg-red-500/20 text-red-400'
                                  : run.status === 'running'
                                    ? 'bg-blue-500/20 text-blue-400'
                                    : 'bg-slate-600/20 text-slate-400'
                            }`}
                          >
                            {run.status}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-500">
                          {new Date(run.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {selectedRunIds.size > 0 && (
              <p className="text-xs text-slate-500 mt-2">
                {selectedRunIds.size} run{selectedRunIds.size > 1 ? 's' : ''} selected
              </p>
            )}
          </div>
        )}
      </div>

      {/* Options */}
      <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-4 space-y-4">
        <h3 className="text-sm font-medium text-slate-300">Export Options</h3>

        {/* Format */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400">Format:</span>
          <div className="flex gap-1 border border-slate-700 rounded-lg bg-slate-900 p-0.5">
            {(['csv', 'json'] as FormatOption[]).map((f) => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                className={`px-3 py-1 text-sm rounded-md transition-colors ${
                  format === f
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {f.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Include artifacts */}
        <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
          <input
            type="checkbox"
            checked={includeArtifacts}
            onChange={(e) => setIncludeArtifacts(e.target.checked)}
            className="rounded border-slate-600 bg-slate-900 text-blue-500"
          />
          Include artifacts
        </label>
      </div>

      {/* Download button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleDownload}
          disabled={!canDownload || exportMutation.isPending}
          className="flex items-center gap-2 px-5 py-2 text-sm font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {exportMutation.isPending ? (
            'Exporting...'
          ) : (
            <>
              <Download size={16} />
              Download {format.toUpperCase()}
            </>
          )}
        </button>
        {exportMutation.isSuccess && (
          <span className="flex items-center gap-1 text-sm text-emerald-400">
            <Check size={16} />
            Downloaded
          </span>
        )}
      </div>

      {exportMutation.error && (
        <div className="rounded-md bg-red-900/30 border border-red-700/50 p-3 text-sm text-red-300">
          {exportMutation.error.message}
        </div>
      )}
    </div>
  );
}
