import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DollarSign, TrendingUp, Activity, Shield, Download } from 'lucide-react';
import { useCostDashboard, type DashboardData } from '../hooks/useCostDashboard';
import { useRuns } from '../hooks/useRuns';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { LoadingState } from '@/components/layout/LoadingState';
import { ErrorState } from '@/components/layout/ErrorState';
import { EmptyState } from '@/components/layout/EmptyState';
import { Button } from '@/components/ui/button';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { KPICard } from '@/components/cost/KPICard';
import { CostTrendChart } from '@/components/cost/CostTrendChart';
import { CostBreakdownChart } from '@/components/cost/CostBreakdownChart';
import { CostRunsTable } from '@/components/cost/CostRunsTable';
import { BudgetStatus } from '@/components/cost/BudgetStatus';
import { colors as tokenColors, chartColors } from '@/lib/design-tokens';

const PERIODS = ['24h', '7d', '30d', 'all'] as const;

export default function CostDashboard() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState<string>('7d');
  const costQuery = useCostDashboard(period);
  const { data: runs, isLoading: runsLoading } = useRuns();

  if (costQuery.isLoading && runsLoading) {
    return (
      <PageShell>
        <LoadingState message="Loading cost dashboard..." />
      </PageShell>
    );
  }

  if (costQuery.error) {
    return (
      <PageShell>
        <Breadcrumb items={[{ label: 'Dashboard', href: '/' }, { label: 'Costs' }]} className="mb-4" />
        <ErrorState
          title="Failed to load cost data"
          message={(costQuery.error as Error).message}
          onRetry={() => costQuery.refetch()}
        />
      </PageShell>
    );
  }

  const costData = costQuery.data;

  if (!costData && !runsLoading && (!runs || runs.length === 0)) {
    return (
      <PageShell>
        <Breadcrumb items={[{ label: 'Dashboard', href: '/' }, { label: 'Costs' }]} className="mb-4" />
        <EmptyState
          title="No cost data yet"
          description="Run a workflow to see costs here."
          action={{ label: 'Create Workflow', onClick: () => navigate('/editor') }}
        />
      </PageShell>
    );
  }

  const budgetLimit = (costData as DashboardData & { budget_limit?: number })?.budget_limit;
  const budgetUsed = costData && budgetLimit && budgetLimit > 0
    ? Math.min((costData.total_cost / budgetLimit) * 100, 100)
    : 0;
  const budgetColor = budgetUsed < 50 ? tokenColors.success.bg : budgetUsed < 80 ? tokenColors.warning.bg : tokenColors.danger.bg;

  return (
    <PageShell>
      <Breadcrumb items={[{ label: 'Dashboard', href: '/' }, { label: 'Costs' }]} className="mb-4" />

      <PageHeader
        title="Cost Dashboard"
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/export')}
            >
              <Download className="w-3.5 h-3.5 mr-1.5" />
              Export CSV
            </Button>
            <Select value={period} onValueChange={setPeriod}>
              <SelectTrigger className="w-[100px]" aria-label="Select period">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERIODS.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
      />

      <div className="mt-6 space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KPICard
            icon={DollarSign}
            label="Total Cost"
            value={`$${(costData?.total_cost ?? 0).toFixed(2)}`}
            ariaLabel={`Total cost: $${(costData?.total_cost ?? 0).toFixed(2)} for last ${period}`}
          />
          <KPICard
            icon={TrendingUp}
            label="Avg per Run"
            value={`$${(costData?.avg_per_run ?? 0).toFixed(4)}`}
          />
          <KPICard
            icon={Activity}
            label="Total Runs"
            value={String(costData?.run_count ?? 0)}
          />
          <KPICard
            icon={Shield}
            label="Budget Used"
            value={budgetLimit && budgetLimit > 0 ? `${budgetUsed.toFixed(0)}%` : 'N/A'}
            subtitle={budgetLimit && budgetLimit > 0 ? undefined : 'Not configured'}
          >
            {budgetLimit && budgetLimit > 0 && (
              <div className="mt-2 w-full bg-[#252528] rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${budgetColor} transition-all`}
                  style={{ width: `${budgetUsed}%` }}
                  role="progressbar"
                  aria-valuenow={budgetUsed}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Budget usage"
                />
              </div>
            )}
          </KPICard>
        </div>

        {/* Cost Trend */}
        <div className="bg-[#131315] rounded-card border border-[#252528]/60 p-4">
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-4">Cost Trend</h2>
          {costQuery.isLoading ? (
            <div className="h-[300px] bg-[#1a1a1d] rounded animate-pulse" />
          ) : (
            <CostTrendChart data={costData?.cost_trend ?? []} />
          )}
        </div>

        {/* Breakdown Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <CostBreakdownChart
            title="Cost by Model"
            data={(costData?.cost_by_model ?? []).map((m) => ({ name: m.model, cost: m.cost }))}
            color={chartColors.primary}
            emptyMessage="No model cost data"
          />
          <CostBreakdownChart
            title="Cost by Node"
            data={(costData?.cost_by_node ?? []).map((n) => ({ name: n.node_id, cost: n.cost }))}
            color={chartColors.secondary}
            emptyMessage="No node cost data"
          />
        </div>

        {/* Runs Table */}
        <div>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-3">Runs by Cost</h2>
          {runsLoading ? (
            <LoadingState message="Loading runs..." variant="inline" />
          ) : (
            <CostRunsTable runs={runs ?? []} />
          )}
        </div>

        {/* Budget Configuration */}
        <BudgetStatus budgetLimit={budgetLimit} />
      </div>
    </PageShell>
  );
}
