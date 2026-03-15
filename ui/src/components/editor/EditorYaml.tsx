import Editor from '@monaco-editor/react';
import { WorkflowGraph } from '@/components/dag/WorkflowGraph';
import type { WorkflowNode, WorkflowEdge } from '@/lib/yaml-to-graph';

export interface EditorYamlProps {
  content: string;
  selectedPath: string | null;
  graphNodes: WorkflowNode[];
  graphEdges: WorkflowEdge[];
  onContentChange: (value: string | undefined) => void;
}

export function EditorYaml({
  content,
  selectedPath,
  graphNodes,
  graphEdges,
  onContentChange,
}: EditorYamlProps) {
  return (
    <div className="flex flex-1 min-w-0">
      {/* Monaco Editor */}
      <div className="flex-1 min-w-0">
        {selectedPath || content.trim() ? (
          <Editor
            height="100%"
            language="yaml"
            theme="vs-dark"
            value={content}
            onChange={onContentChange}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              tabSize: 2,
            }}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-slate-500">
            Select a workflow file to edit
          </div>
        )}
      </div>

      {/* DAG preview */}
      <div className="w-1/2 border-l border-slate-700 bg-slate-900 flex-shrink-0 flex flex-col">
        <div className="flex-1 min-h-0">
          {graphNodes.length > 0 ? (
            <WorkflowGraph nodes={graphNodes} edges={graphEdges} />
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">
              {content.trim() ? 'No nodes found in workflow' : 'DAG preview will appear here'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
