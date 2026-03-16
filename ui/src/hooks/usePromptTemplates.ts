import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';

export interface PromptTemplate {
  name: string;
  category: string;
  description: string;
  is_custom?: boolean;
}

export function usePromptTemplates() {
  return useQuery<{ templates: PromptTemplate[] }>({
    queryKey: ['promptTemplates'],
    queryFn: () => api.get('/prompts/templates'),
  });
}

export function useCreatePromptTemplate() {
  const queryClient = useQueryClient();
  return useMutation<
    { name: string; category: string; filename: string },
    Error,
    { name: string; category: string; content: string }
  >({
    mutationFn: (body) => api.post('/prompts/templates', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promptTemplates'] });
    },
  });
}

export function useUpdatePromptTemplate() {
  const queryClient = useQueryClient();
  return useMutation<
    { name: string; status: string },
    Error,
    { name: string; content: string }
  >({
    mutationFn: ({ name, content }) => api.put(`/prompts/templates/${name}`, { content }),
    onSuccess: (_, { name }) => {
      queryClient.invalidateQueries({ queryKey: ['promptTemplates'] });
      queryClient.invalidateQueries({ queryKey: ['promptTemplate', name] });
    },
  });
}

export function useDeletePromptTemplate() {
  const queryClient = useQueryClient();
  return useMutation<
    { name: string; status: string },
    Error,
    string
  >({
    mutationFn: (name) => api.delete(`/prompts/templates/${name}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['promptTemplates'] });
    },
  });
}

export function usePromptTemplateContent(name: string | null) {
  return useQuery<{ name: string; category: string; content: string; is_custom?: boolean }>({
    queryKey: ['promptTemplate', name],
    queryFn: () => api.get(`/prompts/templates/${name}`),
    enabled: !!name,
  });
}
