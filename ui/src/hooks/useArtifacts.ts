import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { Artifact, CostSummary } from '../lib/types';

export function useArtifacts(runId: string | undefined) {
  return useQuery({
    queryKey: ['artifacts', runId],
    queryFn: () => api.get<{ artifacts: Artifact[] }>(`/runs/${runId}/artifacts`).then((r) => r.artifacts),
    enabled: !!runId,
  });
}

export function useCosts(runId: string | undefined) {
  return useQuery({
    queryKey: ['costs', runId],
    queryFn: () => api.get<CostSummary>(`/runs/${runId}/costs`),
    enabled: !!runId,
  });
}
