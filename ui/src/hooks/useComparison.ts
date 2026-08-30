import { useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';

/** One differing leaf between two structured artifact contents. */
export interface FieldChange {
  path: string;
  before: unknown;
  after: unknown;
  kind: 'changed' | 'added' | 'removed';
}

export interface NodeDiff {
  node_id: string;
  status_a: string;
  status_b: string;
  duration_a: number | null;
  duration_b: number | null;
  cost_a: number | null;
  cost_b: number | null;
  artifact_diff: string | null;
  content_similarity?: number | null;
  /**
   * null when the artifacts were compared as text (no per-field detail),
   * [] when structured content is identical, one entry per changed field
   * otherwise.
   */
  field_changes?: FieldChange[] | null;
  agent_changed?: boolean;
  error_a?: string | null;
  error_b?: string | null;
}

export interface DiffRunSummary {
  run_id: string;
  status: string;
  node_count: number;
  total_cost: number;
}

export interface DiffResult {
  run_a: DiffRunSummary;
  run_b: DiffRunSummary;
  node_diffs: NodeDiff[];
  summary?: {
    total_changed: number;
    total_failed: number;
    total_cost_delta: number;
  };
}

export interface BisectDetails {
  node_id: string;
  good_status: string;
  bad_status: string;
  good_output: string | null;
  bad_output: string | null;
  diff: string | null;
  latency_good_ms?: number | null;
  latency_bad_ms?: number | null;
  cost_good?: number | null;
  cost_bad?: number | null;
}

export interface BisectNodeStatus {
  node_id: string;
  status: 'match' | 'status_diff' | 'content_diff' | 'missing_in_good' | 'missing_in_bad';
  similarity: number | null;
  good_status: string | null;
  bad_status: string | null;
  latency_good_ms: number | null;
  latency_bad_ms: number | null;
  content_diff: string | null;
}

export interface BisectResult {
  good_run: string;
  bad_run: string;
  divergence_node: string | null;
  divergence_index: number | null;
  similarity: number | null;
  details: BisectDetails | null;
  node_map?: BisectNodeStatus[];
  downstream_impact?: string[];
}

export function useDiff() {
  return useMutation<DiffResult, Error, { run_a: string; run_b: string }>({
    mutationFn: (body) => api.post<DiffResult>('/diff', body),
  });
}

export function useBisect() {
  return useMutation<BisectResult, Error, { good_run: string; bad_run: string; threshold?: number }>({
    mutationFn: (body) => api.post<BisectResult>('/bisect', body),
  });
}
