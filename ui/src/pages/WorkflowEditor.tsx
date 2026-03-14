import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import { WorkflowGraph } from '../components/dag/WorkflowGraph';
import { CostEstimatePanel } from '../components/CostEstimatePanel';
import { SaveAsModal } from '../components/SaveAsModal';
import { useWorkflows, useWorkflow, useSaveWorkflow } from '../hooks/useWorkflows';
import { useCreateRun } from '../hooks/useRuns';
import { parseWorkflowYaml, type WorkflowNode, type WorkflowEdge } from '../lib/yaml-to-graph';

export default function WorkflowEditor() {
  const navigate = useNavigate();
  const location = useLocation();
  const initialContent = (location.state as { initialContent?: string })?.initialContent;
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
  const [showSaveAs, setShowSaveAs] = useState(false);
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

  // Accept initialContent from Scaffold page via router state
  useEffect(() => {
    if (initialContent) {
      setContent(initialContent);
      setOriginalContent('');
      setSelectedPath(null);
      window.history.replaceState({}, document.title);
    }
  }, []);

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

  const handleSaveAs = useCallback((path: string) => {
    saveMutation.mutate(
      { path, content },
      {
        onSuccess: () => {
          setSelectedPath(path);
          setOriginalContent(content);
          setShowSaveAs(false);
        },
      },
    );
  }, [content, saveMutation]);

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
    <div className="flex flex-col h-screen">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-slate-900 border-b border-slate-700">
        <span className="text-sm font-medium text-slate-200">
          {selectedPath ?? (content.trim() ? '(new workflow)' : 'No file selected')}
        </span>
        {isDirty && (
          <span className="text-xs text-amber-400 font-medium">(unsaved changes)</span>
        )}
        <div className="flex-1" />
        <button
          onClick={() => selectedPath ? handleSave() : setShowSaveAs(true)}
          disabled={(!selectedPath && !content.trim()) || (!!selectedPath && !isDirty) || saveMutation.isPending}
          className="px-3 py-1.5 text-sm font-medium rounded bg-slate-700 text-slate-200 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-600"
        >
          {saveMutation.isPending ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={handleRun}
          disabled={!selectedPath || createRun.isPending}
          className="px-3 py-1.5 text-sm font-medium rounded bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {createRun.isPending ? 'Starting...' : 'Run'}
        </button>
      </div>

      {/* Parse error banner */}
      {parseError && (
        <div className="px-4 py-2 bg-red-900/40 border-b border-red-800 text-red-300 text-sm">
          YAML parse error: {parseError}
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Left side: file sidebar + editor */}
        <div className="flex flex-1 min-w-0">
          {/* File sidebar */}
          <div className="w-48 border-r border-slate-700 bg-slate-900 overflow-y-auto flex-shrink-0">
            <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Workflows
            </div>
            {loadingList ? (
              <div className="px-3 py-2 text-sm text-slate-500">Loading...</div>
            ) : fileList.length === 0 ? (
              <div className="px-3 py-2 text-sm text-slate-500">No files found</div>
            ) : (
              fileList.map((f) => (
                <button
                  key={f}
                  onClick={() => setSelectedPath(f)}
                  className={`w-full text-left px-3 py-1.5 text-sm truncate ${
                    f === selectedPath
                      ? 'bg-blue-600/20 text-blue-400 font-medium'
                      : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
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
            {selectedPath || content.trim() ? (
              <Editor
                height="100%"
                language="yaml"
                theme="vs-dark"
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
              <div className="flex items-center justify-center h-full text-slate-500">
                Select a workflow file to edit
              </div>
            )}
          </div>
        </div>

        {/* Right side: DAG preview + Cost Estimate */}
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
          {content.trim() && <CostEstimatePanel yamlContent={content} />}
        </div>
      </div>
      {showSaveAs && <SaveAsModal onSave={handleSaveAs} onClose={() => setShowSaveAs(false)} isPending={saveMutation.isPending} />}
    </div>
  );
}
