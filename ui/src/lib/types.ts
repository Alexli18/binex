export interface RunSummary {
  run_id: string;
  workflow_name: string;
  workflow_path: string | null;
  status: string;
  total_nodes: number;
  completed_nodes: number;
  failed_nodes: number;
  skipped_nodes: number;
  total_cost: number;
  started_at: string;
  completed_at: string | null;
}

export interface ExecutionRecord {
  run_id: string;
  task_id: string;
  status: string;
  latency_ms: number;
  error: string | null;
}

export interface Lineage {
  produced_by: string;
  step: number;
  derived_from: string | null;
}

export interface Artifact {
  type: string;
  content: string;
  lineage: Lineage;
}

export interface CostRecord {
  run_id: string;
  node_id: string;
  cost: number;
  model: string | null;
  source: string;
}

export interface CostSummary {
  run_id: string;
  total_cost: number;
  records: CostRecord[];
}

export interface RunEvent {
  type: 'node:started' | 'node:completed' | 'node:failed' | 'run:completed' | 'run:cancelled' | 'human:prompt_needed';
  node_id?: string;
  timestamp: string;
  cost?: number;
  error?: string;
  status?: string;
}

export interface HumanPromptEvent {
  type: 'human:prompt_needed';
  prompt_id: string;
  prompt_type: 'approval' | 'input';
  node_id: string;
  message: string;
  artifacts: {
    id: string;
    type: string;
    content: string;
    produced_by: string | null;
  }[];
}
