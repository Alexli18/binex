import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateRun } from '@/hooks/useRuns';
import { useWorkflows } from '@/hooks/useWorkflows';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';

interface NewRunModalProps {
  open: boolean;
  onClose: () => void;
}

export function NewRunModal({ open, onClose }: NewRunModalProps) {
  const navigate = useNavigate();
  const { data: workflows, isLoading: loadingWorkflows } = useWorkflows();
  const createRun = useCreateRun();
  const [selectedWorkflow, setSelectedWorkflow] = useState('');
  const [variablesText, setVariablesText] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setSelectedWorkflow('');
      setVariablesText('');
      setErrorMsg('');
      onClose();
    }
  };

  const handleSubmit = () => {
    if (!selectedWorkflow) {
      setErrorMsg('Please select a workflow');
      return;
    }
    setErrorMsg('');

    const variables: Record<string, string> = {};
    if (variablesText.trim()) {
      for (const line of variablesText.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        const eqIdx = trimmed.indexOf('=');
        if (eqIdx === -1) {
          setErrorMsg(`Invalid variable format: "${trimmed}". Use key=value.`);
          return;
        }
        variables[trimmed.slice(0, eqIdx).trim()] = trimmed.slice(eqIdx + 1).trim();
      }
    }

    createRun.mutate(
      { workflow_path: selectedWorkflow, variables },
      {
        onSuccess: (data) => {
          handleOpenChange(false);
          navigate(`/runs/${data.run_id}`);
        },
        onError: (err) => {
          setErrorMsg((err as Error).message);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>New Run</DialogTitle>
          <DialogDescription>
            Select a workflow and optionally provide variables to start a new run.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <label
              htmlFor="workflow-select"
              className="block text-sm font-medium text-[#80808a] mb-1"
            >
              Workflow
            </label>
            {loadingWorkflows ? (
              <p className="text-sm text-[#4a4a52]">Loading workflows...</p>
            ) : (
              <select
                id="workflow-select"
                value={selectedWorkflow}
                onChange={(e) => setSelectedWorkflow(e.target.value)}
                className="w-full border border-[#333338] rounded-md px-3 py-1.5 text-sm bg-[#252528] text-[#f0f0f0] focus:outline-none focus:border-amber-500"
              >
                <option value="">-- Select a workflow --</option>
                {(workflows ?? []).map((w) => (
                  <option key={w} value={w}>
                    {w}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label
              htmlFor="variables-input"
              className="block text-sm font-medium text-[#80808a] mb-1"
            >
              Variables (key=value, one per line)
            </label>
            <textarea
              id="variables-input"
              value={variablesText}
              onChange={(e) => setVariablesText(e.target.value)}
              placeholder={"topic=AI\nlanguage=en"}
              rows={3}
              className="w-full border border-[#333338] rounded-md px-3 py-1.5 text-sm font-mono bg-[#252528] text-[#f0f0f0] focus:outline-none focus:border-amber-500"
            />
          </div>

          {errorMsg && (
            <p className="text-red-400 text-sm" role="alert">
              {errorMsg}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button onClick={() => handleOpenChange(false)} variant="outline" size="sm">
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={createRun.isPending}
            size="sm"
          >
            {createRun.isPending ? 'Starting...' : 'Start Run'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
