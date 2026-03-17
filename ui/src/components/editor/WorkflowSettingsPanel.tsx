import { useState } from 'react';
import { X, Plus, Server, Clock, Trash2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

export interface McpServerConfig {
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
}

interface WorkflowSettingsPanelProps {
  open: boolean;
  onClose: () => void;
  mcpServers: Record<string, McpServerConfig>;
  onMcpServersChange: (servers: Record<string, McpServerConfig>) => void;
  schedule: string;
  onScheduleChange: (cron: string) => void;
}

export function WorkflowSettingsPanel({
  open,
  onClose,
  mcpServers,
  onMcpServersChange,
  schedule,
  onScheduleChange,
}: WorkflowSettingsPanelProps) {
  const [addingServer, setAddingServer] = useState(false);
  const [newName, setNewName] = useState('');
  const [newTransport, setNewTransport] = useState<'stdio' | 'http'>('stdio');
  const [newCommand, setNewCommand] = useState('');
  const [newArgs, setNewArgs] = useState('');
  const [newUrl, setNewUrl] = useState('');

  if (!open) return null;

  const serverEntries = Object.entries(mcpServers);

  const handleAdd = () => {
    if (!newName.trim()) return;
    const config: McpServerConfig =
      newTransport === 'stdio'
        ? { command: newCommand, args: newArgs.split(/\s+/).filter(Boolean) }
        : { url: newUrl };
    onMcpServersChange({ ...mcpServers, [newName.trim()]: config });
    setNewName('');
    setNewCommand('');
    setNewArgs('');
    setNewUrl('');
    setAddingServer(false);
  };

  const handleRemove = (name: string) => {
    const next = { ...mcpServers };
    delete next[name];
    onMcpServersChange(next);
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 bottom-0 w-80 bg-slate-900 border-l border-slate-700 z-50 shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
          <span className="text-sm font-semibold text-slate-200">Workflow Settings</span>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X size={16} />
          </button>
        </div>

        {/* MCP Servers */}
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <Server size={12} /> MCP Servers
            </h3>
            <button
              onClick={() => setAddingServer(true)}
              className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-0.5"
            >
              <Plus size={10} /> Add
            </button>
          </div>

          {serverEntries.length === 0 && !addingServer && (
            <p className="text-[11px] text-slate-500">No MCP servers configured</p>
          )}

          {serverEntries.map(([name, cfg]) => (
            <div key={name} className="bg-slate-800 rounded-md p-2.5 border border-slate-700/50">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-medium text-purple-300">{name}</span>
                <div className="flex items-center gap-1.5">
                  <span className={cn(
                    'text-[9px] px-1.5 py-0.5 rounded font-medium',
                    cfg.url ? 'bg-blue-500/15 text-blue-400' : 'bg-emerald-500/15 text-emerald-400',
                  )}>
                    {cfg.url ? 'HTTP' : 'stdio'}
                  </span>
                  <button onClick={() => handleRemove(name)} className="text-red-500 hover:text-red-400">
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
              {cfg.url ? (
                <div className="text-[10px] text-slate-400 font-mono truncate">{cfg.url}</div>
              ) : (
                <div className="text-[10px] text-slate-400 font-mono truncate">
                  {cfg.command} {cfg.args?.join(' ')}
                </div>
              )}
            </div>
          ))}

          {addingServer && (
            <div className="bg-slate-800 rounded-md p-2.5 border border-blue-500/30 space-y-2">
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Server name"
                className="h-6 text-[11px] bg-slate-700 border-slate-600"
              />
              <div className="flex rounded overflow-hidden border border-slate-600 text-[10px]">
                <button
                  type="button"
                  onClick={() => setNewTransport('stdio')}
                  className={cn('flex-1 py-1', newTransport === 'stdio' ? 'bg-blue-600 text-white' : 'text-slate-400')}
                >
                  stdio
                </button>
                <button
                  type="button"
                  onClick={() => setNewTransport('http')}
                  className={cn('flex-1 py-1', newTransport === 'http' ? 'bg-blue-600 text-white' : 'text-slate-400')}
                >
                  HTTP
                </button>
              </div>
              {newTransport === 'stdio' ? (
                <>
                  <Input
                    value={newCommand}
                    onChange={(e) => setNewCommand(e.target.value)}
                    placeholder="Command (e.g. npx)"
                    className="h-6 text-[11px] bg-slate-700 border-slate-600 font-mono"
                  />
                  <Input
                    value={newArgs}
                    onChange={(e) => setNewArgs(e.target.value)}
                    placeholder="Args (space-separated)"
                    className="h-6 text-[11px] bg-slate-700 border-slate-600 font-mono"
                  />
                </>
              ) : (
                <Input
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="http://localhost:3000/mcp"
                  className="h-6 text-[11px] bg-slate-700 border-slate-600 font-mono"
                />
              )}
              <div className="flex gap-1.5">
                <button
                  onClick={handleAdd}
                  className="text-[10px] px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-500"
                >
                  Add Server
                </button>
                <button
                  onClick={() => setAddingServer(false)}
                  className="text-[10px] px-2 py-1 rounded text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Schedule */}
        <div className="p-4 border-t border-slate-700/50 space-y-2">
          <h3 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <Clock size={12} /> Schedule
          </h3>
          <Input
            value={schedule}
            onChange={(e) => onScheduleChange(e.target.value)}
            placeholder="*/5 * * * *  (cron expression)"
            className="h-7 text-[11px] bg-slate-800 border-slate-600 font-mono"
          />
          <p className="text-[10px] text-slate-500">
            5-field cron expression. Leave empty for manual-only runs.
          </p>
        </div>
      </div>
    </>
  );
}
