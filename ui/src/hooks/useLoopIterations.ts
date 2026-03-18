import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

export interface LoopIterationNode {
  node_id: string;
  status: string;
  latency_ms: number | null;
  cost: number;
  error: string | null;
}

export interface LoopIteration {
  iteration: number;
  status: string;
  nodes: LoopIterationNode[];
}

export interface LoopData {
  loop_node_id: string;
  iterations: LoopIteration[];
  total_iterations: number;
}

export interface LoopsResponse {
  run_id: string;
  loops: LoopData[];
}

export function useLoopIterations(runId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ['loops', runId],
    queryFn: () => api.get<LoopsResponse>(`/loops/${runId}`),
    enabled: !!runId && enabled,
    refetchInterval: 2000,
  });
}
