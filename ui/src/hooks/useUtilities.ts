import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../lib/api';

export interface Pattern {
  name: string;
  description: string;
  example: string;
}

export interface ScaffoldResult {
  yaml: string;
  nodes: string[];
  edges: string[][];
}

export interface HealthCheck {
  name: string;
  status: string;
  message: string;
}

export interface Plugin {
  name: string;
  type: string;
  builtin: boolean;
  description: string;
}

export interface GatewayAgent {
  name: string;
  url: string;
  status: string;
  skills: string[];
}

export interface GatewayData {
  status: string;
  agents: GatewayAgent[];
  message: string;
}

export function usePatterns() {
  return useQuery<{ patterns: Pattern[] }>({
    queryKey: ['patterns'],
    queryFn: () => api.get('/scaffold/patterns'),
  });
}

export function useScaffold() {
  return useMutation<
    ScaffoldResult,
    Error,
    { mode: string; expression?: string; template_name?: string }
  >({
    mutationFn: (body) => api.post('/scaffold', body),
  });
}

export function useExport() {
  return useMutation<
    Blob,
    Error,
    { run_ids?: string[]; last_n?: number; format: string; include_artifacts: boolean }
  >({
    mutationFn: async (body) => {
      const resp = await fetch('/api/v1/export', {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: resp.statusText }));
        throw new Error(err.error || resp.statusText);
      }
      return resp.blob();
    },
  });
}

export function useDoctor() {
  return useQuery<{ checks: HealthCheck[] }>({
    queryKey: ['doctor'],
    queryFn: () => api.get('/system/doctor'),
  });
}

export function usePlugins() {
  return useQuery<{ plugins: Plugin[] }>({
    queryKey: ['plugins'],
    queryFn: () => api.get('/system/plugins'),
  });
}

export function useGateway() {
  return useQuery<GatewayData>({
    queryKey: ['gateway'],
    queryFn: () => api.get('/system/gateway'),
    refetchInterval: 10000,
  });
}
