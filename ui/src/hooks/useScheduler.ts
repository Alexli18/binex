import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';

export interface ScheduledWorkflow {
  name: string;
  file_path: string;
  schedule: string;
  next_run: string | null;
  last_run: string | null;
  last_status: string | null;
}

export interface HistoryEntry {
  timestamp: string;
  workflow_name: string;
  run_id: string | null;
  status: 'completed' | 'failed' | 'skipped';
  skip_reason: string | null;
  duration: number | null;
  cost: number | null;
}

export interface SchedulerStatus {
  running: boolean;
  workflows: ScheduledWorkflow[];
  history: HistoryEntry[];
  stats: {
    active_workflows: number;
    runs_today: number;
    skipped_today: number;
    cost_today: number;
  };
}

export function useScheduler() {
  return useQuery<SchedulerStatus>({
    queryKey: ['scheduler'],
    queryFn: () => api.get('/scheduler/status'),
    refetchInterval: 10_000,
  });
}

export function useSchedulerStart() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('/scheduler/start', { directory: '.' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
  });
}

export function useSchedulerStop() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('/scheduler/stop'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
  });
}
