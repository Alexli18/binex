import { useState } from 'react';
import { useRuns } from '../hooks/useRuns';
import { useBisect } from '../hooks/useComparison';
import { StatusBadge } from '../components/common/StatusBadge';
import { GitBranch, AlertCircle, CheckCircle2 } from 'lucide-react';

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

export default function BisectPage() {
  const { data: runs, isLoading: runsLoading } = useRuns();
  const bisect = useBisect();

  const [goodRun, setGoodRun] = useState('');
  const [badRun, setBadRun] = useState('');
  const [threshold, setThreshold] = useState(0.9);

  const handleBisect = () => {
    if (goodRun && badRun) {
      bisect.mutate({ good_run: goodRun, bad_run: badRun, threshold });
    }
  };

  const similarityPercent = bisect.data?.similarity !== null && bisect.data?.similarity !== undefined
    ? Math.round(bisect.data.similarity * 100)
    : null;

  return (
    <div className="p-6 flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <GitBranch className="w-6 h-6 text-purple-400" />
        <h1 className="text-2xl font-bold text-slate-100">Bisect &mdash; Find Divergence</h1>
      </div>

      {/* Selectors */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-400 mb-1">Good Run</label>
              <select
                value={goodRun}
                onChange={(e) => setGoodRun(e.target.value)}
                className="w-full bg-slate-900 border border-slate-600 rounded-md px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
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

            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-400 mb-1">Bad Run</label>
              <select
                value={badRun}
                onChange={(e) => setBadRun(e.target.value)}
                className="w-full bg-slate-900 border border-slate-600 rounded-md px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
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
          </div>

          {/* Threshold slider */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">
              Similarity Threshold: <span className="text-slate-200 font-mono">{threshold.toFixed(2)}</span>
            </label>
            <input
              type="range"
              min="0.1"
              max="1.0"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-full accent-purple-500"
            />
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>0.10</span>
              <span>1.00</span>
            </div>
          </div>

          <button
            onClick={handleBisect}
            disabled={!goodRun || !badRun || bisect.isPending}
            className="self-start px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-md text-sm font-medium transition-colors flex items-center gap-2"
          >
            {bisect.isPending && (
              <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {bisect.isPending ? 'Finding Divergence...' : 'Find Divergence'}
          </button>
        </div>
      </div>

      {/* Error */}
      {bisect.isError && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <p className="text-red-300 text-sm">{bisect.error.message}</p>
        </div>
      )}

      {/* Results */}
      {bisect.data && (
        <div className="flex flex-col gap-4">
          {/* Divergence status */}
          {bisect.data.divergence_node ? (
            <>
              {/* Divergence found */}
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-4">
                  <AlertCircle className="w-5 h-5 text-red-400" />
                  <span className="text-sm font-bold text-slate-200">
                    Divergence at node:{' '}
                    <span className="font-mono text-red-400">{bisect.data.divergence_node}</span>
                  </span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-900/50 text-red-300 border border-red-700">
                    index #{bisect.data.divergence_index}
                  </span>
                </div>

                {/* Similarity bar */}
                {similarityPercent !== null && (
                  <div className="mb-4">
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-slate-400">Similarity</span>
                      <span className="font-mono text-slate-200">{similarityPercent}%</span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full transition-all ${
                          similarityPercent >= 80
                            ? 'bg-green-500'
                            : similarityPercent >= 50
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                        }`}
                        style={{ width: `${similarityPercent}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Details card */}
                {bisect.data.details && (
                  <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
                    <h4 className="text-sm font-bold text-slate-300 mb-3">Divergence Details</h4>
                    <div className="grid grid-cols-2 gap-4 text-sm mb-4">
                      <div>
                        <span className="text-slate-500 block mb-1">Good Run Status</span>
                        <StatusBadge status={bisect.data.details.good_status} />
                      </div>
                      <div>
                        <span className="text-slate-500 block mb-1">Bad Run Status</span>
                        <StatusBadge status={bisect.data.details.bad_status} />
                      </div>
                      {bisect.data.details.good_output !== null && (
                        <div>
                          <span className="text-slate-500 block mb-1">Good Output</span>
                          <pre className="text-xs font-mono text-slate-300 bg-slate-950 p-2 rounded max-h-40 overflow-y-auto whitespace-pre-wrap break-all">
                            {bisect.data.details.good_output}
                          </pre>
                        </div>
                      )}
                      {bisect.data.details.bad_output !== null && (
                        <div>
                          <span className="text-slate-500 block mb-1">Bad Output</span>
                          <pre className="text-xs font-mono text-slate-300 bg-slate-950 p-2 rounded max-h-40 overflow-y-auto whitespace-pre-wrap break-all">
                            {bisect.data.details.bad_output}
                          </pre>
                        </div>
                      )}
                    </div>

                    {bisect.data.details.diff && (
                      <div>
                        <span className="text-slate-500 text-sm block mb-2">Output Diff</span>
                        <ArtifactDiff diff={bisect.data.details.diff} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            /* No divergence found */
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-green-400" />
              <span className="inline-flex items-center px-2.5 py-1 rounded text-sm font-medium bg-green-900/50 text-green-300 border border-green-700">
                No divergence found
              </span>
              <span className="text-slate-400 text-sm">
                The runs are similar above the threshold.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
