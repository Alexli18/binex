import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PageShell } from './PageShell';

describe('PageShell', () => {
  it('renders children', () => {
    render(
      <PageShell>
        <div>Page content</div>
      </PageShell>,
    );
    expect(screen.getByText('Page content')).toBeInTheDocument();
  });

  it('applies max-w-7xl class', () => {
    const { container } = render(
      <PageShell>Content</PageShell>,
    );
    expect(container.firstChild).toHaveClass('max-w-7xl');
  });

  it('applies custom className', () => {
    const { container } = render(
      <PageShell className="extra-class">Content</PageShell>,
    );
    expect(container.firstChild).toHaveClass('extra-class');
  });

  it('applies padding', () => {
    const { container } = render(
      <PageShell>Content</PageShell>,
    );
    expect(container.firstChild).toHaveClass('px-6');
    expect(container.firstChild).toHaveClass('py-6');
  });
});
