import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { SemanticConfirm } from './SemanticConfirm';
import type { SemanticEstimate } from '@/hooks/useComparison';

const estimate: SemanticEstimate = {
  calls: 3,
  prompt_tokens: 900,
  completion_tokens: 480,
  total_tokens: 1380,
  cost: 0.00062,
  model: 'gpt-4o-mini',
  nodes: ['draft', 'review', 'summary'],
};

function setup(overrides: Partial<Parameters<typeof SemanticConfirm>[0]> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <SemanticConfirm
      open
      estimate={estimate}
      loading={false}
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...overrides}
    />
  );
  return { onConfirm, onCancel };
}

describe('SemanticConfirm', () => {
  it('states the number of calls, the model and the cost before anything runs', () => {
    setup();

    // Exact matchers: "3" also appears inside the token count.
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('gpt-4o-mini')).toBeInTheDocument();
    expect(screen.getByText('~1380')).toBeInTheDocument();
    expect(screen.getByText(/\$0\.0006/)).toBeInTheDocument();
  });

  it('says the cost is unknown for an unpriced model rather than showing $0', () => {
    setup({ estimate: { ...estimate, cost: null } });

    expect(screen.getByText(/unknown/i)).toBeInTheDocument();
    expect(screen.queryByText('$0.0000')).not.toBeInTheDocument();
  });

  it('confirms only on an explicit click', async () => {
    const { onConfirm } = setup();

    expect(onConfirm).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: /run analysis/i }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('cancels without running', async () => {
    const { onConfirm, onCancel } = setup();

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('renders nothing when closed', () => {
    const { container } = render(
      <SemanticConfirm
        open={false}
        estimate={estimate}
        loading={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('offers no confirmation when there is nothing to analyze', () => {
    setup({ estimate: { ...estimate, calls: 0, nodes: [], total_tokens: 0, cost: 0 } });

    expect(screen.getByText(/nothing to analyze/i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /run analysis/i })
    ).not.toBeInTheDocument();
  });

  it('shows a loading state while the estimate is being fetched', () => {
    setup({ estimate: null, loading: true });

    expect(screen.getByText(/estimating/i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /run analysis/i })
    ).not.toBeInTheDocument();
  });
});
