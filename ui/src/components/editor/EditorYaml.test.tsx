import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { EditorYaml, type EditorYamlProps } from './EditorYaml';

// Mock Monaco Editor
vi.mock('@monaco-editor/react', () => ({
  default: (props: { value?: string; language?: string; onChange?: (v: string | undefined) => void }) => (
    <textarea
      data-testid="monaco-editor"
      data-language={props.language}
      value={props.value}
      onChange={(e) => props.onChange?.(e.target.value)}
    />
  ),
}));

function makeProps(overrides: Partial<EditorYamlProps> = {}): EditorYamlProps {
  return {
    content: '',
    selectedPath: null,
    onContentChange: vi.fn(),
    ...overrides,
  };
}

describe('EditorYaml', () => {
  it('shows placeholder when no content and no path', () => {
    render(<EditorYaml {...makeProps()} />);
    expect(screen.getByText(/Select a workflow file or press/)).toBeInTheDocument();
    expect(screen.getByText('Cmd+O')).toBeInTheDocument();
  });

  it('renders Monaco editor when selectedPath is set', () => {
    render(<EditorYaml {...makeProps({ selectedPath: 'test.yaml', content: 'name: test' })} />);
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument();
  });

  it('renders Monaco editor when content has text', () => {
    render(<EditorYaml {...makeProps({ content: 'name: workflow' })} />);
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument();
  });

  it('passes YAML content to Monaco', () => {
    render(<EditorYaml {...makeProps({ content: 'steps:\n  - a', selectedPath: 'x.yaml' })} />);
    const editor = screen.getByTestId('monaco-editor') as HTMLTextAreaElement;
    expect(editor.value).toBe('steps:\n  - a');
  });
});
