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
          message={error instanceof Error ? error.message : String(error)}
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
            data-testid="gateway-refresh-btn"
          >
            <RefreshCw size={14} className={isFetching ? 'animate-spin mr-1.5' : 'mr-1.5'} />
            Refresh
          </Button>
        }
      />

      <div className="mt-6 flex flex-col gap-6 max-w-4xl">
        {/* Status + Action */}
        {isOnline ? (
          <div data-testid="gateway-status-online" className="rounded-lg border p-6 bg-green-900/20 border-green-700/30">
            <div className="flex items-center gap-4">
              <div className="w-4 h-4 rounded-full bg-green-400 shadow-lg shadow-green-400/50" />
              <div>
                <h2 className="text-lg font-semibold text-[#f0f0f0]">Gateway Online</h2>
                {data?.message && (
                  <p className="text-sm text-[#80808a] mt-0.5">{data.message}</p>
                )}
              </div>
            </div>
            {agents.length > 0 && (
              <p className="text-sm text-[#80808a] mt-3">
                {agents.length} registered agent{agents.length > 1 ? 's' : ''}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Status banner with Start button */}
            <div data-testid="gateway-status-offline" className="rounded-lg border p-6 bg-[#1a1a1d]/50 border-[#252528]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-4 h-4 rounded-full bg-[#4a4a52]" />
                  <h2 className="text-lg font-semibold text-[#f0f0f0]">Gateway Offline</h2>
                </div>
                <Button
                  size="sm"
                  onClick={() => startMut.mutate()}
                  disabled={startMut.isPending}
                  data-testid="gateway-start-btn"
                >
                  <Play className="w-3.5 h-3.5 mr-1.5" />
                  Start Gateway
                </Button>
              </div>
            </div>

            {/* Getting Started — 3 steps */}
            <div className="rounded-lg border border-[#252528] bg-[#1a1a1d]/50 p-6">
              <h3 className="text-sm font-semibold text-[#f0f0f0] mb-1">What is the A2A Gateway?</h3>
              <p className="text-sm text-[#80808a] mb-5">
                The gateway connects multiple AI agents into a single workflow — agents communicate
                through it, sharing tasks and results.
              </p>

              <div className="space-y-4">
                {/* Step 1 */}
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-amber-500/20 text-amber-400 text-xs font-bold flex items-center justify-center">
                    1
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[#80808a]">Create gateway.yaml</p>
                    <pre className="mt-2 text-xs font-mono text-[#80808a] bg-[#131315] rounded p-3 overflow-x-auto">
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
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-amber-500/20 text-amber-400 text-xs font-bold flex items-center justify-center">
                    2
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[#80808a]">Start the gateway</p>
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
                      <span className="text-xs text-[#4a4a52]">or</span>
                      <code className="text-xs font-mono text-cyan-400 bg-[#131315] rounded px-2.5 py-1.5">
                        binex gateway
                      </code>
                    </div>
                  </div>
                </div>

                {/* Step 3 */}
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-amber-500/20 text-amber-400 text-xs font-bold flex items-center justify-center">
                    3
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[#80808a]">
                      Agents register automatically
                    </p>
                    <p className="text-xs text-[#4a4a52] mt-1">
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
          <div data-testid="gateway-agents-table" className="border border-[#252528] rounded-lg bg-[#1a1a1d]/50 overflow-hidden">
            <div className="px-4 py-3 border-b border-[#252528]">
              <h3 className="text-sm font-medium text-[#80808a]">
                Registered Agents
              </h3>
            </div>
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-[#252528]">
                  <th className="text-left px-4 py-3 font-medium text-[#80808a]">
                    Name
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[#80808a]">
                    URL
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[#80808a]">
                    Status
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[#80808a]">
                    Skills
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#252528]/50">
                {agents.map((agent) => (
                  <tr
                    key={agent.name}
                    data-testid={`gateway-agent-row-${agent.name}`}
                    className="hover:bg-[#1a1a1d]/30 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-[#f0f0f0]">
                      {agent.name}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-[#80808a]">
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
                        <span className="text-[#4a4a52] text-xs">none</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {agent.skills.map((skill) => (
                            <span
                              key={skill}
                              className="text-xs bg-[#131315] text-[#80808a] px-1.5 py-0.5 rounded"
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
          <div className="border border-[#252528] rounded-lg bg-[#1a1a1d]/50 p-6">
            <div className="text-center mb-4">
              <Radio size={36} className="mx-auto text-[#4a4a52] mb-3" />
              <p className="text-[#80808a] font-medium">No agents registered</p>
              <p className="text-sm text-[#4a4a52] mt-1">
                Add agents to your <code className="text-cyan-400 text-xs">gateway.yaml</code> file:
              </p>
            </div>
            <pre className="text-xs font-mono text-[#80808a] bg-[#131315] rounded p-3 overflow-x-auto">
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
        <p className="text-xs text-[#4a4a52]">
          Status refreshes automatically every 10 seconds.
        </p>
      </div>
    </PageShell>
  );
}
