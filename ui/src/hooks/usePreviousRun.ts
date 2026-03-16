import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

interface PreviousRunResponse {
  run_id: string;
}

export function usePreviousRun(runId: string | undefined) {
  return useQuery<PreviousRunResponse | null>({
    queryKey: ['previousRun', runId],
    queryFn: async () => {
      if (!runId) return null;
      try {
        return await api.get<PreviousRunResponse>(`/runs/${runId}/previous`);
      } catch {
        return null;
      }
    },
    enabled: !!runId,
    staleTime: 60_000,
  });
}
