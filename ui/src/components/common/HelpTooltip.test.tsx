import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TooltipProvider } from '@/components/ui/tooltip';

// Override the global mock for this specific test file
vi.unmock('@/components/common/HelpTooltip');

import { HelpTooltip } from './HelpTooltip';

function renderWithProvider(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe('HelpTooltip', () => {
  it('renders help button with aria-label', () => {
    renderWithProvider(<HelpTooltip content="Help text" />);
    expect(screen.getByLabelText('Help')).toBeInTheDocument();
  });

  it('renders with custom className', () => {
    renderWithProvider(<HelpTooltip content="Help" className="custom" />);
    const button = screen.getByLabelText('Help');
    expect(button.className).toContain('custom');
  });

  it('renders SVG icon', () => {
    renderWithProvider(<HelpTooltip content="Help" />);
    const button = screen.getByLabelText('Help');
    expect(button.querySelector('svg')).toBeTruthy();
  });
});
