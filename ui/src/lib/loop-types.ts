export interface ExitCondition {
  field: string;  // JSONPath field, e.g. "$.score"
  operator: '>=' | '<=' | '>' | '<' | '==' | '!=' | 'contains';
  value: string | number;
}

export interface LoopContainerData {
  label: string;
  exitCondition: ExitCondition | null;
  maxIterations: number;
  entryNode?: string;   // explicit entry node override (node label from contains)
  outputNode?: string;  // explicit output node override (node label from contains)
  isDragOver?: boolean;
  runtime?: {
    currentIteration: number;
    currentValue?: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    totalCost?: number;
  };
}
