import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { DebugNodeList, DebugNodeListSkeleton, type DebugNodeListProps } from './DebugNodeList';
import type { DebugNode } from '@/hooks/useAnalysis';

const makeNode = (overrides: Partial<DebugNode> = {}): DebugNode => ({
  node_id: 'node-1',
  status: 'completed',
  started_at: '2026-01-01T00:00:00Z',
  completed_at: '2026-01-01T00:00:01Z',
  duration_s: 1.234,
  error: null,
  artifacts: [],
  ...overrides,
});

function makeProps(overrides: Partial<DebugNodeListProps> = {}): DebugNodeListProps {
  return {
    nodes: [makeNode()],
    selectedNodeId: null,
    errorsOnly: false,
    onSelectNode: vi.fn(),
    onErrorsOnlyChange: vi.fn(),
    ...overrides,
  };
}

describe('DebugNodeList', () => {
  it('renders node list', () => {
    render(<DebugNodeList {...makeProps()} />);
    expect(screen.getByText('node-1')).toBeInTheDocument();
  });

  it('renders multiple nodes', () => {
    const nodes = [makeNode({ node_id: 'a' }), makeNode({ node_id: 'b' })];
    render(<DebugNodeList {...makeProps({ nodes })} />);
    expect(screen.getByText('a')).toBeInTheDocument();
    expect(screen.getByText('b')).toBeInTheDocument();
  });

  it('shows duration for nodes', () => {
    render(<DebugNodeList {...makeProps()} />);
    expect(screen.getByText('1.234s')).toBeInTheDocument();
  });

  it('filters nodes by text input', async () => {
    const user = userEvent.setup();
    const nodes = [makeNode({ node_id: 'alpha' }), makeNode({ node_id: 'beta' })];
    render(<DebugNodeList {...makeProps({ nodes })} />);
    await user.type(screen.getByPlaceholderText('Filter nodes...'), 'alpha');
    expect(screen.getByText('alpha')).toBeInTheDocument();
    expect(screen.queryByText('beta')).not.toBeInTheDocument();
  });

  it('shows "No nodes found" when filter matches nothing', async () => {
    const user = userEvent.setup();
    render(<DebugNodeList {...makeProps()} />);
    await user.type(screen.getByPlaceholderText('Filter nodes...'), 'zzz');
    expect(screen.getByText('No nodes found')).toBeInTheDocument();
  });

  it('calls onSelectNode when node clicked', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<DebugNodeList {...props} />);
    await user.click(screen.getByText('node-1'));
    expect(props.onSelectNode).toHaveBeenCalledWith('node-1');
  });

  it('calls onSelectNode(null) when selected node clicked again', async () => {
    const user = userEvent.setup();
    const props = makeProps({ selectedNodeId: 'node-1' });
    render(<DebugNodeList {...props} />);
    await user.click(screen.getByText('node-1'));
    expect(props.onSelectNode).toHaveBeenCalledWith(null);
  });

  it('toggles errors-only checkbox', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<DebugNodeList {...props} />);
    await user.click(screen.getByLabelText('Errors only'));
    expect(props.onErrorsOnlyChange).toHaveBeenCalledWith(true);
  });

  it('shows error indicator for nodes with errors', () => {
    const nodes = [makeNode({ node_id: 'err-node', error: 'something failed' })];
    render(<DebugNodeList {...makeProps({ nodes })} />);
    expect(screen.getByText('err-node')).toBeInTheDocument();
  });
});

describe('DebugNodeListSkeleton', () => {
  it('renders skeleton elements', () => {
    const { container } = render(<DebugNodeListSkeleton />);
    // Should have multiple skeleton divs
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
