import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpDown, Info } from 'lucide-react';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { RunSummary } from '@/lib/types';

type SortField = 'total_cost' | 'workflow_name' | 'status' | 'started_at';
type SortDir = 'asc' | 'desc';

const STATUS_OPTIONS = ['all', 'completed', 'failed', 'over_budget', 'running', 'cancelled'] as const;

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

interface CostRunsTableProps {
  runs: RunSummary[];
  caoRunIds?: Set<string>;
}

export function CostRunsTable({ runs, caoRunIds }: CostRunsTableProps) {
  const [sortField, setSortField] = useState<SortField>('total_cost');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return runs
      .filter((r) => {
        if (statusFilter !== 'all' && r.status !== statusFilter) return false;
        if (q && !r.run_id.toLowerCase().includes(q) && !r.workflow_name.toLowerCase().includes(q)) return false;
        return true;
      })
      .sort((a, b) => {
        let cmp = 0;
        switch (sortField) {
          case 'total_cost':
            cmp = a.total_cost - b.total_cost;
            break;
          case 'workflow_name':
            cmp = a.workflow_name.localeCompare(b.workflow_name);
            break;
          case 'status':
            cmp = a.status.localeCompare(b.status);
            break;
          case 'started_at':
            cmp = new Date(a.started_at).getTime() - new Date(b.started_at).getTime();
            break;
        }
        return sortDir === 'asc' ? cmp : -cmp;
      });
  }, [runs, sortField, sortDir, statusFilter, search]);

  const SortHeader = ({ field, label, className }: { field: SortField; label: string; className?: string }) => (
    <th
      className={cn('px-4 py-2.5 font-medium text-[#80808a] cursor-pointer select-none', className)}
      onClick={() => toggleSort(field)}
      aria-sort={sortField === field ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown size={12} className={sortField === field ? 'text-amber-400' : 'text-[#4a4a52]'} />
      </span>
    </th>
  );

  return (
    <div className="bg-[#131315] rounded-card border border-[#252528] overflow-hidden">
      {/* Filters */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[#252528]">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[160px]" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s} value={s}>
                {s === 'all' ? 'All statuses' : s.charAt(0).toUpperCase() + s.slice(1).replace('_', ' ')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search runs..."
          className="w-56"
          aria-label="Search runs"
        />
        <span className="ml-auto text-xs text-[#4a4a52]">{filtered.length} runs</span>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="p-8 text-center text-sm text-[#4a4a52]">No runs match your filters</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-[#1a1a1d] sticky top-0 z-10">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-[#80808a]">Run ID</th>
                <SortHeader field="workflow_name" label="Workflow" className="text-left" />
                <SortHeader field="status" label="Status" className="text-left" />
                <SortHeader field="total_cost" label="Cost" className="text-right" />
                <th className="text-center px-4 py-2.5 font-medium text-[#80808a] hidden md:table-cell">Nodes</th>
                <SortHeader field="started_at" label="Date" className="text-left" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#252528]">
              {filtered.map((run) => (
                <tr
                  key={run.run_id}
                  className={cn(
                    'hover:bg-[#1a1a1d] transition-colors',
                    run.status === 'over_budget' && 'bg-amber-900/10',
                  )}
                >
                  <td className="px-4 py-2.5">
                    <Link
                      to={`/runs/${run.run_id}`}
                      className="text-amber-400 hover:text-amber-300 hover:underline font-mono text-xs"
                    >
                      {run.run_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-[#f0f0f0] truncate max-w-[200px]">{run.workflow_name}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={run.status} /></td>
                  <td className="px-4 py-2.5 text-right font-mono text-[#80808a]">
                    {caoRunIds?.has(run.run_id) ? (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-flex items-center gap-1 cursor-help">
                              ${(run.total_cost ?? 0).toFixed(4)}
                              <Info size={12} className="text-[#80808a]" />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="left" className="max-w-[220px]">
                            <p className="text-xs">
                              Includes CAO adapter nodes with subscription-based pricing — no per-token cost reported.
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    ) : (
                      <span>${(run.total_cost ?? 0).toFixed(4)}</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-center text-[#80808a] hidden md:table-cell">
                    {run.completed_nodes}/{run.total_nodes}
                  </td>
                  <td className="px-4 py-2.5 text-[#4a4a52] text-xs" title={new Date(run.started_at).toLocaleString()}>
                    {timeAgo(run.started_at)}
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
