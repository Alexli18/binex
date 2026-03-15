import { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  LayoutDashboard,
  FileCode,
  Pencil,
  Wrench,
  Search,
  DollarSign,
  Download,
  Stethoscope,
  Plug,
  Globe,
  GitCompare,
  Binary,
  Wallet,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ReactNode;
  action: () => void;
  keywords?: string[];
}

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: CommandItem[] = useMemo(() => [
    { id: 'dashboard', label: 'Dashboard', description: 'View all runs', icon: <LayoutDashboard className="w-4 h-4" />, action: () => navigate('/'), keywords: ['home', 'runs'] },
    { id: 'workflows', label: 'Browse Workflows', description: 'View workflow files', icon: <FileCode className="w-4 h-4" />, action: () => navigate('/workflows'), keywords: ['files', 'browse'] },
    { id: 'editor', label: 'Workflow Editor', description: 'Edit workflow YAML', icon: <Pencil className="w-4 h-4" />, action: () => navigate('/editor'), keywords: ['edit', 'yaml', 'visual'] },
    { id: 'scaffold', label: 'Scaffold Workflow', description: 'Create from template or DSL', icon: <Wrench className="w-4 h-4" />, action: () => navigate('/scaffold'), keywords: ['create', 'new', 'template'] },
    { id: 'costs', label: 'Cost Dashboard', description: 'View cost analytics', icon: <DollarSign className="w-4 h-4" />, action: () => navigate('/costs'), keywords: ['money', 'analytics'] },
    { id: 'budget', label: 'Budget', description: 'Budget configuration', icon: <Wallet className="w-4 h-4" />, action: () => navigate('/costs/budget'), keywords: ['limit'] },
    { id: 'diff', label: 'Compare Runs', description: 'Diff two runs side-by-side', icon: <GitCompare className="w-4 h-4" />, action: () => navigate('/diff'), keywords: ['compare', 'difference'] },
    { id: 'bisect', label: 'Bisect Runs', description: 'Find regression point', icon: <Binary className="w-4 h-4" />, action: () => navigate('/bisect'), keywords: ['regression'] },
    { id: 'export', label: 'Export Runs', description: 'Download run data', icon: <Download className="w-4 h-4" />, action: () => navigate('/export'), keywords: ['download', 'csv', 'json'] },
    { id: 'doctor', label: 'System Doctor', description: 'Health checks', icon: <Stethoscope className="w-4 h-4" />, action: () => navigate('/system/doctor'), keywords: ['health', 'check'] },
    { id: 'plugins', label: 'Plugins', description: 'Installed plugins', icon: <Plug className="w-4 h-4" />, action: () => navigate('/system/plugins'), keywords: ['extensions'] },
    { id: 'gateway', label: 'A2A Gateway', description: 'Agent gateway status', icon: <Globe className="w-4 h-4" />, action: () => navigate('/system/gateway'), keywords: ['agents', 'a2a'] },
  ], [navigate]);

  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter((c) =>
      c.label.toLowerCase().includes(q) ||
      c.description?.toLowerCase().includes(q) ||
      c.keywords?.some((k) => k.includes(q))
    );
  }, [commands, query]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const runCommand = (cmd: CommandItem) => {
    onOpenChange(false);
    cmd.action();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      e.preventDefault();
      runCommand(filtered[selectedIndex]);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 gap-0 max-w-lg overflow-hidden">
        <DialogTitle className="sr-only">Command Palette</DialogTitle>
        <DialogDescription className="sr-only">Search and navigate to any page</DialogDescription>
        <div className="flex items-center border-b px-3">
          <Search className="w-4 h-4 text-muted-foreground mr-2 shrink-0" />
          <Input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            className="border-0 focus-visible:ring-0 focus-visible:ring-offset-0 h-11"
          />
        </div>
        <div className="max-h-72 overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">No commands found</p>
          ) : (
            filtered.map((cmd, i) => (
              <button
                key={cmd.id}
                onClick={() => runCommand(cmd)}
                className={cn(
                  'w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors',
                  i === selectedIndex ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/50'
                )}
              >
                <span className="text-muted-foreground">{cmd.icon}</span>
                <div className="flex-1 min-w-0">
                  <span className="font-medium">{cmd.label}</span>
                  {cmd.description && (
                    <span className="ml-2 text-muted-foreground text-xs">{cmd.description}</span>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
