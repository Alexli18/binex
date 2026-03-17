import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { chartColors } from '@/lib/design-tokens';

interface CostTrendPoint {
  date: string;
  cost: number;
  runs: number;
}

interface CostTrendChartProps {
  data: CostTrendPoint[];
}

export function CostTrendChart({ data }: CostTrendChartProps) {
  if (data.length === 0) {
    return (
      <p className="text-slate-500 text-sm text-center py-12">
        No cost data for this period
      </p>
    );
  }

  return (
    <div aria-label="Cost trend over time">
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
          <XAxis dataKey="date" stroke={chartColors.axis} fontSize={12} />
          <YAxis stroke={chartColors.axis} fontSize={12} tickFormatter={(v) => `$${v}`} />
          <Tooltip
            contentStyle={{
              backgroundColor: chartColors.tooltipBg,
              border: `1px solid ${chartColors.tooltipBorder}`,
              borderRadius: '8px',
              color: '#e2e8f0',
            }}
            formatter={(value: unknown, name: unknown) => {
              const v = Number(value);
              if (name === 'cost') return [`$${v.toFixed(4)}`, 'Cost'];
              return [v, 'Runs'];
            }}
          />
          <Area
            type="monotone"
            dataKey="cost"
            stroke={chartColors.primary}
            fill={chartColors.primaryFill}
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
