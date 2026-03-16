import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

export interface ApiModel {
  id: string;
  tier: 'flagship' | 'balanced' | 'fast' | 'reasoning' | 'free' | 'local';
  context_k: number | null;
}

export interface ApiProvider {
  name: string;
  default_model: string;
  env_var: string;
  agent_prefix: string;
  configured: boolean;
  models: ApiModel[];
}

interface ProvidersResponse {
  providers: ApiProvider[];
}

export function useProviders() {
  return useQuery<ProvidersResponse>({
    queryKey: ['providers'],
    queryFn: () => api.get('/providers'),
    staleTime: 60_000,
  });
}
