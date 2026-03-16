import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { LoadingState } from './LoadingState';

describe('LoadingState', () => {
  it('renders page variant by default', () => {
    render(<LoadingState />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('renders custom message', () => {
    render(<LoadingState message="Fetching data..." />);
    expect(screen.getByText('Fetching data...')).toBeInTheDocument();
  });

  it('renders inline variant', () => {
    render(<LoadingState variant="inline" message="Working..." />);
    expect(screen.getByText('Working...')).toBeInTheDocument();
  });

  it('renders skeleton variant without text message', () => {
    const { container } = render(<LoadingState variant="skeleton" />);
    // Skeleton variant renders Skeleton components, not the message text
    expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
    // Should have skeleton divs (Skeleton uses animate-pulse class)
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
  });

  it('renders spinner for page variant', () => {
    const { container } = render(<LoadingState variant="page" />);
    expect(container.querySelector('.animate-spin')).toBeTruthy();
  });

  it('renders spinner for inline variant', () => {
    const { container } = render(<LoadingState variant="inline" />);
    expect(container.querySelector('.animate-spin')).toBeTruthy();
  });
});
