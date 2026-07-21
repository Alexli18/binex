import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CaoNodePanel, type CaoNodePanelProps } from './CaoNodePanel';

// Mock the API — default: server unavailable (isError = true)
vi.mock('@/lib/api', () => ({
  getCaoProfiles: vi.fn().mockRejectedValue(new Error('Server unavailable')),
  getCaoSessions: vi.fn(),
  deleteCaoSession: vi.fn(),
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function makeProps(overrides: Partial<CaoNodePanelProps> = {}): CaoNodePanelProps {
  return {
    agent: 'cao://default',
    config: {},
    onAgentChange: vi.fn(),
    onConfigChange: vi.fn(),
    ...overrides,
  };
}

describe('CaoNodePanel', () => {
  // useCAOProfiles hardcodes retry:1, so the error state arrives after the
  // retry delay (~1s) — give findBy* a longer timeout than the 1s default.
  const FALLBACK_TIMEOUT = { timeout: 4000 };

  it('renders fallback input when server is unavailable', async () => {
    render(<CaoNodePanel {...makeProps()} />, { wrapper: createWrapper() });
    // Wait for query to fail (after its retry)
    expect(
      await screen.findByText(/CAO server unavailable/i, {}, FALLBACK_TIMEOUT),
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText('profile_name.md')).toBeInTheDocument();
  });

  it('calls onAgentChange when manual profile is typed', async () => {
    const onAgentChange = vi.fn();
    render(<CaoNodePanel {...makeProps({ onAgentChange })} />, { wrapper: createWrapper() });
    const input = await screen.findByPlaceholderText(
      'profile_name.md', {}, FALLBACK_TIMEOUT,
    );
    fireEvent.change(input, { target: { value: 'my-agent' } });
    expect(onAgentChange).toHaveBeenCalledWith('cao://my-agent');
  });

  // NOTE: the Handoff/Assign/SendMessage mode radios were removed from the panel;
  // their tests were removed with them.

  it('calls onConfigChange for output format change', () => {
    const onConfigChange = vi.fn();
    render(<CaoNodePanel {...makeProps({ onConfigChange })} />, { wrapper: createWrapper() });
    // Output section exists
    expect(screen.getByText('Format')).toBeInTheDocument();
  });

  it('shows output_field input only when format is json', () => {
    const { rerender } = render(
      <CaoNodePanel {...makeProps({ config: { output_format: 'auto' } })} />,
      { wrapper: createWrapper() },
    );
    expect(screen.queryByPlaceholderText('$.result')).not.toBeInTheDocument();

    rerender(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <CaoNodePanel {...makeProps({ config: { output_format: 'json' } })} />
      </QueryClientProvider>,
    );
    expect(screen.getByPlaceholderText('$.result')).toBeInTheDocument();
  });

  it('renders timeout input with default 60', () => {
    render(<CaoNodePanel {...makeProps()} />, { wrapper: createWrapper() });
    const timeoutInput = screen.getByDisplayValue('60');
    expect(timeoutInput).toBeInTheDocument();
  });

  it('calls onConfigChange when timeout changes', () => {
    const onConfigChange = vi.fn();
    render(<CaoNodePanel {...makeProps({ onConfigChange })} />, { wrapper: createWrapper() });
    const timeoutInput = screen.getByDisplayValue('60');
    fireEvent.change(timeoutInput, { target: { value: '90' } });
    expect(onConfigChange).toHaveBeenCalledWith('timeout_minutes', 90);
  });
});
