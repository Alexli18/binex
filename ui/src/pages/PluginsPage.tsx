import { Puzzle } from 'lucide-react';
import { usePlugins } from '../hooks/useUtilities';

export default function PluginsPage() {
  const { data, isLoading, error } = usePlugins();

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-slate-800 rounded animate-pulse" />
        <div className="h-64 bg-slate-800 rounded animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">
          Failed to load plugins: {(error as Error).message}
        </p>
      </div>
    );
  }

  const plugins = data?.plugins ?? [];

  return (
    <div className="p-6 flex flex-col gap-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Puzzle size={24} className="text-indigo-400" />
        <h1 className="text-xl font-bold">Plugins & Adapters</h1>
      </div>

      {/* Table */}
      {plugins.length === 0 ? (
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-8 text-center">
          <Puzzle size={40} className="mx-auto text-slate-600 mb-3" />
          <p className="text-slate-400">No plugins found.</p>
          <p className="text-sm text-slate-500 mt-1">
            Install plugins or check your configuration.
          </p>
        </div>
      ) : (
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 overflow-hidden">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left px-4 py-3 font-medium text-slate-400">
                  Name
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-400">
                  Type
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-400">
                  Source
                </th>
                <th className="text-left px-4 py-3 font-medium text-slate-400">
                  Description
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {plugins.map((plugin) => (
                <tr
                  key={plugin.name}
                  className="hover:bg-slate-700/30 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-slate-200">
                    {plugin.name}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded">
                      {plugin.type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {plugin.builtin ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30">
                        Built-in
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
                        External
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-400 max-w-sm truncate">
                    {plugin.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
