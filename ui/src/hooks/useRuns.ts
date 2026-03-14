import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { ExecutionRecord, RunSummary } from '../lib/types';

export function useRuns() {
  return useQuery({
    queryKey: ['runs'],
    queryFn: () => api.get<{ runs: RunSummary[] }>('/runs').then((r) => r.runs),
    refetchInterval: 5000,
  });
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.get<RunSummary>(`/runs/${runId}`),
    enabled: !!runId,
    retry: 5,
    retryDelay: 1000,
    refetchInterval: 3000,
  });
}

export function useRecords(runId: string | undefined) {
  return useQuery({
    queryKey: ['records', runId],
    queryFn: () =>
      api
        .get<{ records: ExecutionRecord[] }>(`/runs/${runId}/records`)
        .then((r) => r.records),
    enabled: !!runId,
  });
}

export function useCancelRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => api.post(`/runs/${runId}/cancel`),
    onSuccess: (_, runId) => {
      qc.invalidateQueries({ queryKey: ['run', runId] });
    },
  });
}

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { workflow_path: string; variables?: Record<string, string> }) =>
      api.post<{ run_id: string; status: string }>('/runs', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['runs'] });
    },
  });
}
