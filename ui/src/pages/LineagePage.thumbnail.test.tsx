import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ReactFlowProvider } from 'reactflow';
import { ArtifactNode } from './LineagePage';
import type { LineageNode } from '../hooks/useAnalysis';

function renderNode(data: LineageNode & { label: string }) {
  return render(
    <ReactFlowProvider>
      <ArtifactNode
        id={data.id}
        type="artifact"
        data={data}
        selected={false}
        zIndex={0}
        isConnectable
        xPos={0}
        yPos={0}
        dragging={false}
      />
    </ReactFlowProvider>,
  );
}

describe('LineagePage ArtifactNode', () => {
  it('renders an <img> thumbnail for image binary artifacts (#76)', () => {
    renderNode({
      id: 'img-1',
      label: 'img-1',
      type: 'binary',
      produced_by: 'sprite-gen',
      content: { kind: 'binary', mime: 'image/png' },
      binary: true,
      mime: 'image/png',
      blob_url: '/api/v1/runs/r1/artifacts/img-1/blob',
    });
    const img = screen.getByAltText('img-1') as HTMLImageElement;
    expect(img.tagName).toBe('IMG');
    expect(img.getAttribute('src')).toBe('/api/v1/runs/r1/artifacts/img-1/blob');
    expect(screen.getByText('image/png')).toBeInTheDocument();
  });

  it('renders a text preview for non-binary artifacts', () => {
    renderNode({
      id: 'txt-1',
      label: 'txt-1',
      type: 'text',
      produced_by: 'writer',
      content: 'hello world',
    });
    expect(screen.getByText(/hello world/)).toBeInTheDocument();
    expect(screen.queryByAltText('txt-1')).not.toBeInTheDocument();
  });
});
