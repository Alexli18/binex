import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import { WorkflowGraph } from '../components/dag/WorkflowGraph';
import { CostEstimatePanel } from '../components/CostEstimatePanel';
import { useWorkflows, useWorkflow, useSaveWorkflow } from '../hooks/useWorkflows';
import { useCreateRun } from '../hooks/useRuns';
import { parseWorkflowYaml, type WorkflowNode, type WorkflowEdge } from '../lib/yaml-to-graph';

export default function WorkflowEditor() {
  const navigate = useNavigate();
  const { data: workflows, isLoading: loadingList } = useWorkflows();
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const { data: workflowData } = useWorkflow(selectedPath);
  const saveMutation = useSaveWorkflow();
  const createRun = useCreateRun();

  const [content, setContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [graphNodes, setGraphNodes] = useState<WorkflowNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<WorkflowEdge[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track dirty state
  const isDirty = content !== originalContent;

  // Load file content when workflow data arrives
  useEffect(() => {
    if (workflowData?.content != null) {
      setContent(workflowData.content);
      setOriginalContent(workflowData.content);
    }
  }, [workflowData]);

  // Auto-select first workflow
  useEffect(() => {
    if (workflows && workflows.length > 0 && !selectedPath) {
      setSelectedPath(workflows[0]);
    }
  }, [workflows, selectedPath]);

  // Debounced YAML -> graph conversion
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (!content.trim()) {
        setGraphNodes([]);
        setGraphEdges([]);
        setParseError(null);
        return;
      }
      try {
        const { nodes, edges } = parseWorkflowYaml(content);
        setGraphNodes(nodes);
        setGraphEdges(edges);
        setParseError(null);
      } catch (err) {
        // Keep last-valid graph on error, only show error banner
        setParseError(err instanceof Error ? err.message : String(err));
      }
    }, 500);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [content]);

  // beforeunload handler for unsaved changes
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const handleSave = useCallback(() => {
    if (!selectedPath) return;
    saveMutation.mutate(
      { path: selectedPath, content },
      { onSuccess: () => setOriginalContent(content) },
    );
  }, [selectedPath, content, saveMutation]);

  const handleRun = useCallback(() => {
    if (!selectedPath) return;
    createRun.mutate(
      { workflow_path: selectedPath },
      { onSuccess: (data) => navigate(`/runs/${data.run_id}/live`) },
    );
  }, [selectedPath, createRun, navigate]);

  const handleEditorChange = useCallback((value: string | undefined) => {
    setContent(value ?? '');
  }, []);

  const fileList = useMemo(() => {
    if (!workflows) return [];
    return workflows;
  }, [workflows]);

  return (
    <div className="flex flex-col h-[calc(100vh-52px)]">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-white border-b border-gray-200">
        <span className="text-sm font-medium text-gray-700">
          {selectedPath ?? 'No file selected'}
        </span>
        {isDirty && (
          <span className="text-xs text-amber-600 font-medium">(unsaved changes)</span>
        )}
        <div className="flex-1" />
        <button
          onClick={handleSave}
          disabled={!selectedPath || !isDirty || saveMutation.isPending}
          className="px-3 py-1.5 text-sm font-medium rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saveMutation.isPending ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={handleRun}
          disabled={!selectedPath || createRun.isPending}
          className="px-3 py-1.5 text-sm font-medium rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {createRun.isPending ? 'Starting...' : 'Run'}
        </button>
      </div>

      {/* Parse error banner */}
      {parseError && (
        <div className="px-4 py-2 bg-red-50 border-b border-red-200 text-red-700 text-sm">
          YAML parse error: {parseError}
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Left side: file sidebar + editor */}
        <div className="flex flex-1 min-w-0">
          {/* File sidebar */}
          <div className="w-48 border-r border-gray-200 bg-gray-50 overflow-y-auto flex-shrink-0">
            <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Workflows
            </div>
            {loadingList ? (
              <div className="px-3 py-2 text-sm text-gray-400">Loading...</div>
            ) : fileList.length === 0 ? (
              <div className="px-3 py-2 text-sm text-gray-400">No files found</div>
            ) : (
              fileList.map((f) => (
                <button
                  key={f}
                  onClick={() => setSelectedPath(f)}
                  className={`w-full text-left px-3 py-1.5 text-sm truncate ${
                    f === selectedPath
                      ? 'bg-blue-100 text-blue-800 font-medium'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                  title={f}
                >
                  {f}
                </button>
              ))
            )}
          </div>

          {/* Monaco Editor */}
          <div className="flex-1 min-w-0">
            {selectedPath ? (
              <Editor
                height="100%"
                language="yaml"
                value={content}
                onChange={handleEditorChange}
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
              <div className="flex items-center justify-center h-full text-gray-400">
                Select a workflow file to edit
              </div>
            )}
          </div>
        </div>

        {/* Right side: DAG preview + Cost Estimate */}
        <div className="w-1/2 border-l border-gray-200 bg-white flex-shrink-0 flex flex-col">
          <div className="flex-1 min-h-0">
            {graphNodes.length > 0 ? (
              <WorkflowGraph nodes={graphNodes} edges={graphEdges} />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                {content.trim() ? 'No nodes found in workflow' : 'DAG preview will appear here'}
              </div>
            )}
          </div>
          {content.trim() && <CostEstimatePanel yamlContent={content} />}
        </div>
      </div>
    </div>
  );
}
