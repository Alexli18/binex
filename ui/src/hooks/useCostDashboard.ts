import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';

interface CostByModel {
  model: string;
  cost: number;
  count: number;
}

interface CostByNode {
  node_id: string;
  cost: number;
  count: number;
}

interface CostTrend {
  date: string;
  cost: number;
  runs: number;
}

export interface DashboardData {
  period: string;
  total_cost: number;
  avg_per_run: number;
  run_count: number;
  cost_by_model: CostByModel[];
  cost_by_node: CostByNode[];
  cost_trend: CostTrend[];
}

export interface NodeEstimate {
  node_id: string;
  agent: string;
  model: string | null;
  max_tokens: number;
  estimated_cost: number | null;
  type: string;
}

export interface EstimateData {
  total_estimate: number;
  nodes: NodeEstimate[];
  warnings: string[];
}

export function useCostDashboard(period: string) {
  return useQuery<DashboardData>({
    queryKey: ['costDashboard', period],
    queryFn: () => api.get<DashboardData>(`/costs/dashboard?period=${period}`),
  });
}

export function useCostEstimate() {
  return useMutation<EstimateData, Error, string>({
    mutationFn: (yamlContent) =>
      api.post<EstimateData>('/costs/estimate', { yaml_content: yamlContent }),
  });
}
