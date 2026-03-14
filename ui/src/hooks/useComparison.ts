import { useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';

export interface NodeDiff {
  node_id: string;
  status_a: string;
  status_b: string;
  duration_a: number | null;
  duration_b: number | null;
  cost_a: number | null;
  cost_b: number | null;
  artifact_diff: string | null;
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
}

export interface BisectDetails {
  node_id: string;
  good_status: string;
  bad_status: string;
  good_output: string | null;
  bad_output: string | null;
  diff: string | null;
}

export interface BisectResult {
  good_run: string;
  bad_run: string;
  divergence_node: string | null;
  divergence_index: number | null;
  similarity: number | null;
  details: BisectDetails | null;
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
