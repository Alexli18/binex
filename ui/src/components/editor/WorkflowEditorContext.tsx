import { createContext, useContext } from 'react';

interface WorkflowEditorContextValue {
  mcpServerNames: string[];
}

const Ctx = createContext<WorkflowEditorContextValue>({ mcpServerNames: [] });

export const WorkflowEditorProvider = Ctx.Provider;

export function useWorkflowEditorContext() {
  return useContext(Ctx);
}
