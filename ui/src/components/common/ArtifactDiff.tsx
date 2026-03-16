function DiffLine({ line }: { line: string }) {
  if (line.startsWith('+')) {
    return <div className="bg-green-900/40 text-green-300 px-2">{line}</div>;
  }
  if (line.startsWith('-')) {
    return <div className="bg-red-900/40 text-red-300 px-2">{line}</div>;
  }
  if (line.startsWith('@@')) {
    return <div className="text-blue-400 px-2">{line}</div>;
  }
  return <div className="px-2 text-slate-300">{line}</div>;
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
