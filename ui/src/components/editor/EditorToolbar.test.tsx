import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { EditorToolbar, type EditorToolbarProps } from './EditorToolbar';

function makeProps(overrides: Partial<EditorToolbarProps> = {}): EditorToolbarProps {
  return {
    selectedPath: null,
    isDirty: false,
    mode: 'visual',
    isSaving: false,
    isRunning: false,
    hasContent: true,
    onOpenFiles: vi.fn(),
    onSwitchToVisual: vi.fn(),
    onSwitchToYaml: vi.fn(),
    onSave: vi.fn(),
    onRun: vi.fn(),
    ...overrides,
  };
}

describe('EditorToolbar', () => {
  it('renders mode switch buttons', () => {
    render(<EditorToolbar {...makeProps()} />);
    expect(screen.getByText('Visual')).toBeInTheDocument();
    expect(screen.getByText('YAML')).toBeInTheDocument();
  });

  it('renders Save and Run buttons', () => {
    render(<EditorToolbar {...makeProps()} />);
    expect(screen.getByText('Save')).toBeInTheDocument();
    expect(screen.getByText('▸ Run')).toBeInTheDocument();
  });

  it('shows selected file path', () => {
    render(<EditorToolbar {...makeProps({ selectedPath: 'workflows/test.yaml' })} />);
    expect(screen.getByText('workflows/test.yaml')).toBeInTheDocument();
  });

  it('shows (new workflow) when hasContent but no path', () => {
    render(<EditorToolbar {...makeProps({ selectedPath: null, hasContent: true })} />);
    expect(screen.getByText('(new workflow)')).toBeInTheDocument();
  });

  it('shows empty when no content and no path', () => {
    render(<EditorToolbar {...makeProps({ selectedPath: null, hasContent: false })} />);
    expect(screen.queryByText('(new workflow)')).not.toBeInTheDocument();
  });

  it('shows unsaved indicator when dirty', () => {
    render(<EditorToolbar {...makeProps({ isDirty: true })} />);
    expect(screen.getByText('unsaved')).toBeInTheDocument();
  });

  it('hides unsaved indicator when not dirty', () => {
    render(<EditorToolbar {...makeProps({ isDirty: false })} />);
    expect(screen.queryByText('unsaved')).not.toBeInTheDocument();
  });

  it('calls onSwitchToVisual when Visual clicked', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<EditorToolbar {...props} />);
    await user.click(screen.getByText('Visual'));
    expect(props.onSwitchToVisual).toHaveBeenCalledOnce();
  });

  it('calls onSwitchToYaml when YAML clicked', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<EditorToolbar {...props} />);
    await user.click(screen.getByText('YAML'));
    expect(props.onSwitchToYaml).toHaveBeenCalledOnce();
  });

  it('calls onSave when Save clicked', async () => {
    const user = userEvent.setup();
    const props = makeProps({ selectedPath: 'test.yaml', isDirty: true });
    render(<EditorToolbar {...props} />);
    await user.click(screen.getByText('Save'));
    expect(props.onSave).toHaveBeenCalledOnce();
  });

  it('calls onRun when Run clicked', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<EditorToolbar {...props} />);
    await user.click(screen.getByText('▸ Run'));
    expect(props.onRun).toHaveBeenCalledOnce();
  });

  it('disables Save when not dirty and has path', () => {
    render(<EditorToolbar {...makeProps({ selectedPath: 'x.yaml', isDirty: false })} />);
    expect(screen.getByText('Save').closest('button')).toBeDisabled();
  });

  it('disables Run when no content', () => {
    render(<EditorToolbar {...makeProps({ hasContent: false })} />);
    expect(screen.getByText('▸ Run').closest('button')).toBeDisabled();
  });

  it('shows "Saving..." when isSaving', () => {
    render(<EditorToolbar {...makeProps({ isSaving: true })} />);
    expect(screen.getByText('Saving…')).toBeInTheDocument();
  });

  it('shows "Starting..." when isRunning', () => {
    render(<EditorToolbar {...makeProps({ isRunning: true })} />);
    expect(screen.getByText('Starting…')).toBeInTheDocument();
  });

  it('calls onOpenFiles when Open clicked', async () => {
    const user = userEvent.setup();
    const props = makeProps();
    render(<EditorToolbar {...props} />);
    await user.click(screen.getByText('Open'));
    expect(props.onOpenFiles).toHaveBeenCalledOnce();
  });
});
