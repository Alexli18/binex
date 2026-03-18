import { useState, useMemo } from 'react';
import { RefreshCw } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ExitConditionBuilder } from './ExitConditionBuilder';
import type { ExitCondition, LoopContainerData } from '@/lib/loop-types';
import { evaluateExitCondition } from '@/lib/loop-utils';

interface LoopConfigModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (config: LoopContainerData) => void;
  mode: 'create' | 'edit';
  initialData?: LoopContainerData;
}

const NAME_PATTERN = /^[a-z][a-z0-9_]*$/;

export function LoopConfigModal({
  open,
  onClose,
  onSave,
  mode,
  initialData,
}: LoopConfigModalProps) {
  const [label, setLabel] = useState(initialData?.label || '');
  const [maxIterations, setMaxIterations] = useState(initialData?.maxIterations || 5);
  const [exitCondition, setExitCondition] = useState<ExitCondition>(
    initialData?.exitCondition || { jsonpath: '', operator: '>=', value: '' },
  );
  const [testJson, setTestJson] = useState('');
  const [testResult, setTestResult] = useState<{
    pass: boolean;
    expression: string;
    details: string;
  } | null>(null);

  const nameError = useMemo(() => {
    if (!label.trim()) return 'Name is required';
    if (!NAME_PATTERN.test(label)) return 'Must be snake_case (e.g. my_loop)';
    return null;
  }, [label]);

  const conditionError = useMemo(() => {
    if (!exitCondition.jsonpath.trim()) return 'JSONPath is required';
    if (!exitCondition.jsonpath.startsWith('$.')) return 'Must start with $.';
    if (!exitCondition.value.trim()) return 'Value is required';
    return null;
  }, [exitCondition]);

  const isValid = !nameError && !conditionError && maxIterations >= 1 && maxIterations <= 100;

  const handleSave = () => {
    if (!isValid) return;
    onSave({
      label,
      exitCondition,
      maxIterations,
    });
  };

  const handleCancel = () => {
    onClose();
  };

  const handleTest = () => {
    if (!testJson.trim()) return;
    try {
      const parsed = JSON.parse(testJson);
      const result = evaluateExitCondition(exitCondition, parsed);
      setTestResult(result);
    } catch {
      setTestResult({
        pass: false,
        expression: 'parse error',
        details: 'Invalid JSON',
      });
    }
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      if (mode === 'edit') onClose();
      // In create mode, closing without saving deletes the loop
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px] bg-slate-900 border-slate-700">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-teal-300">
            <RefreshCw size={18} />
            {mode === 'create' ? 'Create Loop' : 'Configure Loop'}
          </DialogTitle>
          <DialogDescription className="text-slate-500">
            Set exit condition and iteration limits for this loop container.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Loop Name */}
          <div>
            <label className="text-xs text-slate-400 block mb-1 font-medium">
              Loop Name
            </label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="refinement_loop"
              className="h-9 bg-slate-800 border-slate-600 font-mono"
            />
            {nameError && label.trim() && (
              <p className="text-[11px] text-red-400 mt-1">{nameError}</p>
            )}
          </div>

          {/* Exit Condition */}
          <div>
            <label className="text-xs text-slate-400 block mb-1.5 font-medium">
              Exit Condition
            </label>
            <ExitConditionBuilder
              value={exitCondition}
              onChange={setExitCondition}
              error={conditionError && exitCondition.jsonpath.trim() ? conditionError : undefined}
            />
          </div>

          {/* Max Iterations */}
          <div>
            <label className="text-xs text-slate-400 block mb-1 font-medium">
              Max Iterations
            </label>
            <Input
              type="number"
              min={1}
              max={100}
              value={maxIterations}
              onChange={(e) => setMaxIterations(parseInt(e.target.value) || 5)}
              className="h-9 bg-slate-800 border-slate-600"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Hard limit. Loop stops regardless of condition.
            </p>
          </div>

          {/* Test Condition */}
          <div>
            <label className="text-xs text-slate-400 block mb-1 font-medium">
              Test Condition (optional)
            </label>
            <div className="flex gap-2">
              <Input
                value={testJson}
                onChange={(e) => {
                  setTestJson(e.target.value);
                  setTestResult(null);
                }}
                placeholder='{"score": 0.74}'
                className="h-8 flex-1 bg-slate-800 border-slate-600 font-mono text-xs"
              />
              <Button
                size="sm"
                variant="outline"
                onClick={handleTest}
                disabled={!testJson.trim() || !!conditionError}
                className="h-8 text-xs border-slate-600"
              >
                Test
              </Button>
            </div>
            {testResult && (
              <div
                className={`mt-1.5 px-3 py-2 rounded-md text-xs font-mono ${
                  testResult.pass
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
                }`}
              >
                {testResult.expression} → {testResult.pass ? '\u2713' : '\u2717'} ({testResult.details})
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={handleCancel} className="text-slate-400">
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={!isValid}
            className="bg-teal-600 hover:bg-teal-500 text-white"
          >
            {mode === 'create' ? 'Create Loop' : 'Save Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
