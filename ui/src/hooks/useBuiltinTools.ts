import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

export interface BuiltinTool {
  name: string;
  description: string;
  category: 'data' | 'web' | 'files' | 'system';
  parameters: Record<string, unknown>;
}

export function useBuiltinTools() {
  return useQuery({
    queryKey: ['builtin-tools'],
    queryFn: () =>
      api.get<{ tools: BuiltinTool[] }>('/tools/builtins').then((r) => r.tools),
    staleTime: 5 * 60 * 1000,
  });
}
