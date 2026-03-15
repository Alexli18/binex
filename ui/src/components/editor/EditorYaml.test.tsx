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

// Mock WorkflowGraph
vi.mock('@/components/dag/WorkflowGraph', () => ({
  WorkflowGraph: (props: { nodes: unknown[]; edges: unknown[] }) => (
    <div data-testid="workflow-graph" data-nodes={props.nodes.length} data-edges={props.edges.length} />
  ),
}));

function makeProps(overrides: Partial<EditorYamlProps> = {}): EditorYamlProps {
  return {
    content: '',
    selectedPath: null,
    graphNodes: [],
    graphEdges: [],
    onContentChange: vi.fn(),
    ...overrides,
  };
}

describe('EditorYaml', () => {
  it('shows placeholder when no content and no path', () => {
    render(<EditorYaml {...makeProps()} />);
    expect(screen.getByText('Select a workflow file to edit')).toBeInTheDocument();
  });

  it('renders Monaco editor when selectedPath is set', () => {
    render(<EditorYaml {...makeProps({ selectedPath: 'test.yaml', content: 'name: test' })} />);
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument();
  });

  it('renders Monaco editor when content has text', () => {
    render(<EditorYaml {...makeProps({ content: 'name: workflow' })} />);
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument();
  });

  it('shows DAG preview when graphNodes exist', () => {
    const graphNodes = [{ id: 'a', label: 'A', type: 'llm', status: 'pending' }];
    render(<EditorYaml {...makeProps({ graphNodes: graphNodes as any, content: 'x' })} />);
    expect(screen.getByTestId('workflow-graph')).toBeInTheDocument();
  });

  it('shows DAG placeholder when no nodes and content', () => {
    render(<EditorYaml {...makeProps({ content: 'name: test' })} />);
    expect(screen.getByText('No nodes found in workflow')).toBeInTheDocument();
  });

  it('shows generic DAG placeholder when no content', () => {
    render(<EditorYaml {...makeProps({ selectedPath: 'test.yaml', content: '' })} />);
    expect(screen.getByText('DAG preview will appear here')).toBeInTheDocument();
  });

  it('passes YAML content to Monaco', () => {
    render(<EditorYaml {...makeProps({ content: 'steps:\n  - a', selectedPath: 'x.yaml' })} />);
    const editor = screen.getByTestId('monaco-editor') as HTMLTextAreaElement;
    expect(editor.value).toBe('steps:\n  - a');
  });
});
