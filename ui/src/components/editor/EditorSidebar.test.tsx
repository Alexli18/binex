import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { EditorSidebar, type EditorSidebarProps } from './EditorSidebar';

vi.mock('@/components/CostEstimatePanel', () => ({
  CostEstimatePanel: ({ yamlContent }: { yamlContent: string }) => (
    <div data-testid="cost-panel">{yamlContent}</div>
  ),
}));

vi.mock('@/components/SaveAsModal', () => ({
  SaveAsModal: ({ onSave, onClose, isPending }: { onSave: (p: string) => void; onClose: () => void; isPending: boolean }) => (
    <div data-testid="save-as-modal" data-pending={isPending}>
      <button onClick={() => onSave('/test.yaml')}>Save</button>
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

function makeProps(overrides: Partial<EditorSidebarProps> = {}): EditorSidebarProps {
  return {
    showCost: false,
    hasContent: true,
    yamlContent: 'name: test',
    showSaveAs: false,
    isSaving: false,
    onSaveAs: vi.fn(),
    onCloseSaveAs: vi.fn(),
    ...overrides,
  };
}

describe('EditorSidebar', () => {
  it('shows cost panel when showCost and hasContent', () => {
    render(<EditorSidebar {...makeProps({ showCost: true, hasContent: true })} />);
    expect(screen.getByTestId('cost-panel')).toBeInTheDocument();
  });

  it('hides cost panel when showCost is false', () => {
    render(<EditorSidebar {...makeProps({ showCost: false })} />);
    expect(screen.queryByTestId('cost-panel')).not.toBeInTheDocument();
  });

  it('hides cost panel when no content', () => {
    render(<EditorSidebar {...makeProps({ showCost: true, hasContent: false })} />);
    expect(screen.queryByTestId('cost-panel')).not.toBeInTheDocument();
  });

  it('shows SaveAsModal when showSaveAs', () => {
    render(<EditorSidebar {...makeProps({ showSaveAs: true })} />);
    expect(screen.getByTestId('save-as-modal')).toBeInTheDocument();
  });

  it('hides SaveAsModal when showSaveAs is false', () => {
    render(<EditorSidebar {...makeProps({ showSaveAs: false })} />);
    expect(screen.queryByTestId('save-as-modal')).not.toBeInTheDocument();
  });
});
