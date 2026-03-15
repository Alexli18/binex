import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useNodesState, useEdgesState, type Node, type Edge } from 'reactflow';
import yaml from 'js-yaml';
import { EditorToolbar, type EditorMode } from '@/components/editor/EditorToolbar';
import { EditorCanvas } from '@/components/editor/EditorCanvas';
import { EditorYaml } from '@/components/editor/EditorYaml';
import { EditorSidebar } from '@/components/editor/EditorSidebar';
import { useWorkflows, useWorkflow, useSaveWorkflow } from '../hooks/useWorkflows';
import { useCreateRun } from '../hooks/useRuns';
import { parseWorkflowYaml, type WorkflowNode, type WorkflowEdge } from '../lib/yaml-to-graph';
import { graphToYaml } from '../lib/graph-to-yaml';
import { api } from '../lib/api';
import { toast } from 'sonner';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';

// ---------------------------------------------------------------------------
// Helpers (kept local — only used by the orchestrator)
// ---------------------------------------------------------------------------

function agentToNodeType(agent: string): { nodeType: string; color: string } {
  if (agent.startsWith('llm://')) return { nodeType: 'llm', color: '#3b82f6' };
  if (agent.startsWith('local://')) return { nodeType: 'local', color: '#22c55e' };
  if (agent.startsWith('human://')) {
    if (agent.includes('input')) return { nodeType: 'human-input', color: '#a855f7' };
    return { nodeType: 'human-approve', color: '#f97316' };
  }
  if (agent.startsWith('a2a://')) return { nodeType: 'a2a', color: '#06b6d4' };
  return { nodeType: 'local', color: '#22c55e' };
}

interface ParsedYamlWorkflow {
  name?: string;
  nodes?: Record<string, { agent: string; depends_on?: string[]; config?: Record<string, unknown> }>;
}

function yamlToRfGraph(yamlContent: string): { nodes: Node[]; edges: Edge[] } {
  if (!yamlContent.trim()) return { nodes: [], edges: [] };
  const parsed = yaml.load(yamlContent) as ParsedYamlWorkflow;
  if (!parsed?.nodes) return { nodes: [], edges: [] };

  const entries = Object.entries(parsed.nodes);
  const nodes: Node[] = entries.map(([id, spec], i) => {
    const agent = spec.agent || 'local://echo';
    const { nodeType, color } = agentToNodeType(agent);
    return {
      id,
      type: 'editable',
      position: { x: 250, y: i * 120 + 50 },
      data: { label: id, nodeType, agent, config: spec.config || {}, color },
    };
  });

  const edges: Edge[] = [];
  for (const [id, spec] of entries) {
    if (spec.depends_on) {
      for (const dep of spec.depends_on) {
        edges.push({ id: `${dep}->${id}`, source: dep, target: id });
      }
    }
  }
  return { nodes, edges };
}

// ---------------------------------------------------------------------------
// Main orchestrator
// ---------------------------------------------------------------------------

export default function WorkflowEditor() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const initialContent = (location.state as { initialContent?: string })?.initialContent;
  const fileParam = searchParams.get('file');
  const { data: workflows, isLoading: loadingList } = useWorkflows();
  const [selectedPath, setSelectedPath] = useState<string | null>(fileParam);
  const { data: workflowData } = useWorkflow(selectedPath);
  const saveMutation = useSaveWorkflow();
  const createRun = useCreateRun();

  const [content, setContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [mode, setMode] = useState<EditorMode>('yaml');
  const [graphNodes, setGraphNodes] = useState<WorkflowNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<WorkflowEdge[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);
  const [showSaveAs, setShowSaveAs] = useState(false);
  const [showFiles, setShowFiles] = useState(true);
  const [showCost, setShowCost] = useState(true);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const syncDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [rfNodes, setRfNodes, onRfNodesChange] = useNodesState([]);
  const [rfEdges, setRfEdges, onRfEdgesChange] = useEdgesState([]);

  const isDirty = content !== originalContent;

  // Load file content when workflow data arrives
  useEffect(() => {
    if (workflowData?.content != null) {
      setContent(workflowData.content);
      setOriginalContent(workflowData.content);
    }
  }, [workflowData]);

  // Sync selectedPath with URL query param whenever it changes
  // Also clear stale content so old file data is never shown
  useEffect(() => {
    if (fileParam) {
      setSelectedPath((prev) => {
        if (prev !== fileParam) {
          setContent('');
          setOriginalContent('');
        }
        return fileParam;
      });
    }
  }, [fileParam]);

  // Auto-select first workflow when no file is specified
  useEffect(() => {
    if (!fileParam && !selectedPath && workflows && workflows.length > 0) {
      setSelectedPath(workflows[0]);
    }
  }, [workflows, selectedPath, fileParam]);

  // Accept initialContent from Scaffold page
  useEffect(() => {
    if (initialContent) {
      setContent(initialContent);
      setOriginalContent('');
      setSelectedPath(null);
      window.history.replaceState({}, document.title);
    }
  }, []);

  // Debounced YAML -> DAG preview
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
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [content]);

  // beforeunload
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => { if (isDirty) e.preventDefault(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  // Sync visual -> YAML
  const syncVisualToYaml = useCallback(() => {
    if (syncDebounceRef.current) clearTimeout(syncDebounceRef.current);
    syncDebounceRef.current = setTimeout(() => {
      const yamlStr = graphToYaml(rfNodes, rfEdges);
      setContent(yamlStr);
    }, 500);
  }, [rfNodes, rfEdges]);

  useEffect(() => {
    const handler = () => syncVisualToYaml();
    window.addEventListener('binex:node-data-change', handler);
    return () => window.removeEventListener('binex:node-data-change', handler);
  }, [syncVisualToYaml]);

  const switchToVisual = useCallback(() => {
    try {
      const { nodes, edges } = yamlToRfGraph(content);
      setRfNodes(nodes);
      setRfEdges(edges);
      setParseError(null);
      setMode('visual');
    } catch (err) {
      setParseError(err instanceof Error ? err.message : String(err));
    }
  }, [content, setRfNodes, setRfEdges]);

  const switchToYaml = useCallback(() => {
    const yamlStr = graphToYaml(rfNodes, rfEdges);
    setContent(yamlStr);
    setMode('yaml');
  }, [rfNodes, rfEdges]);

  const handleSave = useCallback(() => {
    if (!selectedPath) return;
    saveMutation.mutate(
      { path: selectedPath, content },
      { onSuccess: () => { setOriginalContent(content); toast.success('Workflow saved'); } },
    );
  }, [selectedPath, content, saveMutation]);

  const handleSaveAs = useCallback(
    (path: string) => {
      saveMutation.mutate(
        { path, content },
        {
          onSuccess: () => {
            setSelectedPath(path);
            setOriginalContent(content);
            setShowSaveAs(false);
            toast.success('Workflow saved');
          },
        },
      );
    },
    [content, saveMutation],
  );

  const handleRun = useCallback(async () => {
    let pathToRun = selectedPath;
    if (!pathToRun) {
      const tempPath = `_temp_workflow_${Date.now()}.yaml`;
      try {
        await api.put(`/workflows/${tempPath}`, { content });
        pathToRun = tempPath;
        setSelectedPath(tempPath);
        setOriginalContent(content);
      } catch { return; }
    } else if (isDirty) {
      try {
        await api.put(`/workflows/${pathToRun}`, { content });
        setOriginalContent(content);
      } catch { return; }
    }
    createRun.mutate(
      { workflow_path: pathToRun },
      {
        onSuccess: (data) => {
          navigate(data.status === 'running' ? `/runs/${data.run_id}/live` : `/runs/${data.run_id}`);
        },
        onError: (err) => { toast.error(`Run failed: ${(err as Error).message}`); },
      },
    );
  }, [selectedPath, content, isDirty, createRun, navigate]);

  // Keyboard shortcuts: Cmd+S to save, Cmd+Enter to run
  useKeyboardShortcuts(useMemo(() => [
    { key: 's', meta: true, handler: () => { selectedPath ? handleSave() : setShowSaveAs(true); } },
    { key: 'Enter', meta: true, handler: () => { handleRun(); } },
  ], [handleSave, handleRun, selectedPath]));

  const handleEditorChange = useCallback((value: string | undefined) => {
    setContent(value ?? '');
  }, []);

  const fileList = useMemo(() => workflows ?? [], [workflows]);

  return (
    <div className="flex flex-col h-screen">
      <EditorToolbar
        selectedPath={selectedPath}
        isDirty={isDirty}
        mode={mode}
        showFiles={showFiles}
        showCost={showCost}
        isSaving={saveMutation.isPending}
        isRunning={createRun.isPending}
        hasContent={!!content.trim()}
        onToggleFiles={() => setShowFiles(!showFiles)}
        onToggleCost={() => setShowCost(!showCost)}
        onSwitchToVisual={switchToVisual}
        onSwitchToYaml={switchToYaml}
        onSave={() => (selectedPath ? handleSave() : setShowSaveAs(true))}
        onRun={handleRun}
      />

      {parseError && (
        <div className="px-4 py-2 bg-red-900/40 border-b border-red-800 text-red-300 text-sm">
          YAML parse error: {parseError}
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        {/* File sidebar */}
        {showFiles && (
          <div className="w-48 border-r border-slate-700 bg-slate-900 overflow-y-auto flex-shrink-0">
            <div className="flex items-center justify-between px-3 py-2">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Workflows</span>
              <button
                onClick={() => {
                  setSelectedPath(null);
                  setContent('');
                  setOriginalContent('');
                  setRfNodes([]);
                  setRfEdges([]);
                  setMode('visual');
                }}
                className="text-[10px] px-1.5 py-0.5 rounded bg-blue-600 text-white hover:bg-blue-500"
                title="Create new workflow"
              >
                + New
              </button>
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
        )}

        {mode === 'visual' ? (
          <EditorCanvas
            rfNodes={rfNodes}
            rfEdges={rfEdges}
            setRfNodes={setRfNodes}
            setRfEdges={setRfEdges}
            onRfNodesChange={onRfNodesChange}
            onRfEdgesChange={onRfEdgesChange}
            onGraphChange={syncVisualToYaml}
          />
        ) : (
          <EditorYaml
            content={content}
            selectedPath={selectedPath}
            graphNodes={graphNodes}
            graphEdges={graphEdges}
            onContentChange={handleEditorChange}
          />
        )}
      </div>

      <EditorSidebar
        showCost={showCost}
        hasContent={!!content.trim()}
        yamlContent={content}
        showSaveAs={showSaveAs}
        isSaving={saveMutation.isPending}
        onSaveAs={handleSaveAs}
        onCloseSaveAs={() => setShowSaveAs(false)}
      />
    </div>
  );
}
