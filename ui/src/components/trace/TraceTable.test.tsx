import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TraceTable } from './TraceTable';
import type { TraceEntry, Anomaly } from '@/hooks/useAnalysis';

const makeEntry = (overrides: Partial<TraceEntry> = {}): TraceEntry => ({
  node_id: 'node-1',
  status: 'completed',
  started_at: '2026-01-01T00:00:00Z',
  completed_at: '2026-01-01T00:00:01Z',
  duration_s: 1.234,
  offset_s: 0,
  error: null,
  ...overrides,
});

const makeAnomaly = (overrides: Partial<Anomaly> = {}): Anomaly => ({
  node_id: 'node-1',
  duration_s: 5.0,
  ratio: 3.5,
  ...overrides,
});

describe('TraceTable', () => {
  it('shows empty message when no entries', () => {
    render(<TraceTable timeline={[]} anomalies={[]} />);
    expect(screen.getByText('No timeline entries')).toBeInTheDocument();
  });

  it('renders table headers', () => {
    render(<TraceTable timeline={[makeEntry()]} anomalies={[]} />);
    expect(screen.getByText('Node')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Duration')).toBeInTheDocument();
    expect(screen.getByText('Offset')).toBeInTheDocument();
    expect(screen.getByText('Started')).toBeInTheDocument();
  });

  it('renders node data', () => {
    render(<TraceTable timeline={[makeEntry()]} anomalies={[]} />);
    expect(screen.getByText('node-1')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('1.234s')).toBeInTheDocument();
  });

  it('shows anomaly label for anomalous nodes', () => {
    const entries = [makeEntry({ node_id: 'slow-node' })];
    const anomalies = [makeAnomaly({ node_id: 'slow-node' })];
    render(<TraceTable timeline={entries} anomalies={anomalies} />);
    expect(screen.getByText('anomaly')).toBeInTheDocument();
  });

  it('does not show anomaly label for normal nodes', () => {
    const entries = [makeEntry({ node_id: 'normal-node' })];
    render(<TraceTable timeline={entries} anomalies={[]} />);
    expect(screen.queryByText('anomaly')).not.toBeInTheDocument();
  });

  it('renders multiple rows', () => {
    const entries = [
      makeEntry({ node_id: 'a' }),
      makeEntry({ node_id: 'b' }),
      makeEntry({ node_id: 'c' }),
    ];
    render(<TraceTable timeline={entries} anomalies={[]} />);
    expect(screen.getByText('a')).toBeInTheDocument();
    expect(screen.getByText('b')).toBeInTheDocument();
    expect(screen.getByText('c')).toBeInTheDocument();
  });
});
