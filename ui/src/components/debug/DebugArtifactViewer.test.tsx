import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { DebugArtifactViewer } from './DebugArtifactViewer';
import type { DebugArtifact } from '@/hooks/useAnalysis';

const makeArtifact = (overrides: Partial<DebugArtifact> = {}): DebugArtifact => ({
  id: 'art-1',
  type: 'text',
  content: 'Hello world',
  ...overrides,
});

describe('DebugArtifactViewer', () => {
  it('renders title with count', () => {
    render(<DebugArtifactViewer title="Output Artifacts" artifacts={[makeArtifact()]} />);
    expect(screen.getByText('Output Artifacts (1)')).toBeInTheDocument();
  });

  it('renders artifact type and id', () => {
    render(<DebugArtifactViewer title="Test" artifacts={[makeArtifact()]} />);
    expect(screen.getByText('text')).toBeInTheDocument();
    expect(screen.getByText('art-1')).toBeInTheDocument();
  });

  it('expands artifact on click', async () => {
    const user = userEvent.setup();
    render(<DebugArtifactViewer title="Test" artifacts={[makeArtifact()]} />);
    expect(screen.getByText('expand')).toBeInTheDocument();
    await user.click(screen.getByText('expand'));
    expect(screen.getByText('Hello world')).toBeInTheDocument();
    expect(screen.getByText('collapse')).toBeInTheDocument();
  });

  it('collapses artifact on second click', async () => {
    const user = userEvent.setup();
    render(<DebugArtifactViewer title="Test" artifacts={[makeArtifact()]} />);
    await user.click(screen.getByText('expand'));
    await user.click(screen.getByText('collapse'));
    expect(screen.getByText('expand')).toBeInTheDocument();
  });

  it('formats JSON content', async () => {
    const user = userEvent.setup();
    const artifact = makeArtifact({ content: { key: 'value' } as unknown as string });
    render(<DebugArtifactViewer title="Test" artifacts={[artifact]} />);
    await user.click(screen.getByText('expand'));
    expect(screen.getByText(/"key": "value"/)).toBeInTheDocument();
  });

  it('renders multiple artifacts', () => {
    const artifacts = [makeArtifact({ id: 'a1' }), makeArtifact({ id: 'a2' })];
    render(<DebugArtifactViewer title="Test" artifacts={artifacts} />);
    expect(screen.getByText('Test (2)')).toBeInTheDocument();
    expect(screen.getByText('a1')).toBeInTheDocument();
    expect(screen.getByText('a2')).toBeInTheDocument();
  });

  it('auto-expands single artifact when defaultExpanded', () => {
    render(<DebugArtifactViewer title="Test" artifacts={[makeArtifact()]} defaultExpanded />);
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  const binaryArtifact = (mime: string): DebugArtifact =>
    makeArtifact({
      id: 'img-1',
      type: 'binary',
      content: { kind: 'binary', mime, size: 2048, sha256: 'abc' },
      binary: true,
      mime,
      size: 2048,
      blob_url: '/api/v1/runs/r1/artifacts/img-1/blob',
    });

  it('shows a mime badge on binary artifacts', () => {
    render(<DebugArtifactViewer title="Test" artifacts={[binaryArtifact('image/png')]} />);
    expect(screen.getByText('image/png')).toBeInTheDocument();
  });

  it('renders an <img> preview for image binaries when expanded', async () => {
    const user = userEvent.setup();
    render(<DebugArtifactViewer title="Test" artifacts={[binaryArtifact('image/png')]} />);
    await user.click(screen.getByText('expand'));
    const img = screen.getByAltText('img-1') as HTMLImageElement;
    expect(img.tagName).toBe('IMG');
    expect(img.getAttribute('src')).toBe('/api/v1/runs/r1/artifacts/img-1/blob');
  });

  it('renders an <audio> player for audio binaries', async () => {
    const user = userEvent.setup();
    const { container } = render(
      <DebugArtifactViewer title="Test" artifacts={[binaryArtifact('audio/wav')]} />,
    );
    await user.click(screen.getByText('expand'));
    expect(container.querySelector('audio')).not.toBeNull();
  });

  it('falls back to a download link for other binaries', async () => {
    const user = userEvent.setup();
    render(<DebugArtifactViewer title="Test" artifacts={[binaryArtifact('application/zip')]} />);
    await user.click(screen.getByText('expand'));
    expect(screen.getByText(/Download application\/zip/)).toBeInTheDocument();
  });

  it('detects binary from envelope even without the binary flag', async () => {
    const user = userEvent.setup();
    const art = makeArtifact({
      id: 'img-2',
      content: { kind: 'binary', mime: 'image/png' },
      blob_url: '/blob',
      mime: 'image/png',
    });
    render(<DebugArtifactViewer title="Test" artifacts={[art]} />);
    await user.click(screen.getByText('expand'));
    expect(screen.getByAltText('img-2')).toBeInTheDocument();
  });
});
