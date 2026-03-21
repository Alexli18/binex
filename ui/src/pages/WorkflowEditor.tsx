import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useNodesState, useEdgesState, type Node, type Edge } from 'reactflow';
import yaml from 'js-yaml';
import { EditorToolbar, type EditorMode } from '@/components/editor/EditorToolbar';
import { EditorCanvas } from '@/components/editor/EditorCanvas';
import { EditorYaml } from '@/components/editor/EditorYaml';
import { EditorSidebar } from '@/components/editor/EditorSidebar';
import { WorkflowEditorProvider } from '@/components/editor/WorkflowEditorContext';
import { WorkflowSettingsPanel, type McpServerConfig } from '@/components/editor/WorkflowSettingsPanel';
import { useWorkflows, useWorkflow, useSaveWorkflow } from '../hooks/useWorkflows';
import { useCreateRun } from '../hooks/useRuns';
import { parseWorkflowYaml, type WorkflowNode, type WorkflowEdge } from '../lib/yaml-to-graph';
import { graphToYaml } from '../lib/graph-to-yaml';
import { api } from '../lib/api';
import { toast } from 'sonner';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { Input } from '@/components/ui/input';
import { chartColors } from '@/lib/design-tokens';

// ---------------------------------------------------------------------------
// Helpers (kept local — only used by the orchestrator)
// ---------------------------------------------------------------------------

/**
 * Maps agent URI prefixes to a node type and a border/icon colour.
 *
 * Hex values are taken directly from the design-tokens palette so that
 * EditableNode's inline `style={{ borderColor }}` stays in sync with the
 * Tailwind classes used in read-only CustomNode:
 *   llm    → violet-500  (#8b5cf6)
 *   local  → cyan-500    (#06b6d4)
 *   a2a    → indigo-500  (#6366f1)
 *   human  → amber-500   (#f59e0b)
 */
function agentToNodeType(agent: string): { nodeType: string; color: string } {
  if (agent.startsWith('llm://')) return { nodeType: 'llm', color: '#8b5cf6' };
  if (agent.startsWith('local://')) return { nodeType: 'local', color: '#06b6d4' };
  if (agent.startsWith('human://')) {
    // human-input and human-approve both map to human:// prefix in design-tokens
    if (agent.includes('input')) return { nodeType: 'human-input', color: '#f59e0b' };
    return { nodeType: 'human-approve', color: '#f59e0b' };
  }
  if (agent.startsWith('a2a://')) return { nodeType: 'a2a', color: '#6366f1' };
  if (agent.startsWith('cao://')) return { nodeType: 'cao', color: chartColors.cao };
  return { nodeType: 'local', color: '#06b6d4' };
}

interface ParsedYamlWorkflow {
  name?: string;
  schedule?: string;
  mcp_servers?: Record<string, unknown>;
  nodes?: Record<string, { agent: string; depends_on?: string[]; config?: Record<string, unknown>; system_prompt?: string; inputs?: Record<string, string>; outputs?: string[]; tools?: string[]; cao?: Record<string, unknown> }>;
}

interface YamlParseResult {
  nodes: Node[];
  edges: Edge[];
  mcpServers: Record<string, unknown>;
  schedule: string;
}

function yamlToRfGraph(yamlContent: string): YamlParseResult {
  if (!yamlContent.trim()) return { nodes: [], edges: [], mcpServers: {}, schedule: '' };
  const parsed = yaml.load(yamlContent) as ParsedYamlWorkflow;
  if (!parsed?.nodes) return { nodes: [], edges: [], mcpServers: {}, schedule: '' };

  const entries = Object.entries(parsed.nodes);
  const nodes: Node[] = entries.map(([id, spec], i) => {
    const agent = spec.agent ?? 'local://echo';
    const { nodeType, color } = agentToNodeType(agent);
    return {
      id,
      type: 'editable',
      position: { x: 250, y: i * 120 + 50 },
      data: {
        label: id,
        nodeType,
        agent,
        config: { ...spec.config, ...(spec.system_prompt ? { system_prompt: spec.system_prompt } : {}), ...(spec.cao ?? {}) },
        system_prompt: spec.system_prompt,
        inputs: spec.inputs,
        outputs: spec.outputs,
        tools: spec.tools ?? [],
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
  return {
    nodes,
    edges,
    mcpServers: parsed.mcp_servers ?? {},
    schedule: parsed.schedule ?? '',
  };
}

// ---------------------------------------------------------------------------
// Main orchestrator
// ---------------------------------------------------------------------------

export default function WorkflowEditor() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const initialContent = (location.state as { initialContent?: string } | null)?.initialContent;
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
  const [filesOpen, setFilesOpen] = useState(false);
  const [fileFilter, setFileFilter] = useState('');
  const [mcpServers, setMcpServers] = useState<Record<string, McpServerConfig>>({});
  const [schedule, setSchedule] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const syncDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [rfNodes, setRfNodes, onRfNodesChange] = useNodesState([]);
  const [rfEdges, setRfEdges, onRfEdgesChange] = useEdgesState([]);

  const isDirty = content !== originalContent;

  const filteredFiles = useMemo(() => {
    const list = workflows ?? [];
    if (!fileFilter) return list;
    const q = fileFilter.toLowerCase();
    return list.filter((f) => f.toLowerCase().includes(q));
  }, [workflows, fileFilter]);

  // Load file content when workflow data arrives or selected path changes
  useEffect(() => {
    if (workflowData?.content != null) {
      setContent(workflowData.content);
      setOriginalContent(workflowData.content);
      // Extract workflow-level settings from YAML
      try {
        const result = yamlToRfGraph(workflowData.content);
        setMcpServers((result.mcpServers ?? {}) as Record<string, McpServerConfig>);
        setSchedule(result.schedule ?? '');
        // If in visual mode, also sync RF nodes/edges
        if (mode === 'visual') {
          setRfNodes(result.nodes);
          setRfEdges(result.edges);
        }
      } catch {
        // parse error handled by debounced effect
      }
    }
  }, [workflowData, selectedPath, mode, setRfNodes, setRfEdges]);

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
  }, [initialContent]);

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
      const yamlStr = graphToYaml(rfNodes, rfEdges, 'my-workflow', { mcpServers, schedule });
      setContent(yamlStr);
    }, 500);
  }, [rfNodes, rfEdges, mcpServers, schedule]);

  useEffect(() => {
    const handler = () => syncVisualToYaml();
    window.addEventListener('binex:node-data-change', handler);
    return () => window.removeEventListener('binex:node-data-change', handler);
  }, [syncVisualToYaml]);

  const switchToVisual = useCallback(() => {
    try {
      const result = yamlToRfGraph(content);
      setRfNodes(result.nodes);
      setRfEdges(result.edges);
      setMcpServers((result.mcpServers ?? {}) as Record<string, McpServerConfig>);
      setSchedule(result.schedule ?? '');
      setParseError(null);
      setMode('visual');
    } catch (err) {
      setParseError(err instanceof Error ? err.message : String(err));
    }
  }, [content, setRfNodes, setRfEdges]);

  const switchToYaml = useCallback(() => {
    const yamlStr = graphToYaml(rfNodes, rfEdges, 'my-workflow', { mcpServers, schedule });
    setContent(yamlStr);
    setMode('yaml');
  }, [rfNodes, rfEdges, mcpServers, schedule]);

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

  // Keyboard shortcuts: Cmd+S to save, Cmd+Enter to run, Cmd+O to open files
  useKeyboardShortcuts(useMemo(() => [
    { key: 's', meta: true, handler: () => { if (selectedPath) { handleSave(); } else { setShowSaveAs(true); } } },
    { key: 'Enter', meta: true, handler: () => { handleRun(); } },
    { key: 'o', meta: true, handler: () => { setFilesOpen((v) => !v); } },
  ], [handleSave, handleRun, selectedPath]));

  // Escape to close file browser
  const filePanelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!filesOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setFilesOpen(false);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [filesOpen]);

  // Focus trap: keep focus inside file browser panel when open
  useEffect(() => {
    if (!filesOpen || !filePanelRef.current) return;
    const panel = filePanelRef.current;
    const focusable = panel.querySelectorAll<HTMLElement>(
      'button, input, [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;

    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    panel.addEventListener('keydown', handleTab);
    return () => panel.removeEventListener('keydown', handleTab);
  }, [filesOpen]);

  const handleEditorChange = useCallback((value: string | undefined) => {
    setContent(value ?? '');
  }, []);

  return (
    <div className="flex flex-col h-screen">
      <EditorToolbar
        selectedPath={selectedPath}
        isDirty={isDirty}
        mode={mode}
        isSaving={saveMutation.isPending}
        isRunning={createRun.isPending}
        hasContent={!!content.trim()}
        onOpenFiles={() => setFilesOpen(true)}
        onSwitchToVisual={switchToVisual}
        onSwitchToYaml={switchToYaml}
        onSave={() => (selectedPath ? handleSave() : setShowSaveAs(true))}
        onRun={handleRun}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <WorkflowEditorProvider value={{ mcpServerNames: Object.keys(mcpServers) }}>
      <div className="flex flex-1 min-h-0">
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
            onContentChange={handleEditorChange}
          />
        )}
      </div>

      </WorkflowEditorProvider>

      {/* Workflow Settings Panel */}
      <WorkflowSettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        mcpServers={mcpServers}
        onMcpServersChange={(servers) => { setMcpServers(servers); syncVisualToYaml(); }}
        schedule={schedule}
        onScheduleChange={(cron) => { setSchedule(cron); syncVisualToYaml(); }}
      />

      {/* Status bar */}
      <div className="flex items-center gap-4 px-4 py-1.5 bg-slate-900/80 border-t border-slate-700/50 text-xs text-slate-500">
        {parseError ? (
          <span className="text-red-400">Parse error: {parseError}</span>
        ) : content.trim() ? (
          <span className="text-emerald-400">YAML valid</span>
        ) : null}
        {graphNodes.length > 0 && (
          <span>Nodes: {graphNodes.length}</span>
        )}
        {graphEdges.length > 0 && (
          <span>Edges: {graphEdges.length}</span>
        )}
      </div>

      {/* Slide-out file browser */}
      {filesOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 z-40 transition-opacity"
            onClick={() => setFilesOpen(false)}
          />
          {/* Panel */}
          <div
            ref={filePanelRef}
            role="dialog"
            aria-label="Open workflow file"
            className="fixed left-12 top-0 bottom-0 w-72 bg-slate-900 border-r border-slate-700 z-50 shadow-xl animate-slide-in-right overflow-y-auto"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
              <span className="text-sm font-semibold text-slate-200">Open Workflow</span>
              <button
                onClick={() => {
                  setSelectedPath(null);
                  setContent('');
                  setOriginalContent('');
                  setRfNodes([]);
                  setRfEdges([]);
                  setMode('visual');
                  setFilesOpen(false);
                }}
                className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-500 transition-colors"
              >
                + New
              </button>
            </div>
            {/* Search */}
            <div className="px-3 py-2">
              <Input
                type="text"
                placeholder="Filter workflows..."
                className="h-8"
                onChange={(e) => setFileFilter(e.target.value)}
                autoFocus
              />
            </div>
            {/* File list */}
            {loadingList ? (
              <div className="px-4 py-3 text-sm text-slate-500">Loading...</div>
            ) : filteredFiles.length === 0 ? (
              <div className="px-4 py-3 text-sm text-slate-500">No files found</div>
            ) : (
              filteredFiles.map((f) => (
                <button
                  key={f}
                  onClick={() => {
                    setSelectedPath(f);
                    setContent('');
                    setOriginalContent('');
                    setFilesOpen(false);
                  }}
                  className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
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
        </>
      )}

      <EditorSidebar
        showCost={false}
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
