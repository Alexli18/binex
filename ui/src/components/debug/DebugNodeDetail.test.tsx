import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { DebugNodeDetail, DebugNodeDetailSkeleton } from './DebugNodeDetail';
import type { DebugNode } from '@/hooks/useAnalysis';

vi.mock('./DebugArtifactViewer', () => ({
  DebugArtifactViewer: ({ title, artifacts }: { title: string; artifacts: unknown[] }) => (
    <div data-testid={`artifact-viewer-${title}`}>
      {artifacts.length} artifacts
    </div>
  ),
}));

vi.mock('./DebugErrorPanel', () => ({
  DebugErrorPanel: ({ error }: { error: string }) => (
    <div data-testid="error-panel">{error}</div>
  ),
}));

const makeNode = (overrides: Partial<DebugNode> = {}): DebugNode => ({
  node_id: 'test-node',
  status: 'completed',
  started_at: '2026-01-01T00:00:00Z',
  completed_at: '2026-01-01T00:00:01Z',
  duration_s: 1.5,
  error: null,
  artifacts: [],
  ...overrides,
});

describe('DebugNodeDetail', () => {
  it('shows placeholder when no node selected', () => {
    render(<DebugNodeDetail node={null} onReplay={vi.fn()} />);
    expect(screen.getByText('Select a node to view details')).toBeInTheDocument();
  });

  it('shows node_id as title', () => {
    render(<DebugNodeDetail node={makeNode()} onReplay={vi.fn()} />);
    expect(screen.getByText('test-node')).toBeInTheDocument();
  });

  it('shows status badge', () => {
    render(<DebugNodeDetail node={makeNode({ status: 'failed' })} onReplay={vi.fn()} />);
    const elements = screen.getAllByText('failed');
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it('shows duration', () => {
    render(<DebugNodeDetail node={makeNode()} onReplay={vi.fn()} />);
    expect(screen.getByText('1.500s')).toBeInTheDocument();
  });

  it('shows dash when duration is null', () => {
    render(<DebugNodeDetail node={makeNode({ duration_s: null })} onReplay={vi.fn()} />);
    expect(screen.getByText('-')).toBeInTheDocument();
  });

  it('calls onReplay when Replay clicked', async () => {
    const user = userEvent.setup();
    const onReplay = vi.fn();
    render(<DebugNodeDetail node={makeNode()} onReplay={onReplay} />);
    await user.click(screen.getByText('Replay'));
    expect(onReplay).toHaveBeenCalledWith('test-node');
  });

  it('shows "Replay call" and calls onReplayCall on observed runs', async () => {
    const user = userEvent.setup();
    const onReplayCall = vi.fn();
    const onReplay = vi.fn();
    render(
      <DebugNodeDetail
        node={makeNode()}
        onReplay={onReplay}
        observed
        onReplayCall={onReplayCall}
      />,
    );
    await user.click(screen.getByText('Replay call'));
    expect(onReplayCall).toHaveBeenCalledWith('test-node');
    expect(onReplay).not.toHaveBeenCalled();
  });

  it('shows agent info when present', () => {
    render(<DebugNodeDetail node={makeNode({ agent: 'llm://gpt-4' })} onReplay={vi.fn()} />);
    expect(screen.getByText('llm://gpt-4')).toBeInTheDocument();
  });

  it('shows model info when present', () => {
    render(<DebugNodeDetail node={makeNode({ model: 'gpt-4o' })} onReplay={vi.fn()} />);
    expect(screen.getByText('gpt-4o')).toBeInTheDocument();
  });

  it('shows system prompt when present', () => {
    render(<DebugNodeDetail node={makeNode({ system_prompt: 'You are helpful' })} onReplay={vi.fn()} />);
    expect(screen.getByText('You are helpful')).toBeInTheDocument();
  });

  it('shows error panel when node has error', () => {
    render(<DebugNodeDetail node={makeNode({ error: 'boom' })} onReplay={vi.fn()} />);
    expect(screen.getByTestId('error-panel')).toBeInTheDocument();
  });

  it('shows output artifacts when present', () => {
    const artifacts = [{ id: 'a1', type: 'text', content: 'hello' }];
    render(<DebugNodeDetail node={makeNode({ artifacts })} onReplay={vi.fn()} />);
    expect(screen.getByTestId('artifact-viewer-Output Artifacts')).toBeInTheDocument();
  });

  it('shows input artifacts when present', () => {
    const input_artifacts = [{ id: 'i1', type: 'text', content: 'input' }];
    render(<DebugNodeDetail node={makeNode({ input_artifacts })} onReplay={vi.fn()} />);
    expect(screen.getByTestId('artifact-viewer-Input Artifacts')).toBeInTheDocument();
  });
});

describe('DebugNodeDetailSkeleton', () => {
  it('renders without error', () => {
    const { container } = render(<DebugNodeDetailSkeleton />);
    expect(container.firstChild).toBeTruthy();
  });
});
