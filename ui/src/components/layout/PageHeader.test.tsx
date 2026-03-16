import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { PageHeader } from './PageHeader';

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('PageHeader', () => {
  it('renders title', () => {
    renderWithRouter(<PageHeader title="Dashboard" />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    renderWithRouter(<PageHeader title="Test" description="A description" />);
    expect(screen.getByText('A description')).toBeInTheDocument();
  });

  it('does not render description when not provided', () => {
    renderWithRouter(<PageHeader title="Test" />);
    expect(screen.queryByText('A description')).not.toBeInTheDocument();
  });

  it('renders back link when provided', () => {
    renderWithRouter(<PageHeader title="Test" backLink={{ to: '/runs', label: 'Back to runs' }} />);
    const link = screen.getByText('Back to runs');
    expect(link).toBeInTheDocument();
    expect(link.closest('a')).toHaveAttribute('href', '/runs');
  });

  it('renders actions when provided', () => {
    renderWithRouter(
      <PageHeader title="Test" actions={<button>Action</button>} />,
    );
    expect(screen.getByText('Action')).toBeInTheDocument();
  });

  it('renders separator', () => {
    const { container } = renderWithRouter(<PageHeader title="Test" />);
    expect(container.querySelector('[data-slot="separator"], [role="separator"], [data-orientation]')).toBeTruthy();
  });
});
