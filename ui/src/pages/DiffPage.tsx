import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useRuns } from '../hooks/useRuns';
import { useDiff } from '../hooks/useComparison';
import { StatusBadge } from '../components/common/StatusBadge';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { ArrowRight, AlertCircle } from 'lucide-react';
import { ArtifactDiff } from '@/components/common/ArtifactDiff';
import { cn } from '@/lib/utils';
import { statusColors } from '@/lib/design-tokens';
import type { NodeDiff } from '../hooks/useComparison';

type DiffFilter = 'all' | 'changed' | 'failed' | 'cost_delta';

function formatDelta(a: number | null, b: number | null, isCost: boolean): string | null {
  if (a === null || b === null) return null;
  const delta = b - a;
  if (delta === 0) return '';
  const sign = delta > 0 ? '+' : '';
  if (isCost) return `${sign}$${delta.toFixed(6)}`;
  return `${sign}${delta.toFixed(0)}ms`;
}

export default function DiffPage() {
  const [searchParams] = useSearchParams();
  const initialRunA = searchParams.get('runA') ?? '';
  const initialRunB = searchParams.get('runB') ?? '';

  const { data: runs, isLoading: runsLoading } = useRuns();
  const diff = useDiff();

  const [runA, setRunA] = useState(initialRunA);
  const [runB, setRunB] = useState(initialRunB);

  // Auto-compare when both params provided
  useEffect(() => {
    if (initialRunA && initialRunB) {
      diff.mutate({ run_a: initialRunA, run_b: initialRunB });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [expandedDiffs, setExpandedDiffs] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<DiffFilter>('all');

  const filterCounts = useMemo(() => {
    if (!diff.data) return { all: 0, changed: 0, failed: 0, cost_delta: 0 };
    const diffs = diff.data.node_diffs;
    return {
      all: diffs.length,
      changed: diffs.filter(nd => nd.status_a !== nd.status_b || nd.artifact_diff !== null).length,
      failed: diffs.filter(nd => nd.status_a === 'failed' || nd.status_b === 'failed').length,
      cost_delta: diffs.filter(nd => nd.cost_a !== null && nd.cost_b !== null && Math.abs(nd.cost_a - nd.cost_b) > 0).length,
    };
  }, [diff.data]);

  const filteredNodeDiffs = useMemo(() => {
    if (!diff.data) return [];
    const diffs = diff.data.node_diffs;
    switch (filter) {
      case 'changed':
        return diffs.filter(nd => nd.status_a !== nd.status_b || nd.artifact_diff !== null);
      case 'failed':
        return diffs.filter(nd => nd.status_a === 'failed' || nd.status_b === 'failed');
      case 'cost_delta':
        return diffs.filter(nd => nd.cost_a !== null && nd.cost_b !== null && Math.abs(nd.cost_a - nd.cost_b) > 0);
      default:
        return diffs;
    }
  }, [diff.data, filter]);

  const handleCompare = () => {
    if (runA && runB) {
      diff.mutate({ run_a: runA, run_b: runB });
    }
  };

  const toggleDiff = (nodeId: string) => {
    setExpandedDiffs((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  };

  return (
    <PageShell>
      <Breadcrumb items={[{ label: 'Dashboard', href: '/' }, { label: 'Diff' }]} className="mb-4" />

      <PageHeader
        title="Compare Runs"
        description="Side-by-side comparison of two workflow runs"
      />

      <div className="mt-6 flex flex-col gap-6">
        {/* Selectors */}
        <div className="bg-[#1a1a1d] border border-[#252528] rounded-card p-4">
          <div className="flex flex-col md:flex-row items-end gap-4">
            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-[#80808a] mb-1">Run A</label>
              <Select value={runA} onValueChange={setRunA}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a run..." />
                </SelectTrigger>
                <SelectContent>
                  {runsLoading && (
                    <SelectItem value="__loading" disabled>Loading...</SelectItem>
                  )}
                  {runs?.map((r) => (
                    <SelectItem key={r.run_id} value={r.run_id}>
                      {r.workflow_name} — {r.run_id.slice(0, 8)} ({r.status})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <ArrowRight className="w-5 h-5 text-[#4a4a52] hidden md:block mb-2" />

            <div className="flex-1 w-full">
              <label className="block text-sm font-medium text-[#80808a] mb-1">Run B</label>
              <Select value={runB} onValueChange={setRunB}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a run..." />
                </SelectTrigger>
                <SelectContent>
                  {runsLoading && (
                    <SelectItem value="__loading" disabled>Loading...</SelectItem>
                  )}
                  {runs?.map((r) => (
                    <SelectItem key={r.run_id} value={r.run_id}>
                      {r.workflow_name} — {r.run_id.slice(0, 8)} ({r.status})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              onClick={handleCompare}
              disabled={!runA || !runB || diff.isPending}
              size="sm"
            >
              {diff.isPending ? 'Comparing...' : 'Compare'}
            </Button>
          </div>
        </div>

        {/* Error */}
        {diff.isError && (
          <div className={`${statusColors.failed.bg} border ${statusColors.failed.border} rounded-card p-4 flex items-center gap-2`}>
            <AlertCircle className={`w-5 h-5 ${statusColors.failed.text} flex-shrink-0`} />
            <p className={`${statusColors.failed.text} text-sm`}>{diff.error.message}</p>
          </div>
        )}

        {/* Results */}
        {diff.data && (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                { label: 'Run A', data: diff.data.run_a },
                { label: 'Run B', data: diff.data.run_b },
              ].map(({ label, data }) => (
                <div key={label} className="bg-[#1a1a1d] border border-[#252528] rounded-card p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-[#80808a]">{label}</h3>
                    <StatusBadge status={data.status} />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-[#4a4a52]">Run ID</span>
                      <p className="font-mono text-xs text-[#80808a] mt-0.5 break-all">{data.run_id}</p>
                    </div>
                    <div>
                      <span className="text-[#4a4a52]">Nodes</span>
                      <p className="text-[#80808a] mt-0.5">{data.node_count}</p>
                    </div>
                    <div>
                      <span className="text-[#4a4a52]">Total Cost</span>
                      <p className="font-mono text-[#80808a] mt-0.5">${(data.total_cost ?? 0).toFixed(4)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Node-by-Node Table */}
            <div className="bg-[#1a1a1d] border border-[#252528] rounded-card overflow-hidden">
              <div className="px-4 py-3 border-b border-[#252528]">
                <h3 className="text-sm font-bold text-[#80808a] mb-3">
                  Node-by-Node Comparison ({diff.data.node_diffs.length} nodes)
                </h3>
                <div className="flex rounded-lg overflow-hidden border border-[#333338]/50 bg-[#1a1a1d]/50 w-fit">
                  {([
                    { key: 'all' as DiffFilter, label: 'All' },
                    { key: 'changed' as DiffFilter, label: 'Changed' },
                    { key: 'failed' as DiffFilter, label: 'Failed' },
                    { key: 'cost_delta' as DiffFilter, label: 'Cost \u0394' },
                  ]).map(({ key, label }) => (
                    <button
                      key={key}
                      onClick={() => setFilter(key)}
                      className={cn(
                        'px-3.5 py-1.5 text-xs font-medium transition-colors',
                        filter === key
                          ? 'bg-amber-500 text-black'
                          : 'text-[#80808a] hover:text-[#f0f0f0]',
                      )}
                    >
                      {label} ({filterCounts[key]})
                    </button>
                  ))}
                </div>
              </div>

              {filteredNodeDiffs.length === 0 ? (
                <div className="p-4 text-sm text-[#4a4a52]">
                  {filter === 'all' ? 'No node differences found.' : 'No nodes match this filter.'}
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="text-left text-[#4a4a52] border-b border-[#252528]">
                        <th className="px-4 py-2 font-medium">Node</th>
                        <th className="px-4 py-2 font-medium">Status A</th>
                        <th className="px-4 py-2 font-medium">Status B</th>
                        <th className="px-4 py-2 font-medium text-right">Duration A</th>
                        <th className="px-4 py-2 font-medium text-right">Duration B</th>
                        <th className="px-4 py-2 font-medium text-right">Cost A</th>
                        <th className="px-4 py-2 font-medium text-right">Cost B</th>
                        <th className="px-4 py-2 font-medium">Diff</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#252528]/50">
                      {filteredNodeDiffs.map((nd: NodeDiff) => {
                        const statusDiffers = nd.status_a !== nd.status_b;
                        const durationDelta = formatDelta(nd.duration_a, nd.duration_b, false);
                        const costDelta = formatDelta(nd.cost_a, nd.cost_b, true);
                        const hasDiff = nd.artifact_diff !== null;

                        return (
                          <React.Fragment key={nd.node_id}>
                          <tr
                            className={`${statusDiffers ? 'bg-red-900/20' : ''} hover:bg-[#1a1a1d]/30`}
                          >
                            <td className="px-4 py-2 font-mono text-xs text-[#f0f0f0]">{nd.node_id}</td>
                            <td className="px-4 py-2">
                              <StatusBadge status={nd.status_a} />
                            </td>
                            <td className="px-4 py-2">
                              <StatusBadge status={nd.status_b} />
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-xs text-[#80808a]">
                              {nd.duration_a !== null ? `${nd.duration_a}ms` : '-'}
                              {durationDelta && (
                                <span className={`ml-1 text-xs ${durationDelta.startsWith('+') ? statusColors.failed.text : statusColors.completed.text}`}>
                                  ({durationDelta})
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-xs text-[#80808a]">
                              {nd.duration_b !== null ? `${nd.duration_b}ms` : '-'}
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-xs text-[#80808a]">
                              {nd.cost_a !== null ? `$${nd.cost_a.toFixed(6)}` : '-'}
                              {costDelta && (
                                <span className={`ml-1 text-xs ${costDelta.startsWith('+') ? statusColors.failed.text : statusColors.completed.text}`}>
                                  ({costDelta})
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-xs text-[#80808a]">
                              {nd.cost_b !== null ? `$${nd.cost_b.toFixed(6)}` : '-'}
                            </td>
                            <td className="px-4 py-2">
                              {hasDiff && (
                                <Button
                                  onClick={() => toggleDiff(nd.node_id)}
                                  variant="link"
                                  size="sm"
                                  className="text-amber-400 hover:text-amber-300 text-xs p-0 h-auto"
                                >
                                  {expandedDiffs.has(nd.node_id) ? 'hide' : 'show'}
                                </Button>
                              )}
                            </td>
                          </tr>
                          {hasDiff && expandedDiffs.has(nd.node_id) && (
                            <tr>
                              <td colSpan={8} className="px-4 py-3 bg-[#1a1a1d]/50">
                                <ArtifactDiff diff={nd.artifact_diff!} />
                              </td>
                            </tr>
                          )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </PageShell>
  );
}
