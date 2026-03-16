import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StatusBadge } from './StatusBadge';

const allStatuses = [
  'completed',
  'running',
  'failed',
  'cancelled',
  'pending',
  'skipped',
  'over_budget',
  'interrupted',
];

describe('StatusBadge', () => {
  it.each(allStatuses)('renders %s status', (status) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(status)).toBeInTheDocument();
  });

  it('renders with dot by default', () => {
    const { container } = render(<StatusBadge status="completed" />);
    const dot = container.querySelector('.rounded-full');
    expect(dot).toBeTruthy();
  });

  it('hides dot when dot=false', () => {
    const { container } = render(<StatusBadge status="completed" dot={false} />);
    const dot = container.querySelector('.rounded-full');
    expect(dot).toBeNull();
  });

  it('applies sm size classes by default', () => {
    render(<StatusBadge status="completed" />);
    const badge = screen.getByText('completed');
    expect(badge.className).toContain('text-xs');
  });

  it('applies md size classes', () => {
    render(<StatusBadge status="completed" size="md" />);
    const badge = screen.getByText('completed');
    expect(badge.className).toContain('text-body-sm');
  });

  it('accepts custom className', () => {
    render(<StatusBadge status="completed" className="custom-class" />);
    const badge = screen.getByText('completed');
    expect(badge.className).toContain('custom-class');
  });

  it('handles unknown status with fallback colors', () => {
    render(<StatusBadge status="unknown_status" />);
    expect(screen.getByText('unknown_status')).toBeInTheDocument();
  });

  it('shows pulse animation for running status', () => {
    const { container } = render(<StatusBadge status="running" />);
    const dot = container.querySelector('.rounded-full');
    expect(dot?.className).toContain('animate-pulse-status');
  });
});
