import { useState } from 'react';
import { useRuns } from '../hooks/useRuns';
import { useDiff } from '../hooks/useComparison';
import { StatusBadge } from '../components/common/StatusBadge';
import { GitCompare, ArrowRight, AlertCircle } from 'lucide-react';
import type { NodeDiff } from '../hooks/useComparison';

function DiffLine({ line }: { line: string }) {
  if (line.startsWith('+')) {
    return <div className="bg-green-900/40 text-green-300 px-2">{line}</div>;
  }
  if (line.startsWith('-')) {
    return <div className="bg-red-900/40 text-red-300 px-2">{line}</div>;
  }
  if (line.startsWith('@@')) {
    return <div className="text-blue-400 px-2">{line}</div>;
  }
  return <div className="px-2 text-slate-300">{line}</div>;
}

function ArtifactDiff({ diff }: { diff: string }) {
  const lines = diff.split('\n');
  return (
    <pre className="bg-slate-950 rounded-lg p-3 text-xs font-mono overflow-x-auto max-h-96 overflow-y-auto border border-slate-700">
      {lines.map((line, i) => (
        <DiffLine key={i} line={line} />
      ))}
    </pre>
  );
}

function formatDelta(a: number | null, b: number | null, isCost: boolean): string | null {
  if (a === null || b === null) return null;
  const delta = b - a;
  if (delta === 0) return '';
  const sign = delta > 0 ? '+' : '';
  if (isCost) return `${sign}$${delta.toFixed(6)}`;
  return `${sign}${delta.toFixed(0)}ms`;
}

export default function DiffPage() {
  const { data: runs, isLoading: runsLoading } = useRuns();
  const diff = useDiff();

  const [runA, setRunA] = useState('');
  const [runB, setRunB] = useState('');
  const [expandedDiffs, setExpandedDiffs] = useState<Set<string>>(new Set());

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
    <div className="p-6 flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <GitCompare className="w-6 h-6 text-blue-400" />
        <h1 className="text-2xl font-bold text-slate-100">Compare Runs</h1>
      </div>

      {/* Selectors */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
        <div className="flex flex-col md:flex-row items-end gap-4">
          <div className="flex-1 w-full">
            <label className="block text-sm font-medium text-slate-400 mb-1">Run A</label>
            <select
              value={runA}
              onChange={(e) => setRunA(e.target.value)}
              className="w-full bg-slate-900 border border-slate-600 rounded-md px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a run...</option>
              {runsLoading && <option disabled>Loading...</option>}
              {runs?.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.workflow_name} — {r.run_id.slice(0, 8)} ({r.status})
                </option>
              ))}
            </select>
          </div>

          <ArrowRight className="w-5 h-5 text-slate-500 hidden md:block mb-2" />

          <div className="flex-1 w-full">
            <label className="block text-sm font-medium text-slate-400 mb-1">Run B</label>
            <select
              value={runB}
              onChange={(e) => setRunB(e.target.value)}
              className="w-full bg-slate-900 border border-slate-600 rounded-md px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a run...</option>
              {runsLoading && <option disabled>Loading...</option>}
              {runs?.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.workflow_name} — {r.run_id.slice(0, 8)} ({r.status})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleCompare}
            disabled={!runA || !runB || diff.isPending}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium transition-colors whitespace-nowrap"
          >
            {diff.isPending ? 'Comparing...' : 'Compare'}
          </button>
        </div>
      </div>

      {/* Error */}
      {diff.isError && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <p className="text-red-300 text-sm">{diff.error.message}</p>
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
              <div key={label} className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-slate-300">{label}</h3>
                  <StatusBadge status={data.status} />
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-slate-500">Run ID</span>
                    <p className="font-mono text-xs text-slate-300 mt-0.5 break-all">{data.run_id}</p>
                  </div>
                  <div>
                    <span className="text-slate-500">Nodes</span>
                    <p className="text-slate-300 mt-0.5">{data.node_count}</p>
                  </div>
                  <div>
                    <span className="text-slate-500">Total Cost</span>
                    <p className="font-mono text-slate-300 mt-0.5">${data.total_cost.toFixed(4)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Node-by-Node Table */}
          <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-700">
              <h3 className="text-sm font-bold text-slate-300">
                Node-by-Node Comparison ({diff.data.node_diffs.length} nodes)
              </h3>
            </div>

            {diff.data.node_diffs.length === 0 ? (
              <div className="p-4 text-sm text-slate-500">No node differences found.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 border-b border-slate-700">
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
                  <tbody className="divide-y divide-slate-700/50">
                    {diff.data.node_diffs.map((nd: NodeDiff) => {
                      const statusDiffers = nd.status_a !== nd.status_b;
                      const durationDelta = formatDelta(nd.duration_a, nd.duration_b, false);
                      const costDelta = formatDelta(nd.cost_a, nd.cost_b, true);
                      const hasDiff = nd.artifact_diff !== null;

                      return (
                        <tr
                          key={nd.node_id}
                          className={`${statusDiffers ? 'bg-red-900/20' : ''} hover:bg-slate-700/30`}
                        >
                          <td className="px-4 py-2 font-mono text-xs text-slate-200">{nd.node_id}</td>
                          <td className="px-4 py-2">
                            <StatusBadge status={nd.status_a} />
                          </td>
                          <td className="px-4 py-2">
                            <StatusBadge status={nd.status_b} />
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-xs text-slate-300">
                            {nd.duration_a !== null ? `${nd.duration_a}ms` : '-'}
                            {durationDelta && (
                              <span className={`ml-1 text-xs ${durationDelta.startsWith('+') ? 'text-red-400' : 'text-green-400'}`}>
                                ({durationDelta})
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-xs text-slate-300">
                            {nd.duration_b !== null ? `${nd.duration_b}ms` : '-'}
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-xs text-slate-300">
                            {nd.cost_a !== null ? `$${nd.cost_a.toFixed(6)}` : '-'}
                            {costDelta && (
                              <span className={`ml-1 text-xs ${costDelta.startsWith('+') ? 'text-red-400' : 'text-green-400'}`}>
                                ({costDelta})
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-2 text-right font-mono text-xs text-slate-300">
                            {nd.cost_b !== null ? `$${nd.cost_b.toFixed(6)}` : '-'}
                          </td>
                          <td className="px-4 py-2">
                            {hasDiff && (
                              <button
                                onClick={() => toggleDiff(nd.node_id)}
                                className="text-blue-400 hover:text-blue-300 text-xs underline"
                              >
                                {expandedDiffs.has(nd.node_id) ? 'hide' : 'show'}
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Expanded artifact diffs */}
          {diff.data.node_diffs
            .filter((nd: NodeDiff) => nd.artifact_diff && expandedDiffs.has(nd.node_id))
            .map((nd: NodeDiff) => (
              <div key={nd.node_id} className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                <h4 className="text-sm font-bold text-slate-300 mb-2">
                  Artifact Diff: <span className="font-mono text-blue-400">{nd.node_id}</span>
                </h4>
                <ArtifactDiff diff={nd.artifact_diff!} />
              </div>
            ))}
        </>
      )}
    </div>
  );
}
