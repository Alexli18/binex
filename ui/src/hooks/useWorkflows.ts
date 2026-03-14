import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';

export function useWorkflows() {
  return useQuery({
    queryKey: ['workflows'],
    queryFn: () => api.get<{ workflows: string[] }>('/workflows').then((r) => r.workflows),
  });
}

export function useWorkflow(path: string | null) {
  return useQuery({
    queryKey: ['workflow', path],
    queryFn: () => api.get<{ path: string; content: string }>(`/workflows/${path}`),
    enabled: !!path,
  });
}

export function useSaveWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ path, content }: { path: string; content: string }) =>
      api.put<{ path: string; saved: boolean }>(`/workflows/${path}`, { content }),
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: ['workflow', variables.path] });
      qc.invalidateQueries({ queryKey: ['workflows'] });
    },
  });
}
