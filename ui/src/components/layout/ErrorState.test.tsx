import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { ErrorState } from './ErrorState';

describe('ErrorState', () => {
  it('renders default title', () => {
    render(<ErrorState message="Failed to load" />);
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('renders custom title', () => {
    render(<ErrorState title="Network Error" message="Failed to load" />);
    expect(screen.getByText('Network Error')).toBeInTheDocument();
  });

  it('renders error message', () => {
    render(<ErrorState message="Connection refused" />);
    expect(screen.getByText('Connection refused')).toBeInTheDocument();
  });

  it('renders retry button when onRetry provided', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorState message="Error" onRetry={onRetry} />);
    const btn = screen.getByText('Retry');
    expect(btn).toBeInTheDocument();
    await user.click(btn);
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('does not render retry button when onRetry not provided', () => {
    render(<ErrorState message="Error" />);
    expect(screen.queryByText('Retry')).not.toBeInTheDocument();
  });
});
