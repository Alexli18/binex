import { useState } from 'react';
import type { DebugArtifact } from '@/hooks/useAnalysis';

export interface DebugArtifactViewerProps {
  title: string;
  artifacts: DebugArtifact[];
  defaultExpanded?: boolean;
}

function formatBytes(size?: number): string {
  if (!size) return '';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

/** Inline preview for a binary artifact (#76): image, audio, PDF, or download. */
function BinaryPreview({ artifact }: { artifact: DebugArtifact }) {
  const { mime = '', blob_url, size } = artifact;
  if (!blob_url) {
    return (
      <div className="border-t border-[#252528] bg-[#131315] p-3 text-xs text-[#80808a]">
        Binary artifact ({mime || 'unknown'}) — no payload URL.
      </div>
    );
  }
  const meta = (
    <div className="mt-2 text-xs text-[#4a4a52]">
      {mime} · {formatBytes(size)} ·{' '}
      <a href={blob_url} download className="text-amber-400 hover:underline">
        download
      </a>
    </div>
  );
  return (
    <div className="border-t border-[#252528] bg-[#131315] p-3">
      {mime.startsWith('image/') ? (
        <img
          src={blob_url}
          alt={artifact.id}
          className="max-h-80 max-w-full rounded border border-[#252528] object-contain"
        />
      ) : mime.startsWith('audio/') ? (
        <audio src={blob_url} controls className="w-full" />
      ) : mime === 'application/pdf' ? (
        <embed src={blob_url} type="application/pdf" className="h-80 w-full rounded" />
      ) : (
        <a href={blob_url} download className="text-sm text-amber-400 hover:underline">
          Download {mime || 'file'}
        </a>
      )}
      {meta}
    </div>
  );
}

export function DebugArtifactViewer({
  title,
  artifacts,
  defaultExpanded = false,
}: DebugArtifactViewerProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(
    defaultExpanded && artifacts.length === 1 ? 0 : null,
  );

  return (
    <div>
      <span className="text-sm text-[#4a4a52]">
        {title} ({artifacts.length})
      </span>
      <div className="mt-2 space-y-2">
        {artifacts.map((a, i) => {
          const isExpanded = expandedIndex === i;
          const isBinary =
            a.binary === true ||
            (typeof a.content === 'object' &&
              a.content !== null &&
              (a.content as { kind?: string }).kind === 'binary');
          const content =
            typeof a.content === 'string'
              ? a.content
              : JSON.stringify(a.content, null, 2);
          return (
            <div
              key={i}
              className="rounded-md border border-[#252528] bg-[#1a1a1d]/50"
            >
              <button
                onClick={() => setExpandedIndex(isExpanded ? null : i)}
                className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-[#1a1a1d]/30 transition-colors"
              >
                <span className="font-medium text-[#80808a]">
                  {a.type}
                  {isBinary && (
                    <span className="ml-2 rounded bg-amber-400/10 px-1.5 py-0.5 text-xs text-amber-400">
                      {a.mime ?? 'binary'}
                    </span>
                  )}
                  <span className="ml-2 text-xs text-[#4a4a52] font-mono">
                    {a.id}
                  </span>
                  {(a as { produced_by?: string }).produced_by && (
                    <span className="ml-2 text-xs text-[#4a4a52]">
                      from {(a as { produced_by?: string }).produced_by}
                    </span>
                  )}
                </span>
                <span className="text-xs text-amber-400">
                  {isExpanded ? 'collapse' : 'expand'}
                </span>
              </button>
              {isExpanded &&
                (isBinary ? (
                  <BinaryPreview artifact={a} />
                ) : (
                  <pre className="border-t border-[#252528] bg-[#131315] p-3 text-xs text-[#80808a] whitespace-pre-wrap break-words max-h-80 overflow-y-auto">
                    {content}
                  </pre>
                ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
