import type { LucideIcon } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface KPICardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  subtitle?: string;
  ariaLabel?: string;
  children?: React.ReactNode;
}

export function KPICard({ icon: Icon, label, value, subtitle, ariaLabel, children }: KPICardProps) {
  return (
    <Card className="bg-slate-900 border-slate-700/60" aria-label={ariaLabel}>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-slate-500 text-sm mb-1">
          <Icon className="w-4 h-4" />
          {label}
        </div>
        <p className="text-2xl font-semibold text-slate-100 font-mono">{value}</p>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
        {children}
      </CardContent>
    </Card>
  );
}
