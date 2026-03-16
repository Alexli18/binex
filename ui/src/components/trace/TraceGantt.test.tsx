import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { TraceGantt } from './TraceGantt';
import type { TraceEntry } from '@/hooks/useAnalysis';

const makeEntry = (overrides: Partial<TraceEntry> = {}): TraceEntry => ({
  node_id: 'node-1',
  status: 'completed',
  started_at: '2026-01-01T00:00:00Z',
  completed_at: '2026-01-01T00:00:01Z',
  duration_s: 1.0,
  offset_s: 0,
  error: null,
  ...overrides,
});

describe('TraceGantt', () => {
  it('shows empty message when totalDuration is 0', () => {
    render(<TraceGantt timeline={[]} totalDuration={0} anomalyNodeIds={new Set()} />);
    expect(screen.getByText(/No timeline data/)).toBeInTheDocument();
  });

  it('renders time axis', () => {
    render(<TraceGantt timeline={[makeEntry()]} totalDuration={2.0} anomalyNodeIds={new Set()} />);
    expect(screen.getByText('0s')).toBeInTheDocument();
    expect(screen.getByText('2.0s')).toBeInTheDocument();
  });

  it('renders node labels', () => {
    const entries = [makeEntry({ node_id: 'alpha' }), makeEntry({ node_id: 'beta', offset_s: 0.5 })];
    render(<TraceGantt timeline={entries} totalDuration={2.0} anomalyNodeIds={new Set()} />);
    expect(screen.getByText('alpha')).toBeInTheDocument();
    expect(screen.getByText('beta')).toBeInTheDocument();
  });

  it('shows detail panel when bar is clicked', async () => {
    const user = userEvent.setup();
    const entries = [makeEntry({ node_id: 'click-me', duration_s: 1.5, offset_s: 0 })];
    const { container } = render(
      <TraceGantt timeline={entries} totalDuration={3.0} anomalyNodeIds={new Set()} />,
    );
    // Click on the bar (the absolute positioned div with cursor-pointer)
    const bar = container.querySelector('.cursor-pointer');
    expect(bar).toBeTruthy();
    await user.click(bar!);
    // Should show detail with node id
    expect(screen.getAllByText('click-me').length).toBeGreaterThanOrEqual(2);
  });

  it('sorts entries by offset', () => {
    const entries = [
      makeEntry({ node_id: 'second', offset_s: 1 }),
      makeEntry({ node_id: 'first', offset_s: 0 }),
    ];
    const { container } = render(
      <TraceGantt timeline={entries} totalDuration={2.0} anomalyNodeIds={new Set()} />,
    );
    const labels = container.querySelectorAll('.font-mono.text-slate-400');
    expect(labels[0]?.textContent).toBe('first');
    expect(labels[1]?.textContent).toBe('second');
  });
});
