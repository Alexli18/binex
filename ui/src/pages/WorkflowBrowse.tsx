import { useNavigate } from 'react-router-dom';
import { FileCode, Plus, Play, Pencil } from 'lucide-react';
import { useWorkflows } from '../hooks/useWorkflows';

export default function WorkflowBrowse() {
  const navigate = useNavigate();
  const { data: workflows, isLoading, error } = useWorkflows();

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
          Failed to load workflows: {(error as Error).message}
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileCode size={24} className="text-blue-400" />
          <h1 className="text-xl font-bold">Workflows</h1>
        </div>
        <button
          onClick={() => navigate('/scaffold')}
          className="flex items-center gap-2 px-4 py-1.5 text-sm font-medium rounded bg-blue-600 text-white hover:bg-blue-700"
        >
          <Plus size={16} />
          Create New
        </button>
      </div>

      {/* Table */}
      {!workflows || workflows.length === 0 ? (
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-8 text-center">
          <FileCode size={40} className="mx-auto text-slate-600 mb-3" />
          <p className="text-slate-400">No workflow files found.</p>
          <p className="text-sm text-slate-500 mt-1">
            Create one with the Scaffold wizard or place YAML files in your project.
          </p>
        </div>
      ) : (
        <div className="border border-slate-700 rounded-lg bg-slate-800/50 overflow-hidden">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left px-4 py-3 font-medium text-slate-400">
                  File Path
                </th>
                <th className="text-right px-4 py-3 font-medium text-slate-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {workflows.map((path) => (
                <tr
                  key={path}
                  className="hover:bg-slate-700/30 cursor-pointer transition-colors"
                  onClick={() =>
                    navigate(`/editor?file=${encodeURIComponent(path)}`)
                  }
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileCode size={16} className="text-slate-500 shrink-0" />
                      <span className="font-mono text-xs text-slate-200 truncate">
                        {path}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(
                            `/editor?file=${encodeURIComponent(path)}`,
                          );
                        }}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-slate-600 text-slate-300 hover:bg-slate-700 transition-colors"
                        title="Edit workflow"
                      >
                        <Pencil size={12} />
                        Edit
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(
                            `/editor?file=${encodeURIComponent(path)}`,
                          );
                        }}
                        className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-slate-600 text-slate-300 hover:bg-slate-700 transition-colors"
                        title="Validate workflow"
                      >
                        <Play size={12} />
                        Validate
                      </button>
                    </div>
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
