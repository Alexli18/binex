import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { chartColors } from '@/lib/design-tokens';

interface BreakdownItem {
  name: string;
  cost: number;
}

interface CostBreakdownChartProps {
  title: string;
  data: BreakdownItem[];
  color?: string;
  emptyMessage?: string;
}

export function CostBreakdownChart({
  title,
  data,
  color = chartColors.primary,
  emptyMessage = 'No data',
}: CostBreakdownChartProps) {
  const chartHeight = Math.max(200, data.length * 40);

  return (
    <div className="bg-slate-900 rounded-card border border-slate-700/60 p-4">
      <h2 className="text-sm font-semibold text-slate-100 mb-4">{title}</h2>
      {data.length === 0 ? (
        <p className="text-slate-500 text-sm text-center py-12">{emptyMessage}</p>
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
            <XAxis type="number" stroke={chartColors.axis} fontSize={12} tickFormatter={(v) => `$${v}`} />
            <YAxis type="category" dataKey="name" stroke={chartColors.axis} fontSize={12} width={120} />
            <Tooltip
              contentStyle={{
                backgroundColor: chartColors.tooltipBg,
                border: `1px solid ${chartColors.tooltipBorder}`,
                borderRadius: '8px',
                color: '#e2e8f0',
              }}
              formatter={(value: unknown) => [`$${Number(value).toFixed(6)}`, 'Cost']}
            />
            <Bar dataKey="cost" fill={color} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
