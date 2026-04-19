import { useState, useMemo } from 'react';
import { Download, Check } from 'lucide-react';

const statusClasses: Record<string, string> = {
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
  running: 'bg-amber-500/20 text-amber-400',
};
import { useRuns } from '../hooks/useRuns';
import { useExport } from '../hooks/useUtilities';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { ErrorState } from '@/components/layout/ErrorState';
import { LoadingState } from '@/components/layout/LoadingState';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

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
        new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
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
    <PageShell>
      <Breadcrumb items={[{ label: 'Dashboard', href: '/' }, { label: 'Export' }]} className="mb-4" />

      <PageHeader
        title="Export Run Data"
        description="Download workflow run data in CSV or JSON format"
      />

      <div className="mt-6 flex flex-col gap-6 max-w-4xl">
        {/* Selection mode */}
        <div className="border border-[#252528] rounded-card bg-[#1a1a1d]/50 p-4 space-y-4">
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-[#80808a] cursor-pointer">
              <input
                type="radio"
                checked={!useLastN}
                onChange={() => setUseLastN(false)}
                className="text-amber-400"
              />
              Select specific runs
            </label>
            <label className="flex items-center gap-2 text-sm text-[#80808a] cursor-pointer">
              <input
                type="radio"
                checked={useLastN}
                onChange={() => setUseLastN(true)}
                className="text-amber-400"
              />
              Last N runs
            </label>
          </div>

          {useLastN ? (
            <div className="flex items-center gap-3">
              <label className="text-sm text-[#80808a]">Number of runs:</label>
              <Input
                type="number"
                min={1}
                max={1000}
                value={lastN}
                onChange={(e) => setLastN(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-24"
              />
            </div>
          ) : (
            <div>
              {loadingRuns ? (
                <LoadingState message="Loading runs..." variant="inline" />
              ) : runsError ? (
                <ErrorState
                  title="Failed to load runs"
                  message={runsError instanceof Error ? runsError.message : String(runsError)}
                />
              ) : sortedRuns.length === 0 ? (
                <p className="text-[#4a4a52] text-sm">No runs available.</p>
              ) : (
                <div className="border border-[#252528] rounded-card overflow-hidden max-h-64 overflow-y-auto">
                  <table className="min-w-full text-sm">
                    <thead className="sticky top-0 bg-[#131315]">
                      <tr className="border-b border-[#252528]">
                        <th className="text-left px-3 py-2 w-8">
                          <input
                            type="checkbox"
                            checked={
                              sortedRuns.length > 0 &&
                              selectedRunIds.size === sortedRuns.length
                            }
                            onChange={toggleAll}
                            className="rounded border-[#333338] bg-[#131315] text-amber-400"
                            aria-label="Select all runs"
                          />
                        </th>
                        <th className="text-left px-3 py-2 font-medium text-[#80808a]">
                          Run ID
                        </th>
                        <th className="text-left px-3 py-2 font-medium text-[#80808a]">
                          Workflow
                        </th>
                        <th className="text-left px-3 py-2 font-medium text-[#80808a]">
                          Status
                        </th>
                        <th className="text-left px-3 py-2 font-medium text-[#80808a]">
                          Created
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#252528]/50">
                      {sortedRuns.map((run) => (
                        <tr
                          key={run.run_id}
                          className="hover:bg-[#1a1a1d]/30 cursor-pointer transition-colors"
                          onClick={() => toggleRun(run.run_id)}
                        >
                          <td className="px-3 py-2">
                            <input
                              type="checkbox"
                              checked={selectedRunIds.has(run.run_id)}
                              onChange={() => toggleRun(run.run_id)}
                              onClick={(e) => e.stopPropagation()}
                              className="rounded border-[#333338] bg-[#131315] text-amber-400"
                              aria-label={`Select run ${run.run_id}`}
                            />
                          </td>
                          <td className="px-3 py-2 font-mono text-xs text-[#80808a]">
                            {run.run_id.slice(0, 12)}...
                          </td>
                          <td className="px-3 py-2 text-[#80808a]">
                            {run.workflow_name}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={`text-xs px-1.5 py-0.5 rounded ${statusClasses[run.status] ?? 'bg-[#333338]/20 text-[#80808a]'}`}
                            >
                              {run.status}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-xs text-[#4a4a52]">
                            {new Date(run.started_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {selectedRunIds.size > 0 && (
                <p className="text-xs text-[#4a4a52] mt-2">
                  {selectedRunIds.size} run{selectedRunIds.size > 1 ? 's' : ''} selected
                </p>
              )}
            </div>
          )}
        </div>

        {/* Options */}
        <div className="border border-[#252528] rounded-card bg-[#1a1a1d]/50 p-4 space-y-4">
          <h3 className="text-sm font-medium text-[#80808a]">Export Options</h3>

          {/* Format */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#80808a]">Format:</span>
            <div className="flex gap-1 border border-[#252528] rounded-lg bg-[#131315] p-0.5">
              {(['csv', 'json'] as FormatOption[]).map((f) => (
                <Button
                  key={f}
                  onClick={() => setFormat(f)}
                  variant={format === f ? 'default' : 'ghost'}
                  size="sm"
                  className={format === f ? '' : 'text-[#80808a] hover:text-[#f0f0f0]'}
                >
                  {f.toUpperCase()}
                </Button>
              ))}
            </div>
          </div>

          {/* Include artifacts */}
          <label className="flex items-center gap-2 text-sm text-[#80808a] cursor-pointer">
            <input
              type="checkbox"
              checked={includeArtifacts}
              onChange={(e) => setIncludeArtifacts(e.target.checked)}
              className="rounded border-[#333338] bg-[#131315] text-amber-400"
            />
            Include artifacts
          </label>
        </div>

        {/* Download button */}
        <div className="flex items-center gap-3">
          <Button
            onClick={handleDownload}
            disabled={!canDownload || exportMutation.isPending}
          >
            {exportMutation.isPending ? (
              'Exporting...'
            ) : (
              <>
                <Download size={16} className="mr-2" />
                Download {format.toUpperCase()}
              </>
            )}
          </Button>
          {exportMutation.isSuccess && (
            <span className="flex items-center gap-1 text-sm text-emerald-400">
              <Check size={16} />
              Downloaded
            </span>
          )}
        </div>

        {exportMutation.error && (
          <div className="rounded-card bg-red-900/30 border border-red-700/50 p-3 text-sm text-red-300">
            {exportMutation.error.message}
          </div>
        )}
      </div>
    </PageShell>
  );
}
