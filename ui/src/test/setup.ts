import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Mock HelpTooltip globally — it requires TooltipProvider from Radix
// which is only provided in the app root. Tests should not need it.
vi.mock('@/components/common/HelpTooltip', () => ({
  HelpTooltip: () => null,
}));
