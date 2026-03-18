export interface ExitCondition {
  field: string;  // JSONPath field, e.g. "$.score"
  operator: '>=' | '<=' | '>' | '<' | '==' | '!=' | 'contains';
  value: string | number;
}

export interface LoopContainerData {
  label: string;
  exitCondition: ExitCondition | null;
  maxIterations: number;
  isDragOver?: boolean;
  runtime?: {
    currentIteration: number;
    currentValue?: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    totalCost?: number;
  };
}
