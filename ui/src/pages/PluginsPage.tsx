import { useState } from 'react';
import { Puzzle, RefreshCw, Terminal, Bot, Globe, UserCheck, ChevronDown, TerminalSquare } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { usePlugins } from '../hooks/useUtilities';
import { getCaoHealth, startCaoServer, stopCaoServer, type CaoHealthStatus } from '@/lib/api';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { ErrorState } from '@/components/layout/ErrorState';
import { LoadingState } from '@/components/layout/LoadingState';
import { Button } from '@/components/ui/button';

interface AdapterInfo {
  name: string;
  prefix: string;
  description: string;
  icon: typeof Terminal;
  usage: string;
}

const BUILTIN_ADAPTERS: AdapterInfo[] = [
  {
    name: 'Local Agent',
    prefix: 'local',
    description: 'Run Python functions as workflow agents. Best for custom logic, data processing, and tool integrations.',
    icon: Terminal,
    usage: 'agent: local://my_module.my_function',
  },
  {
    name: 'LLM Provider',
    prefix: 'llm',
    description: 'Connect to any LLM via litellm — OpenAI, Anthropic, Gemini, Ollama, and 100+ providers.',
    icon: Bot,
    usage: 'agent: llm://openai/gpt-4o',
  },
  {
    name: 'A2A Remote Agent',
    prefix: 'a2a',
    description: 'Call remote agents over HTTP using the Agent-to-Agent protocol.',
    icon: Globe,
    usage: 'agent: a2a://http://localhost:8001',
  },
  {
    name: 'Human Approval',
    prefix: 'human',
    description: 'Pause workflow for human review. The agent prompts for approval before continuing.',
    icon: UserCheck,
    usage: 'agent: human://approve',
  },
];

const FRAMEWORK_DESCRIPTIONS: Record<string, string> = {
  autogen: 'Microsoft AutoGen multi-agent framework integration',
  crewai: 'CrewAI agent orchestration framework adapter',
  langchain: 'LangChain agent and chain integration',
};

const FRAMEWORK_USAGE: Record<string, string> = {
  autogen: 'agent: autogen://my_agent',
  crewai: 'agent: crewai://researcher',
  langchain: 'agent: langchain://my_chain',
};

const CAO_STATUS_STYLES = {
  online: { dot: 'bg-emerald-400', label: 'Online', text: 'text-emerald-400' },
  degraded: { dot: 'bg-amber-400', label: 'Degraded', text: 'text-amber-400' },
  offline: { dot: 'bg-red-400', label: 'Offline', text: 'text-red-400' },
} as const;

function CaoAdapterCard() {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);

  const { data } = useQuery<CaoHealthStatus>({
    queryKey: ['cao-health'],
    queryFn: getCaoHealth,
    refetchInterval: 30_000,
    retry: 0,
    staleTime: 15_000,
  });

  const status = data?.status ?? 'offline';
  const style = CAO_STATUS_STYLES[status];
  const serverUrl = data?.server_url ?? 'http://localhost:9889';
  const isOnline = status === 'online' || status === 'degraded';

  const handleToggle = async () => {
    setLoading(true);
    try {
      if (isOnline) {
        await stopCaoServer();
      } else {
        await startCaoServer();
      }
      // Refresh health after action
      await new Promise((r) => setTimeout(r, 1500));
      await queryClient.invalidateQueries({ queryKey: ['cao-health'] });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h3 className="text-sm font-medium text-[#80808a] mb-3">
        CLI Agent Orchestrator (1)
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-[#252528] bg-[#1a1a1d]/50 p-4">
          <div className="flex items-start gap-3 mb-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center">
              <TerminalSquare size={16} className="text-orange-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-medium text-[#f0f0f0]">CAO Agent</h4>
                <code className="text-xs font-mono text-cyan-400">cao://</code>
                <span className="flex items-center gap-1.5 ml-auto">
                  <span className={`inline-block w-2 h-2 rounded-full ${style.dot}`} />
                  <span className={`text-xs ${style.text}`}>{style.label}</span>
                </span>
              </div>
              <p className="text-xs text-[#80808a] mt-1">
                Orchestrate CLI AI agents (Claude Code, Kiro CLI, Amazon Q CLI)
                via AWS CAO tmux terminals.
              </p>
            </div>
          </div>
          <div className="bg-[#131315] rounded p-2 overflow-x-auto flex items-center justify-between">
            <code className="text-xs font-mono text-[#80808a]">agent: cao://developer</code>
            <span className="text-[10px] font-mono text-[#4a4a52] ml-2 shrink-0">{serverUrl}</span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div className="flex flex-wrap gap-1.5">
              {['claude_code', 'kiro_cli', 'q_cli'].map((p) => (
                <span key={p} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#252528] text-[#80808a]">
                  {p}
                </span>
              ))}
            </div>
            <button
              onClick={handleToggle}
              disabled={loading}
              className={`text-xs px-3 py-1 rounded border transition-colors disabled:opacity-50 ${
                isOnline
                  ? 'border-red-700/50 text-red-400 hover:bg-red-900/30'
                  : 'border-emerald-700/50 text-emerald-400 hover:bg-emerald-900/30'
              }`}
            >
              {loading ? '...' : isOnline ? 'Stop' : 'Start'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PluginsPage() {
  const { data, isLoading, error, refetch, isFetching } = usePlugins();
  const [showCreateGuide, setShowCreateGuide] = useState(false);

  if (isLoading) {
    return (
      <PageShell>
        <LoadingState message="Loading plugins..." />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <Breadcrumb items={[{ label: 'System' }, { label: 'Plugins' }]} className="mb-4" />
        <ErrorState
          title="Failed to load plugins"
          message={(error as Error).message}
          onRetry={() => refetch()}
        />
      </PageShell>
    );
  }

  const plugins = data?.plugins ?? [];
  const externalPlugins = plugins.filter(p => !p.builtin);

  return (
    <PageShell>
      <Breadcrumb items={[{ label: 'System' }, { label: 'Plugins' }]} className="mb-4" />

      <PageHeader
        title="Plugins & Adapters"
        description="Extend workflows with built-in and third-party agent adapters"
        actions={
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw size={14} className={isFetching ? 'animate-spin mr-1.5' : 'mr-1.5'} />
            Refresh
          </Button>
        }
      />

      <div className="mt-6 flex flex-col gap-6 max-w-4xl">
        {/* Built-in Adapters — card grid */}
        <div>
          <h3 className="text-sm font-medium text-[#80808a] mb-3">
            Built-in Adapters ({BUILTIN_ADAPTERS.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {BUILTIN_ADAPTERS.map((adapter) => (
              <div
                key={adapter.prefix}
                className="rounded-lg border border-[#252528] bg-[#1a1a1d]/50 p-4"
              >
                <div className="flex items-start gap-3 mb-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-green-500/10 flex items-center justify-center">
                    <adapter.icon size={16} className="text-green-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-medium text-[#f0f0f0]">{adapter.name}</h4>
                      <code className="text-xs font-mono text-cyan-400">{adapter.prefix}://</code>
                    </div>
                    <p className="text-xs text-[#80808a] mt-1">{adapter.description}</p>
                  </div>
                </div>
                <div className="bg-[#131315] rounded p-2 overflow-x-auto">
                  <code className="text-xs font-mono text-[#80808a]">{adapter.usage}</code>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* CAO Adapter — external service with health check */}
        <CaoAdapterCard />

        {/* Framework Adapters — only if external plugins exist */}
        {externalPlugins.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-[#80808a] mb-3">
              Framework Adapters ({externalPlugins.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {externalPlugins.map((plugin) => (
                <div
                  key={plugin.name}
                  className="rounded-lg border border-[#252528] bg-[#1a1a1d]/50 p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-medium text-[#f0f0f0]">{plugin.name}</h4>
                      <code className="text-xs font-mono text-cyan-400">{plugin.name}://</code>
                    </div>
                    {plugin.version && (
                      <span className="text-xs font-mono text-[#4a4a52]">v{plugin.version}</span>
                    )}
                  </div>
                  <p className="text-xs text-[#80808a] mb-3">
                    {FRAMEWORK_DESCRIPTIONS[plugin.name] ?? plugin.description}
                  </p>
                  <div className="bg-[#131315] rounded p-2 overflow-x-auto">
                    <code className="text-xs font-mono text-[#80808a]">
                      {FRAMEWORK_USAGE[plugin.name] ?? `agent: ${plugin.name}://my_agent`}
                    </code>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Create Your Own Plugin — collapsible */}
        <div className="rounded-lg border border-[#252528] bg-[#1a1a1d]/50 overflow-hidden">
          <button
            onClick={() => setShowCreateGuide(!showCreateGuide)}
            className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-[#1a1a1d]/30 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Puzzle size={16} className="text-[#80808a]" />
              <span className="text-sm font-medium text-[#80808a]">Create Your Own Plugin</span>
            </div>
            <ChevronDown
              size={14}
              className={`text-[#4a4a52] transition-transform duration-200 ${showCreateGuide ? '' : '-rotate-90'}`}
            />
          </button>
          {showCreateGuide && (
            <div className="px-4 pb-4 border-t border-[#252528]/50">
              <p className="text-xs text-[#80808a] mt-3 mb-3">
                Binex discovers plugins via Python entry points. Add this to your{' '}
                <code className="text-cyan-400">pyproject.toml</code>:
              </p>
              <pre className="text-xs font-mono text-[#80808a] bg-[#131315] rounded p-3 overflow-x-auto">
{`[project.entry-points."binex.plugins"]
my_adapter = "my_package.plugin:MyAdapterPlugin"`}
              </pre>
              <p className="text-xs text-[#80808a] mt-3 mb-2">
                Your plugin class must implement <code className="text-cyan-400">create_adapter(uri, config)</code>:
              </p>
              <pre className="text-xs font-mono text-[#80808a] bg-[#131315] rounded p-3 overflow-x-auto">
{`class MyAdapterPlugin:
    def create_adapter(self, uri: str, config: dict):
        return MyAdapter(uri, **config)`}
              </pre>
              <p className="text-xs text-[#4a4a52] mt-3">
                After installing, your adapter is available as{' '}
                <code className="text-cyan-400">my_adapter://</code> in workflow YAML.
              </p>
            </div>
          )}
        </div>

        {/* Empty state fallback */}
        {plugins.length === 0 && (
          <div className="border border-[#252528] rounded-lg bg-[#1a1a1d]/50 p-8 text-center">
            <Puzzle size={40} className="mx-auto text-[#4a4a52] mb-3" />
            <p className="text-[#80808a] font-medium">No plugins detected</p>
            <p className="text-sm text-[#4a4a52] mt-1">
              Built-in adapters should be available automatically.
              Try restarting <code className="text-cyan-400 text-xs">binex ui</code>.
            </p>
          </div>
        )}
      </div>
    </PageShell>
  );
}
