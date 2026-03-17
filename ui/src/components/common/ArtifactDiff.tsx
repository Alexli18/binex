import { diffColors, typography } from '@/lib/design-tokens';

function DiffLine({ line }: { line: string }) {
  if (line.startsWith('+')) {
    return <div className={`${diffColors.added.bg} ${diffColors.added.text} px-2`}>{line}</div>;
  }
  if (line.startsWith('-')) {
    return <div className={`${diffColors.removed.bg} ${diffColors.removed.text} px-2`}>{line}</div>;
  }
  if (line.startsWith('@@')) {
    return <div className={`${diffColors.hunk} px-2`}>{line}</div>;
  }
  return <div className={`px-2 ${typography.body}`}>{line}</div>;
}

export function ArtifactDiff({ diff }: { diff: string }) {
  const lines = diff.split('\n');
  return (
    <pre className="bg-slate-950 rounded-card p-3 text-xs font-mono overflow-x-auto max-h-96 overflow-y-auto border border-slate-700">
      {lines.map((line, i) => (
        <DiffLine key={i} line={line} />
      ))}
    </pre>
  );
}
