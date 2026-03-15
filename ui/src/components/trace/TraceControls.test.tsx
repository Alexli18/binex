import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { TraceControls } from './TraceControls';
import type { Anomaly } from '@/hooks/useAnalysis';

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

const makeAnomaly = (overrides: Partial<Anomaly> = {}): Anomaly => ({
  node_id: 'slow-node',
  duration_s: 5.0,
  ratio: 3.5,
  ...overrides,
});

describe('TraceControls', () => {
  it('renders title', () => {
    renderWithRouter(
      <TraceControls runId="r1" status="completed" totalDuration={2.5} anomalies={[]} />,
    );
    expect(screen.getByText('Trace Timeline')).toBeInTheDocument();
  });

  it('shows total duration and status', () => {
    renderWithRouter(
      <TraceControls runId="r1" status="completed" totalDuration={2.5} anomalies={[]} />,
    );
    expect(screen.getByText(/2\.500s/)).toBeInTheDocument();
    expect(screen.getByText(/completed/)).toBeInTheDocument();
  });

  it('renders Debug and Diagnose links', () => {
    renderWithRouter(
      <TraceControls runId="r1" status="completed" totalDuration={1} anomalies={[]} />,
    );
    expect(screen.getByText('Debug')).toBeInTheDocument();
    expect(screen.getByText('Diagnose')).toBeInTheDocument();
  });

  it('renders legend items', () => {
    renderWithRouter(
      <TraceControls runId="r1" status="completed" totalDuration={1} anomalies={[]} />,
    );
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Anomaly')).toBeInTheDocument();
  });

  it('shows anomalies section when anomalies present', () => {
    renderWithRouter(
      <TraceControls
        runId="r1"
        status="completed"
        totalDuration={10}
        anomalies={[makeAnomaly()]}
      />,
    );
    expect(screen.getByText('Latency Anomalies (1)')).toBeInTheDocument();
    expect(screen.getByText('slow-node')).toBeInTheDocument();
    expect(screen.getByText(/5\.000s/)).toBeInTheDocument();
    expect(screen.getByText(/3\.5x avg/)).toBeInTheDocument();
  });

  it('hides anomalies section when empty', () => {
    renderWithRouter(
      <TraceControls runId="r1" status="completed" totalDuration={1} anomalies={[]} />,
    );
    expect(screen.queryByText(/Latency Anomalies/)).not.toBeInTheDocument();
  });
});
