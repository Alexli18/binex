import { Button } from '@/components/ui/button';
import { typography } from '@/lib/design-tokens';
import type { SemanticEstimate } from '@/hooks/useComparison';

interface SemanticConfirmProps {
  open: boolean;
  estimate: SemanticEstimate | null;
  loading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function formatCost(cost: number | null): string {
  // An unpriced model must not read as free.
  if (cost === null || cost === undefined) return 'unknown (unpriced model)';
  return `~$${cost.toFixed(4)}`;
}

/**
 * Cost confirmation for semantic analysis.
 *
 * Semantic diff/bisect spends the user's tokens, so the CLI prints an estimate
 * and asks before any call. The browser must not be a way around that: nothing
 * runs until the estimate has been shown and explicitly accepted here.
 */
export function SemanticConfirm({
  open,
  estimate,
  loading,
  onConfirm,
  onCancel,
}: SemanticConfirmProps) {
  if (!open) return null;

  const nothingToDo = !loading && estimate !== null && estimate.calls === 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Confirm semantic analysis"
      data-testid="semantic-confirm"
    >
      <div className="w-full max-w-md rounded-card border border-[#252528] bg-[#131316] p-5">
        <h2 className={`${typography.heading} text-sm mb-1`}>Semantic analysis</h2>
        <p className={`${typography.body} text-xs mb-4`}>
          A model is asked whether each changed text node changed meaningfully.
          This spends your tokens.
        </p>

        {loading && (
          <p className={`${typography.body} text-xs`}>Estimating cost…</p>
        )}

        {!loading && nothingToDo && (
          <p className={`${typography.body} text-xs`}>
            Nothing to analyze — no text node differs between these runs.
          </p>
        )}

        {!loading && estimate !== null && !nothingToDo && (
          <dl className="grid grid-cols-2 gap-y-1 text-xs font-mono mb-4">
            <dt className={typography.body}>Judge calls</dt>
            <dd className="text-[#f0f0f0] text-right">{estimate.calls}</dd>
            <dt className={typography.body}>Model</dt>
            <dd className="text-[#f0f0f0] text-right">{estimate.model}</dd>
            <dt className={typography.body}>Tokens</dt>
            <dd className="text-[#f0f0f0] text-right">
              ~{estimate.total_tokens}
            </dd>
            <dt className={typography.body}>Estimated cost</dt>
            <dd className="text-amber-400 text-right">{formatCost(estimate.cost)}</dd>
          </dl>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          {!loading && !nothingToDo && estimate !== null && (
            <Button size="sm" onClick={onConfirm} data-testid="semantic-run-btn">
              Run analysis
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
