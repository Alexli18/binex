import { Radio, RefreshCw, Terminal } from 'lucide-react';
import { useGateway } from '../hooks/useUtilities';

export default function GatewayPage() {
  const { data, isLoading, error, refetch, isFetching } = useGateway();

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="h-32 bg-slate-800 rounded-lg animate-pulse" />
        <div className="h-48 bg-slate-800 rounded-lg animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">
          Failed to load gateway status: {(error as Error).message}
        </p>
      </div>
    );
  }

  const isOnline = data?.status === 'online';
  const agents = data?.agents ?? [];

  return (
    <div className="p-6 flex flex-col gap-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Radio size={24} className="text-cyan-400" />
          <h1 className="text-xl font-bold">A2A Gateway</h1>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded border border-slate-600 text-slate-300 hover:bg-slate-700 disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Status card */}
      <div
        className={`rounded-lg border p-6 ${
          isOnline
            ? 'bg-green-900/20 border-green-700/30'
            : 'bg-red-900/20 border-red-700/30'
        }`}
      >
        <div className="flex items-center gap-4">
          <div
            className={`w-4 h-4 rounded-full ${
              isOnline ? 'bg-green-400 shadow-lg shadow-green-400/50' : 'bg-red-400 shadow-lg shadow-red-400/50'
            }`}
          />
          <div>
            <h2 className="text-lg font-semibold text-slate-200">
              {isOnline ? 'Gateway Online' : 'Gateway Offline'}
            </h2>
            {data?.message && (
              <p className="text-sm text-slate-400 mt-0.5">{data.message}</p>
            )}
          </div>
        </div>
        {isOnline && agents.length > 0 && (
          <p className="text-sm text-slate-400 mt-3">
            {agents.length} registered agent{agents.length > 1 ? 's' : ''}
          </p>
        )}
      </div>

      {/* Offline instructions */}
      {!isOnline && (
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-5">
          <div className="flex items-start gap-3">
            <Terminal size={20} className="text-slate-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-slate-300">
                The gateway is not running. Start it with:
              </p>
              <code className="block mt-2 text-sm font-mono text-cyan-400 bg-slate-900 rounded px-3 py-2">
                binex gateway
              </code>
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
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${
                        agent.status === 'healthy' || agent.status === 'online'
                          ? 'bg-green-500/20 text-green-400'
                          : agent.status === 'unhealthy' || agent.status === 'offline'
                            ? 'bg-red-500/20 text-red-400'
                            : 'bg-slate-600/20 text-slate-400'
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          agent.status === 'healthy' || agent.status === 'online'
                            ? 'bg-green-400'
                            : agent.status === 'unhealthy' || agent.status === 'offline'
                              ? 'bg-red-400'
                              : 'bg-slate-400'
                        }`}
                      />
                      {agent.status}
                    </span>
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

      {/* Online but no agents */}
      {isOnline && agents.length === 0 && (
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-8 text-center">
          <Radio size={40} className="mx-auto text-slate-600 mb-3" />
          <p className="text-slate-400">
            No agents registered with the gateway.
          </p>
          <p className="text-sm text-slate-500 mt-1">
            Configure agents in your gateway.yaml file.
          </p>
        </div>
      )}

      {/* Auto-refresh notice */}
      <p className="text-xs text-slate-600">
        Status refreshes automatically every 10 seconds.
      </p>
    </div>
  );
}
