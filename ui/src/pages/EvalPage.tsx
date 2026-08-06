import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { FlaskConical, CheckCircle2, XCircle, AlertTriangle, Loader2 } from 'lucide-react';

interface CaseResult {
  case_id: string;
  verdict: 'pass' | 'fail' | 'no_baseline';
  run_id: string | null;
  baseline_run_id: string | null;
  similarity: number | null;
  cost_delta: number | null;
  latency_delta_ms: number | null;
  violated_thresholds: string[];
  error: string | null;
}

interface EvalExecution {
  id: string;
  suite_name: string;
  executed_at: string;
  total: number;
  passed: number;
  failed: number;
  no_baseline: number;
  total_cost: number;
  cases?: CaseResult[];
}

function useEvalExecutions() {
  return useQuery({
    queryKey: ['eval-executions'],
    queryFn: () => api.get<{ executions: EvalExecution[] }>('/eval/executions'),
    select: (d) => d.executions,
    refetchInterval: 10000,
  });
}

function useEvalDetail(id: string | null) {
  return useQuery({
    queryKey: ['eval-execution', id],
    queryFn: () => api.get<EvalExecution>(`/eval/executions/${id}`),
    enabled: !!id,
  });
}

const AMBER = '#e8a020';
const CARD = '#1a1a1d';
const BORDER = '#252528';
const MUTED = '#80808a';
const TEXT = '#f0f0f0';

function VerdictBadge({ verdict }: { verdict: string }) {
  if (verdict === 'pass') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#4ade80', fontSize: 12, fontWeight: 600 }}>
        <CheckCircle2 size={12} /> PASS
      </span>
    );
  }
  if (verdict === 'fail') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#f87171', fontSize: 12, fontWeight: 600 }}>
        <XCircle size={12} /> FAIL
      </span>
    );
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: AMBER, fontSize: 12, fontWeight: 600 }}>
      <AlertTriangle size={12} /> NO BASELINE
    </span>
  );
}

function CaseRow({ c }: { c: CaseResult }) {
  const navigate = useNavigate();

  const handleClick = () => {
    if (c.run_id && c.baseline_run_id) {
      navigate(`/diff?runA=${c.baseline_run_id}&runB=${c.run_id}`);
    } else if (c.run_id) {
      navigate(`/runs/${c.run_id}`);
    }
  };

  return (
    <tr
      onClick={handleClick}
      style={{ cursor: c.run_id ? 'pointer' : 'default', borderBottom: `1px solid ${BORDER}` }}
    >
      <td style={{ padding: '10px 16px', color: TEXT, fontSize: 13 }}>{c.case_id}</td>
      <td style={{ padding: '10px 16px' }}><VerdictBadge verdict={c.verdict} /></td>
      <td style={{ padding: '10px 16px', color: MUTED, fontSize: 12 }}>
        {c.similarity !== null ? (c.similarity ?? 0).toFixed(3) : '—'}
      </td>
      <td style={{ padding: '10px 16px', color: MUTED, fontSize: 12 }}>
        {c.cost_delta !== null ? `$${(c.cost_delta ?? 0).toFixed(4)}` : '—'}
      </td>
      <td style={{ padding: '10px 16px', color: MUTED, fontSize: 12 }}>
        {c.latency_delta_ms !== null ? `${c.latency_delta_ms}ms` : '—'}
      </td>
      <td style={{ padding: '10px 16px', color: '#f87171', fontSize: 11 }}>
        {c.violated_thresholds.join('; ')}
        {c.error && <span>{c.error}</span>}
      </td>
    </tr>
  );
}

function ExecutionDetail({ id }: { id: string }) {
  const { data, isLoading } = useEvalDetail(id);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}>
        <Loader2 size={20} style={{ color: AMBER }} />
      </div>
    );
  }
  if (!data || !data.cases) return null;

  return (
    <div style={{ background: CARD, border: `1px solid ${BORDER}`, borderRadius: 8, overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${BORDER}` }}>
            {['Case', 'Verdict', 'Similarity', 'Cost Δ', 'Latency Δ', 'Issues'].map(h => (
              <th key={h} style={{ padding: '8px 16px', textAlign: 'left', fontSize: 11, color: MUTED, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.cases.map((c: CaseResult) => <CaseRow key={c.case_id} c={c} />)}
        </tbody>
      </table>
    </div>
  );
}

function ExecutionRow({ exec, selected, onSelect }: { exec: EvalExecution; selected: boolean; onSelect: () => void }) {
  const passRate = exec.total > 0 ? Math.round((exec.passed / exec.total) * 100) : 0;
  return (
    <div
      onClick={onSelect}
      style={{
        background: selected ? '#1f1f23' : CARD,
        border: `1px solid ${selected ? AMBER : BORDER}`,
        borderRadius: 8,
        padding: '14px 16px',
        cursor: 'pointer',
        marginBottom: 8,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ color: TEXT, fontSize: 13, fontWeight: 600 }}>{exec.suite_name}</div>
          <div style={{ color: MUTED, fontSize: 11, marginTop: 2 }}>{new Date(exec.executed_at).toLocaleString()}</div>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ color: '#4ade80', fontSize: 12 }}>{exec.passed}✓</span>
          <span style={{ color: '#f87171', fontSize: 12 }}>{exec.failed}✗</span>
          {exec.no_baseline > 0 && <span style={{ color: AMBER, fontSize: 12 }}>{exec.no_baseline}?</span>}
          <span style={{ color: MUTED, fontSize: 11 }}>{passRate}%</span>
        </div>
      </div>
    </div>
  );
}

export function EvalPage() {
  const { data: executions = [], isLoading } = useEvalExecutions();
  const [activeId, setActiveId] = useState<string | null>(null);

  const displayId = activeId ?? executions[0]?.id ?? null;

  return (
    <PageShell>
      <div style={{ padding: '24px 32px', maxWidth: 1200, margin: '0 auto' }}>
        <PageHeader
          title="Eval"
          description="Regression test suite executions"
        />

        {isLoading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 64 }}>
            <Loader2 size={24} style={{ color: AMBER }} />
          </div>
        )}

        {!isLoading && executions.length === 0 && (
          <div style={{ textAlign: 'center', padding: 64, color: MUTED }}>
            <FlaskConical size={32} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
            <div style={{ fontSize: 14 }}>No eval executions yet.</div>
            <div style={{ fontSize: 12, marginTop: 6 }}>
              Run <code style={{ color: AMBER }}>binex eval run your-suite.yaml</code> to get started.
            </div>
          </div>
        )}

        {executions.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 24 }}>
            <div>
              {executions.map((exec) => (
                <ExecutionRow
                  key={exec.id}
                  exec={exec}
                  selected={displayId === exec.id}
                  onSelect={() => setActiveId(exec.id)}
                />
              ))}
            </div>
            <div>
              {displayId && <ExecutionDetail id={displayId} />}
            </div>
          </div>
        )}
      </div>
    </PageShell>
  );
}
