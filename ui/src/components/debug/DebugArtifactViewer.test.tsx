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
    expect(screen.getByText(/\"key\": \"value\"/)).toBeInTheDocument();
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
});
