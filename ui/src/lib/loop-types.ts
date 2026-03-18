export interface ExitCondition {
  jsonpath: string;
  operator: '>=' | '<=' | '>' | '<' | '==' | '!=' | 'contains';
  value: string;
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
