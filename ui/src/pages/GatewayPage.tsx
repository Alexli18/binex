import { Play, Radio, RefreshCw } from 'lucide-react';
import { useGateway, useGatewayStart } from '../hooks/useUtilities';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { ErrorState } from '@/components/layout/ErrorState';
import { LoadingState } from '@/components/layout/LoadingState';
import { Button } from '@/components/ui/button';
import { StatusBadge } from '@/components/common/StatusBadge';

/**
 * Maps agent health strings to the canonical status keys used by design-tokens
 * so that StatusBadge can apply the correct colour token set.
 */
function normalizeAgentStatus(status: string): string {
  if (status === 'healthy' || status === 'online') return 'completed';
  if (status === 'unhealthy' || status === 'offline') return 'failed';
  return status;
}

export default function GatewayPage() {
  const { data, isLoading, error, refetch, isFetching } = useGateway();
  const startMut = useGatewayStart();

  if (isLoading) {
    return (
      <PageShell>
        <LoadingState message="Loading gateway status..." />
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <Breadcrumb items={[{ label: 'System' }, { label: 'Gateway' }]} className="mb-4" />
        <ErrorState
          title="Failed to load gateway status"
          message={(error as Error).message}
          onRetry={() => refetch()}
        />
      </PageShell>
    );
  }

  const isOnline = data?.status === 'online';
  const agents = data?.agents ?? [];

  return (
    <PageShell>
      <Breadcrumb items={[{ label: 'System' }, { label: 'Gateway' }]} className="mb-4" />

      {/* FIX 4: Less jargon in description */}
      <PageHeader
        title="A2A Gateway"
        description="Route tasks between independent AI agents"
        actions={
          <Button
            onClick={() => refetch()}
            disabled={isFetching}
            variant="outline"
            size="sm"
          >
            <RefreshCw size={14} className={isFetching ? 'animate-spin mr-1.5' : 'mr-1.5'} />
            Refresh
          </Button>
        }
      />

      <div className="mt-6 flex flex-col gap-6 max-w-4xl">
        {/* Status + Action */}
        {isOnline ? (
          <div className="rounded-lg border p-6 bg-green-900/20 border-green-700/30">
            <div className="flex items-center gap-4">
              <div className="w-4 h-4 rounded-full bg-green-400 shadow-lg shadow-green-400/50" />
              <div>
                <h2 className="text-lg font-semibold text-slate-200">Gateway Online</h2>
                {data?.message && (
                  <p className="text-sm text-slate-400 mt-0.5">{data.message}</p>
                )}
              </div>
            </div>
            {agents.length > 0 && (
              <p className="text-sm text-slate-400 mt-3">
                {agents.length} registered agent{agents.length > 1 ? 's' : ''}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Status banner with Start button */}
            <div className="rounded-lg border p-6 bg-slate-800/50 border-slate-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-4 h-4 rounded-full bg-slate-500" />
                  <h2 className="text-lg font-semibold text-slate-200">Gateway Offline</h2>
                </div>
                <Button
                  size="sm"
                  onClick={() => startMut.mutate()}
                  disabled={startMut.isPending}
                >
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                  Start Gateway
                </Button>
              </div>
            </div>

            {/* Getting Started — 3 steps */}
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
              <h3 className="text-sm font-semibold text-slate-200 mb-1">What is the A2A Gateway?</h3>
              <p className="text-sm text-slate-400 mb-5">
                The gateway connects multiple AI agents into a single workflow — agents communicate
                through it, sharing tasks and results.
              </p>

              <div className="space-y-4">
                {/* Step 1 */}
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 text-xs font-bold flex items-center justify-center">
                    1
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-300">Create gateway.yaml</p>
                    <pre className="mt-2 text-xs font-mono text-slate-400 bg-slate-900 rounded p-3 overflow-x-auto">
{`agents:
  - name: researcher
    url: http://localhost:8001
    skills: [research, summarize]
  - name: writer
    url: http://localhost:8002
    skills: [write, edit]`}
                    </pre>
                  </div>
                </div>

                {/* Step 2 */}
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 text-xs font-bold flex items-center justify-center">
                    2
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-300">Start the gateway</p>
                    <div className="flex items-center gap-3 mt-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startMut.mutate()}
                        disabled={startMut.isPending}
                      >
                        <Play className="w-3.5 h-3.5 mr-1.5" />
                        Start Gateway
                      </Button>
                      <span className="text-xs text-slate-500">or</span>
                      <code className="text-xs font-mono text-cyan-400 bg-slate-900 rounded px-2.5 py-1.5">
                        binex gateway
                      </code>
                    </div>
                  </div>
                </div>

                {/* Step 3 */}
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 text-xs font-bold flex items-center justify-center">
                    3
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-300">
                      Agents register automatically
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      Once running, the gateway discovers agents defined in gateway.yaml and shows them below.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Agent table */}
        {isOnline && agents.length > 0 && (
          <div className="border border-slate-700 rounded-lg bg-slate-800/50 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-700">
              <h3 className="text-sm font-medium text-slate-300">
                Registered Agents
              </h3>
            </div>
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 font-medium text-slate-400">
                    Name
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-slate-400">
                    URL
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-slate-400">
                    Status
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-slate-400">
                    Skills
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {agents.map((agent) => (
                  <tr
                    key={agent.name}
                    className="hover:bg-slate-700/30 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-slate-200">
                      {agent.name}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">
                      {agent.url}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge
                        status={normalizeAgentStatus(agent.status)}
                        dot
                      />
                    </td>
                    <td className="px-4 py-3">
                      {agent.skills.length === 0 ? (
                        <span className="text-slate-500 text-xs">none</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {agent.skills.map((skill) => (
                            <span
                              key={skill}
                              className="text-xs bg-slate-900 text-slate-300 px-1.5 py-0.5 rounded"
                            >
                              {skill}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* FIX 3: Online but no agents — with YAML example */}
        {isOnline && agents.length === 0 && (
          <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-6">
            <div className="text-center mb-4">
              <Radio size={36} className="mx-auto text-slate-600 mb-3" />
              <p className="text-slate-300 font-medium">No agents registered</p>
              <p className="text-sm text-slate-500 mt-1">
                Add agents to your <code className="text-cyan-400 text-xs">gateway.yaml</code> file:
              </p>
            </div>
            <pre className="text-xs font-mono text-slate-400 bg-slate-900 rounded p-3 overflow-x-auto">
{`agents:
  - name: researcher
    url: http://localhost:8001
    skills: [research, summarize]
  - name: writer
    url: http://localhost:8002
    skills: [write, edit]`}
            </pre>
          </div>
        )}

        {/* Auto-refresh notice */}
        <p className="text-xs text-slate-600">
          Status refreshes automatically every 10 seconds.
        </p>
      </div>
    </PageShell>
  );
}
