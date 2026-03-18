import type { ExitCondition } from '@/lib/loop-types';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const OPERATORS: ExitCondition['operator'][] = [
  '>=', '<=', '>', '<', '==', '!=', 'contains',
];

interface ExitConditionBuilderProps {
  value: ExitCondition;
  onChange: (condition: ExitCondition) => void;
  error?: string;
}

export function ExitConditionBuilder({ value, onChange, error }: ExitConditionBuilderProps) {
  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-[1fr_100px_100px] gap-2">
        {/* JSONPath */}
        <div>
          <label className="text-[11px] text-slate-400 mb-1 block">JSONPath</label>
          <Input
            value={value.field}
            onChange={(e) => onChange({ ...value, field: e.target.value })}
            placeholder="$.score"
            className="h-8 bg-slate-800 border-slate-600 font-mono text-sm"
          />
        </div>

        {/* Operator */}
        <div>
          <label className="text-[11px] text-slate-400 mb-1 block">Operator</label>
          <Select
            value={value.operator}
            onValueChange={(op) =>
              onChange({ ...value, operator: op as ExitCondition['operator'] })
            }
          >
            <SelectTrigger className="h-8 bg-slate-800 border-slate-600">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {OPERATORS.map((op) => (
                <SelectItem key={op} value={op}>
                  {op}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Value */}
        <div>
          <label className="text-[11px] text-slate-400 mb-1 block">Value</label>
          <Input
            value={value.value}
            onChange={(e) => onChange({ ...value, value: e.target.value })}
            placeholder="0.9"
            className="h-8 bg-slate-800 border-slate-600 font-mono text-sm"
          />
        </div>
      </div>
      {error && <p className="text-[11px] text-red-400">{error}</p>}
    </div>
  );
}
