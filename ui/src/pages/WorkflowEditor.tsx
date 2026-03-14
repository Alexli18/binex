import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import ReactFlow, {
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  addEdge,
  useReactFlow,
  Background,
  Controls,
  type Connection,
  type Node,
  type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import yaml from 'js-yaml';
import { FolderOpen, DollarSign } from 'lucide-react';
import { WorkflowGraph } from '../components/dag/WorkflowGraph';
import { CostEstimatePanel } from '../components/CostEstimatePanel';
import { SaveAsModal } from '../components/SaveAsModal';
import { NodePalette, type NodeTypeConfig } from '../components/editor/NodePalette';
import { EditableNode } from '../components/editor/EditableNode';
import { useWorkflows, useWorkflow, useSaveWorkflow } from '../hooks/useWorkflows';
import { useCreateRun } from '../hooks/useRuns';
import { parseWorkflowYaml, type WorkflowNode, type WorkflowEdge } from '../lib/yaml-to-graph';
import { graphToYaml } from '../lib/graph-to-yaml';
import { api } from '../lib/api';

const rfNodeTypes = { editable: EditableNode };

type EditorMode = 'visual' | 'yaml';

// Map agent prefix to node type config
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

// Parse YAML to ReactFlow nodes + edges with full EditableNode data
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
      data: {
        label: id,
        nodeType,
        agent,
        config: spec.config || {},
        color,
      },
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

let nodeIdCounter = 0;

// Inner component that uses useReactFlow (must be inside ReactFlowProvider)
function VisualCanvas({
  rfNodes,
  rfEdges,
  setRfNodes,
  setRfEdges,
  onRfNodesChange,
  onRfEdgesChange,
  onGraphChange,
}: {
  rfNodes: Node[];
  rfEdges: Edge[];
  setRfNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setRfEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  onRfNodesChange: ReturnType<typeof useNodesState>[2];
  onRfEdgesChange: ReturnType<typeof useEdgesState>[2];
  onGraphChange: () => void;
}) {
  const { screenToFlowPosition } = useReactFlow();

  const onConnect = useCallback(
    (connection: Connection) => {
      setRfEdges((eds) => addEdge(connection, eds));
      setTimeout(onGraphChange, 0);
    },
    [setRfEdges, onGraphChange],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const raw = event.dataTransfer.getData('application/reactflow');
      if (!raw) return;
      const ntConfig: NodeTypeConfig = JSON.parse(raw);
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      nodeIdCounter += 1;
      const id = `${ntConfig.type}_${nodeIdCounter}`;
      const newNode: Node = {
        id,
        type: 'editable',
        position,
        data: {
          label: id,
          nodeType: ntConfig.type,
          agent: ntConfig.defaultAgent,
          config: {},
          color: ntConfig.color,
        },
      };
      setRfNodes((nds) => [...nds, newNode]);
      setTimeout(onGraphChange, 0);
    },
    [screenToFlowPosition, setRfNodes, onGraphChange],
  );

  const onNodesDelete = useCallback(() => {
    setTimeout(onGraphChange, 0);
  }, [onGraphChange]);

  const onEdgesDelete = useCallback(() => {
    setTimeout(onGraphChange, 0);
  }, [onGraphChange]);

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      onNodesChange={onRfNodesChange}
      onEdgesChange={onRfEdgesChange}
      onConnect={onConnect}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onNodesDelete={onNodesDelete}
      onEdgesDelete={onEdgesDelete}
      nodeTypes={rfNodeTypes}
      fitView
      deleteKeyCode="Delete"
      className="bg-slate-950"
    >
      <Background color="#334155" gap={20} />
      <Controls className="!bg-slate-800 !border-slate-700 !shadow-lg" />
    </ReactFlow>
  );
}

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
  const [mode, setMode] = useState<EditorMode>('yaml');
  const [graphNodes, setGraphNodes] = useState<WorkflowNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<WorkflowEdge[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);
  const [showSaveAs, setShowSaveAs] = useState(false);
  const [showFiles, setShowFiles] = useState(true);
  const [showCost, setShowCost] = useState(true);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const syncDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ReactFlow state
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

  // Auto-select first workflow
  useEffect(() => {
    if (workflows && workflows.length > 0 && !selectedPath) {
      setSelectedPath(workflows[0]);
    }
  }, [workflows, selectedPath]);

  // Accept initialContent from Scaffold page
  useEffect(() => {
    if (initialContent) {
      setContent(initialContent);
      setOriginalContent('');
      setSelectedPath(null);
      window.history.replaceState({}, document.title);
    }
  }, []);

  // Debounced YAML → DAG preview graph (for YAML mode right panel)
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

  // beforeunload handler
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) e.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  // Sync visual changes → YAML (debounced)
  const syncVisualToYaml = useCallback(() => {
    if (syncDebounceRef.current) clearTimeout(syncDebounceRef.current);
    syncDebounceRef.current = setTimeout(() => {
      const yamlStr = graphToYaml(rfNodes, rfEdges);
      setContent(yamlStr);
    }, 500);
  }, [rfNodes, rfEdges]);

  // Listen for node data changes (from EditableNode inline editing)
  useEffect(() => {
    const handler = () => syncVisualToYaml();
    window.addEventListener('binex:node-data-change', handler);
    return () => window.removeEventListener('binex:node-data-change', handler);
  }, [syncVisualToYaml]);

  // Switch mode: YAML → Visual
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

  // Switch mode: Visual → YAML
  const switchToYaml = useCallback(() => {
    const yamlStr = graphToYaml(rfNodes, rfEdges);
    setContent(yamlStr);
    setMode('yaml');
  }, [rfNodes, rfEdges]);

  const handleSave = useCallback(() => {
    if (!selectedPath) return;
    saveMutation.mutate(
      { path: selectedPath, content },
      { onSuccess: () => setOriginalContent(content) },
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
          },
        },
      );
    },
    [content, saveMutation],
  );

  const handleRun = useCallback(async () => {
    let pathToRun = selectedPath;

    // If no path, need to save first
    if (!pathToRun) {
      // Auto-save as temp workflow
      const tempPath = `_temp_workflow_${Date.now()}.yaml`;
      try {
        await api.put(`/workflows/${tempPath}`, { content });
        pathToRun = tempPath;
        setSelectedPath(tempPath);
        setOriginalContent(content);
      } catch {
        return;
      }
    } else if (isDirty) {
      // Save current changes before running
      try {
        await api.put(`/workflows/${pathToRun}`, { content });
        setOriginalContent(content);
      } catch {
        return;
      }
    }

    createRun.mutate(
      { workflow_path: pathToRun },
      {
        onSuccess: (data) => {
          if (data.status === 'running') {
            navigate(`/runs/${data.run_id}/live`);
          } else {
            // Completed synchronously (non-human workflow)
            navigate(`/runs/${data.run_id}`);
          }
        },
        onError: (err) => {
          alert(`Run failed: ${(err as Error).message}`);
        },
      },
    );
  }, [selectedPath, content, isDirty, createRun, navigate]);

  const handleEditorChange = useCallback((value: string | undefined) => {
    setContent(value ?? '');
  }, []);

  const fileList = useMemo(() => workflows ?? [], [workflows]);

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

        {/* Panel toggles */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowFiles(!showFiles)}
            className={`p-1.5 rounded text-xs ${showFiles ? 'text-blue-400 bg-slate-700' : 'text-slate-500 hover:text-slate-300'}`}
            title="Toggle file browser"
          >
            <FolderOpen size={14} />
          </button>
          <button
            onClick={() => setShowCost(!showCost)}
            className={`p-1.5 rounded text-xs ${showCost ? 'text-blue-400 bg-slate-700' : 'text-slate-500 hover:text-slate-300'}`}
            title="Toggle cost estimate"
          >
            <DollarSign size={14} />
          </button>
        </div>

        {/* Mode toggle */}
        <div className="flex rounded overflow-hidden border border-slate-600">
          <button
            onClick={switchToVisual}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              mode === 'visual'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Visual
          </button>
          <button
            onClick={switchToYaml}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              mode === 'yaml'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            YAML
          </button>
        </div>

        <button
          onClick={() => (selectedPath ? handleSave() : setShowSaveAs(true))}
          disabled={
            (!selectedPath && !content.trim()) ||
            (!!selectedPath && !isDirty) ||
            saveMutation.isPending
          }
          className="px-3 py-1.5 text-sm font-medium rounded bg-slate-700 text-slate-200 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed border border-slate-600"
        >
          {saveMutation.isPending ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={handleRun}
          disabled={!content.trim() || createRun.isPending}
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
        {/* File sidebar */}
        {showFiles && (
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
        )}

        {mode === 'visual' ? (
          /* ── Visual Mode ── */
          <div className="flex flex-1 min-w-0">
            <NodePalette />
            <div className="flex-1 min-w-0">
              <ReactFlowProvider>
                <VisualCanvas
                  rfNodes={rfNodes}
                  rfEdges={rfEdges}
                  setRfNodes={setRfNodes}
                  setRfEdges={setRfEdges}
                  onRfNodesChange={onRfNodesChange}
                  onRfEdgesChange={onRfEdgesChange}
                  onGraphChange={syncVisualToYaml}
                />
              </ReactFlowProvider>
            </div>
          </div>
        ) : (
          /* ── YAML Mode ── */
          <div className="flex flex-1 min-w-0">
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

            {/* DAG preview + Cost */}
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
        )}
      </div>

      {/* Cost estimate (both modes) */}
      {showCost && content.trim() && <CostEstimatePanel yamlContent={content} />}

      {showSaveAs && (
        <SaveAsModal
          onSave={handleSaveAs}
          onClose={() => setShowSaveAs(false)}
          isPending={saveMutation.isPending}
        />
      )}
    </div>
  );
}
