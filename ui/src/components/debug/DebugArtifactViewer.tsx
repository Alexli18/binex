import { useState } from 'react';
import type { DebugArtifact } from '@/hooks/useAnalysis';

export interface DebugArtifactViewerProps {
  title: string;
  artifacts: DebugArtifact[];
  defaultExpanded?: boolean;
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
              {isExpanded && (
                <pre className="border-t border-[#252528] bg-[#131315] p-3 text-xs text-[#80808a] whitespace-pre-wrap break-words max-h-80 overflow-y-auto">
                  {content}
                </pre>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
