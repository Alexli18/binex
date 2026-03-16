import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { DebugErrorPanel } from './DebugErrorPanel';

describe('DebugErrorPanel', () => {
  it('renders error message', () => {
    render(<DebugErrorPanel error="Something went wrong" />);
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('renders Error label', () => {
    render(<DebugErrorPanel error="test" />);
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('shows stack trace tip for Python tracebacks', () => {
    const error = 'Traceback (most recent call last):\n  File "test.py", line 1\nValueError: bad';
    render(<DebugErrorPanel error={error} />);
    expect(screen.getByText(/Check the stack trace above/)).toBeInTheDocument();
  });

  it('shows stack trace tip for JS stack traces', () => {
    const error = 'Error: failed\n  at Object.run (index.js:10)\n  at main (app.js:5)';
    render(<DebugErrorPanel error={error} />);
    expect(screen.getByText(/Check the stack trace above/)).toBeInTheDocument();
  });

  it('does not show tip for simple errors', () => {
    render(<DebugErrorPanel error="timeout" />);
    expect(screen.queryByText(/Check the stack trace above/)).not.toBeInTheDocument();
  });
});
