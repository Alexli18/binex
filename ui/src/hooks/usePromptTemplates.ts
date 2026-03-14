import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

export interface PromptTemplate {
  name: string;
  category: string;
  description: string;
}

export function usePromptTemplates() {
  return useQuery<{ templates: PromptTemplate[] }>({
    queryKey: ['promptTemplates'],
    queryFn: () => api.get('/prompts/templates'),
  });
}

export function usePromptTemplateContent(name: string | null) {
  return useQuery<{ name: string; content: string }>({
    queryKey: ['promptTemplate', name],
    queryFn: () => api.get(`/prompts/templates/${name}`),
    enabled: !!name,
  });
}
