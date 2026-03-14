import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

// Debug types
export interface DebugArtifact {
  id: string;
  type: string;
  content: string;
}

export interface DebugNode {
  node_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_s: number | null;
  error: string | null;
  agent?: string;
  system_prompt?: string;
  model?: string;
  artifacts: DebugArtifact[];
}

export interface DebugData {
  run_id: string;
  status: string;
  workflow_name: string | null;
  workflow_path: string | null;
  nodes: DebugNode[];
}

// Trace types
export interface TraceEntry {
  node_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_s: number | null;
  offset_s: number | null;
  error: string | null;
}

export interface Anomaly {
  node_id: string;
  duration_s: number;
  ratio: number;
}

export interface TraceData {
  run_id: string;
  status: string;
  total_duration_s: number;
  timeline: TraceEntry[];
  anomalies: Anomaly[];
}

// Diagnose types
export interface RootCause {
  node_id: string;
  error: string;
  status: string;
}

export interface LatencyAnomaly {
  node_id: string;
  duration_s: number;
  expected_s: number;
  ratio: number;
}

export interface DiagnoseData {
  run_id: string;
  status: string;
  severity: string;
  root_causes: RootCause[];
  latency_anomalies: LatencyAnomaly[];
  recommendations: string[];
  total_cost: number;
}

// Lineage types
export interface LineageNode {
  id: string;
  type: string;
  content: string;
  produced_by: string;
}

export interface LineageEdge {
  source: string;
  target: string;
}

export interface LineageData {
  run_id: string;
  nodes: LineageNode[];
  edges: LineageEdge[];
}

// Hooks
export function useDebug(runId: string | undefined, errorsOnly = false) {
  return useQuery<DebugData>({
    queryKey: ['debug', runId, errorsOnly],
    queryFn: () => api.get<DebugData>(`/runs/${runId}/debug?errors_only=${errorsOnly}`),
    enabled: !!runId,
  });
}

export function useTrace(runId: string | undefined) {
  return useQuery<TraceData>({
    queryKey: ['trace', runId],
    queryFn: () => api.get<TraceData>(`/runs/${runId}/trace`),
    enabled: !!runId,
  });
}

export function useDiagnose(runId: string | undefined) {
  return useQuery<DiagnoseData>({
    queryKey: ['diagnose', runId],
    queryFn: () => api.get<DiagnoseData>(`/runs/${runId}/diagnose`),
    enabled: !!runId,
  });
}

export function useLineage(runId: string | undefined) {
  return useQuery<LineageData>({
    queryKey: ['lineage', runId],
    queryFn: () => api.get<LineageData>(`/runs/${runId}/lineage`),
    enabled: !!runId,
  });
}
