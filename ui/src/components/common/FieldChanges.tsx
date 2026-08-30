import { diffColors, typography } from '@/lib/design-tokens';
import type { FieldChange } from '@/hooks/useComparison';

/** Render a leaf value the way it would read in the artifact. */
function formatValue(value: unknown): string {
  if (typeof value === 'string') return `"${value}"`;
  return JSON.stringify(value) ?? String(value);
}

const kindStyles: Record<FieldChange['kind'], string> = {
  changed: 'text-amber-400',
  added: diffColors.added.text,
  removed: diffColors.removed.text,
};

function Absent() {
  return <span className={typography.muted}>(absent)</span>;
}

function ChangeRow({ change }: { change: FieldChange }) {
  return (
    <div
      data-testid="field-change-row"
      className="flex flex-wrap items-baseline gap-2 px-2 py-1"
    >
      <span className="font-mono text-xs text-[#f0f0f0]">{change.path}</span>
      <span className={`text-[10px] uppercase tracking-wide ${kindStyles[change.kind]}`}>
        {change.kind}
      </span>
      {change.kind === 'added' ? (
        <Absent />
      ) : (
        <span className={`font-mono text-xs ${diffColors.removed.text}`}>
          {formatValue(change.before)}
        </span>
      )}
      <span className={typography.muted}>→</span>
      {change.kind === 'removed' ? (
        <Absent />
      ) : (
        <span className={`font-mono text-xs ${diffColors.added.text}`}>
          {formatValue(change.after)}
        </span>
      )}
    </div>
  );
}

/**
 * Field-level differences between two structured artifact contents.
 *
 * This is what replaces a similarity ratio for structured output: which field
 * moved, and to what. An empty list means the two contents are structurally
 * identical — key order alone is not a change.
 */
export function FieldChanges({ changes }: { changes: FieldChange[] }) {
  if (changes.length === 0) {
    return (
      <p className={`px-2 py-1 text-xs ${typography.body}`}>
        No field changes — the outputs are structurally identical.
      </p>
    );
  }

  return (
    <div className="bg-slate-950 rounded-card p-2 text-xs overflow-x-auto max-h-96 overflow-y-auto border border-slate-700 divide-y divide-slate-800">
      {changes.map((change, i) => (
        <ChangeRow key={`${change.path}-${i}`} change={change} />
      ))}
    </div>
  );
}
