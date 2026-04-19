import { useState, useMemo } from 'react';
import { Wrench, Plus, Search } from 'lucide-react';
import { useBuiltinTools, type BuiltinTool } from '@/hooks/useBuiltinTools';
import { useWorkflowEditorContext } from './WorkflowEditorContext';
import { Input } from '@/components/ui/input';

interface ToolPickerPopoverProps {
  selectedTools: string[];
  onToggleTool: (uri: string) => void;
}

const CAT_ORDER = ['data', 'web', 'files', 'system'] as const;
const CAT_LABELS: Record<string, string> = { data: 'Data', web: 'Web', files: 'Files', system: 'System' };

export function ToolPickerPopover({ selectedTools, onToggleTool }: ToolPickerPopoverProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [customUri, setCustomUri] = useState('');
  const { data: builtins } = useBuiltinTools();
  const { mcpServerNames } = useWorkflowEditorContext();

  const selectedSet = useMemo(() => new Set(selectedTools), [selectedTools]);

  const filteredBuiltins = useMemo(() => {
    if (!builtins) return [];
    if (!search) return builtins;
    const q = search.toLowerCase();
    return builtins.filter(
      (t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q),
    );
  }, [builtins, search]);

  const groupedBuiltins = useMemo(() => {
    const groups: Record<string, BuiltinTool[]> = {};
    for (const t of filteredBuiltins) {
      (groups[t.category] ??= []).push(t);
    }
    return groups;
  }, [filteredBuiltins]);

  const filteredMcp = useMemo(() => {
    if (!search) return mcpServerNames;
    const q = search.toLowerCase();
    return mcpServerNames.filter((n) => n.toLowerCase().includes(q));
  }, [mcpServerNames, search]);

  if (!open) {
    return (
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        className="flex items-center gap-1 text-[10px] text-amber-400 hover:text-amber-300 transition-colors"
      >
        <Plus size={10} />
        Add Tool
      </button>
    );
  }

  return (
    <div
      className="absolute left-0 right-0 top-full mt-1 z-50 bg-[#1a1a1d] border border-[#333338] rounded-lg shadow-xl shadow-black/40 max-h-[320px] overflow-y-auto"
      onClick={(e) => e.stopPropagation()}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-2.5 py-1.5 border-b border-[#252528]/50">
        <span className="text-[11px] font-semibold text-[#80808a] flex items-center gap-1">
          <Wrench size={11} /> Add Tools
        </span>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-[10px] text-[#4a4a52] hover:text-[#80808a]"
        >
          Done
        </button>
      </div>

      {/* Search */}
      <div className="px-2.5 py-1.5">
        <div className="relative">
          <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#4a4a52]" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tools..."
            className="h-6 pl-6 text-[11px] bg-[#252528] border-[#333338]"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      </div>

      {/* Built-in tools */}
      {CAT_ORDER.map((cat) => {
        const tools = groupedBuiltins[cat];
        if (!tools?.length) return null;
        return (
          <div key={cat} className="px-2.5 pb-1">
            <div className="text-[9px] font-bold uppercase tracking-wider text-[#4a4a52] mb-0.5">
              {CAT_LABELS[cat]}
            </div>
            {tools.map((t) => {
              const uri = `builtin://${t.name}`;
              const checked = selectedSet.has(uri);
              return (
                <label
                  key={t.name}
                  className="flex items-start gap-1.5 py-0.5 cursor-pointer hover:bg-[#252528]/50 rounded px-1 -mx-1"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleTool(uri)}
                    className="mt-0.5 accent-amber-500"
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div className="min-w-0">
                    <div className="text-[11px] text-[#f0f0f0]">{t.name}</div>
                    <div className="text-[9px] text-[#4a4a52] truncate">{t.description}</div>
                  </div>
                </label>
              );
            })}
          </div>
        );
      })}

      {/* MCP servers */}
      {filteredMcp.length > 0 && (
        <div className="px-2.5 pb-1 border-t border-[#252528]/50 pt-1">
          <div className="text-[9px] font-bold uppercase tracking-wider text-[#4a4a52] mb-0.5">
            MCP Servers
          </div>
          {filteredMcp.map((name) => {
            const uri = `mcp://${name}`;
            const checked = selectedSet.has(uri);
            return (
              <label
                key={name}
                className="flex items-center gap-1.5 py-0.5 cursor-pointer hover:bg-[#252528]/50 rounded px-1 -mx-1"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => onToggleTool(uri)}
                  className="accent-purple-500"
                  onClick={(e) => e.stopPropagation()}
                />
                <span className="text-[11px] text-purple-300">{name}</span>
              </label>
            );
          })}
        </div>
      )}

      {/* Custom python:// */}
      <div className="px-2.5 py-1.5 border-t border-[#252528]/50">
        <div className="text-[9px] font-bold uppercase tracking-wider text-[#4a4a52] mb-0.5">
          Custom
        </div>
        <div className="flex gap-1">
          <Input
            value={customUri}
            onChange={(e) => setCustomUri(e.target.value)}
            placeholder="python://module.func"
            className="h-5 text-[10px] bg-[#252528] border-[#333338] font-mono flex-1"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && customUri.trim()) {
                const uri = customUri.trim().startsWith('python://') ? customUri.trim() : `python://${customUri.trim()}`;
                onToggleTool(uri);
                setCustomUri('');
              }
            }}
          />
          <button
            type="button"
            onClick={() => {
              if (customUri.trim()) {
                const uri = customUri.trim().startsWith('python://') ? customUri.trim() : `python://${customUri.trim()}`;
                onToggleTool(uri);
                setCustomUri('');
              }
            }}
            className="text-[10px] text-amber-400 hover:text-amber-300 px-1"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
