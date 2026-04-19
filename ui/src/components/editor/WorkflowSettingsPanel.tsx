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
      <div className="fixed inset-0 bg-black/60 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 bottom-0 w-80 bg-[#131315] border-l border-[#252528] z-50 shadow-xl overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#252528]/50">
          <span className="text-sm font-semibold text-[#f0f0f0]">Workflow Settings</span>
          <button onClick={onClose} className="text-[#4a4a52] hover:text-[#80808a]">
            <X size={16} />
          </button>
        </div>

        {/* MCP Servers */}
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-[#80808a] flex items-center gap-1.5">
              <Server size={12} /> MCP Servers
            </h3>
            <button
              onClick={() => setAddingServer(true)}
              className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-0.5"
            >
              <Plus size={10} /> Add
            </button>
          </div>

          {serverEntries.length === 0 && !addingServer && (
            <p className="text-[11px] text-[#4a4a52]">No MCP servers configured</p>
          )}

          {serverEntries.map(([name, cfg]) => (
            <div key={name} className="bg-[#1a1a1d] rounded-md p-2.5 border border-[#252528]/50">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-medium text-purple-300">{name}</span>
                <div className="flex items-center gap-1.5">
                  <span className={cn(
                    'text-[9px] px-1.5 py-0.5 rounded font-medium',
                    cfg.url ? 'bg-amber-500/15 text-amber-400' : 'bg-emerald-500/15 text-emerald-400',
                  )}>
                    {cfg.url ? 'HTTP' : 'stdio'}
                  </span>
                  <button onClick={() => handleRemove(name)} className="text-red-500 hover:text-red-400">
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
              {cfg.url ? (
                <div className="text-[10px] text-[#80808a] font-mono truncate">{cfg.url}</div>
              ) : (
                <div className="text-[10px] text-[#80808a] font-mono truncate">
                  {cfg.command} {cfg.args?.join(' ')}
                </div>
              )}
            </div>
          ))}

          {addingServer && (
            <div className="bg-[#1a1a1d] rounded-md p-2.5 border border-amber-500/30 space-y-2">
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Server name"
                className="h-6 text-[11px] bg-[#252528] border-[#333338]"
              />
              <div className="flex rounded overflow-hidden border border-[#333338] text-[10px]">
                <button
                  type="button"
                  onClick={() => setNewTransport('stdio')}
                  className={cn('flex-1 py-1', newTransport === 'stdio' ? 'bg-amber-500 text-black' : 'text-[#80808a]')}
                >
                  stdio
                </button>
                <button
                  type="button"
                  onClick={() => setNewTransport('http')}
                  className={cn('flex-1 py-1', newTransport === 'http' ? 'bg-amber-500 text-black' : 'text-[#80808a]')}
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
                    className="h-6 text-[11px] bg-[#252528] border-[#333338] font-mono"
                  />
                  <Input
                    value={newArgs}
                    onChange={(e) => setNewArgs(e.target.value)}
                    placeholder="Args (space-separated)"
                    className="h-6 text-[11px] bg-[#252528] border-[#333338] font-mono"
                  />
                </>
              ) : (
                <Input
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="http://localhost:3000/mcp"
                  className="h-6 text-[11px] bg-[#252528] border-[#333338] font-mono"
                />
              )}
              <div className="flex gap-1.5">
                <button
                  onClick={handleAdd}
                  className="text-[10px] px-2 py-1 rounded bg-amber-500 text-black hover:bg-amber-400"
                >
                  Add Server
                </button>
                <button
                  onClick={() => setAddingServer(false)}
                  className="text-[10px] px-2 py-1 rounded text-[#80808a] hover:text-[#f0f0f0]"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Schedule */}
        <div className="p-4 border-t border-[#252528]/50 space-y-2">
          <h3 className="text-xs font-semibold text-[#80808a] flex items-center gap-1.5">
            <Clock size={12} /> Schedule
          </h3>
          <Input
            value={schedule}
            onChange={(e) => onScheduleChange(e.target.value)}
            placeholder="*/5 * * * *  (cron expression)"
            className="h-7 text-[11px] bg-[#1a1a1d] border-[#333338] font-mono"
          />
          <p className="text-[10px] text-[#4a4a52]">
            5-field cron expression. Leave empty for manual-only runs.
          </p>
        </div>
      </div>
    </>
  );
}
