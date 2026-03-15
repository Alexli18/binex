import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { EditorCanvas, type EditorCanvasProps } from './EditorCanvas';

// Mock ReactFlow — it requires browser APIs not available in jsdom
vi.mock('reactflow', () => {
  const ReactFlowProvider = ({ children }: { children: React.ReactNode }) => <div>{children}</div>;
  const useReactFlow = () => ({ screenToFlowPosition: vi.fn(() => ({ x: 0, y: 0 })) });
  const addEdge = vi.fn((conn: unknown, edges: unknown[]) => [...edges, conn]);
  const ReactFlow = (props: { nodes: unknown[]; edges: unknown[]; className?: string; children?: React.ReactNode }) => (
    <div data-testid="reactflow" className={props.className}>
      <span data-testid="node-count">{props.nodes.length}</span>
      <span data-testid="edge-count">{props.edges.length}</span>
      {props.children}
    </div>
  );
  const Background = () => <div data-testid="rf-background" />;
  const Controls = () => <div data-testid="rf-controls" />;
  return { default: ReactFlow, ReactFlowProvider, useReactFlow, addEdge, Background, Controls };
});

vi.mock('./NodePalette', () => ({
  NodePalette: () => <div data-testid="node-palette" />,
}));

vi.mock('./EditableNode', () => ({
  EditableNode: () => <div data-testid="editable-node" />,
}));

function makeProps(overrides: Partial<EditorCanvasProps> = {}): EditorCanvasProps {
  return {
    rfNodes: [],
    rfEdges: [],
    setRfNodes: vi.fn(),
    setRfEdges: vi.fn(),
    onRfNodesChange: vi.fn(),
    onRfEdgesChange: vi.fn(),
    onGraphChange: vi.fn(),
    ...overrides,
  };
}

describe('EditorCanvas', () => {
  it('renders ReactFlow and NodePalette', () => {
    render(<EditorCanvas {...makeProps()} />);
    expect(screen.getByTestId('reactflow')).toBeInTheDocument();
    expect(screen.getByTestId('node-palette')).toBeInTheDocument();
  });

  it('passes nodes and edges to ReactFlow', () => {
    const nodes = [{ id: 'a', position: { x: 0, y: 0 }, data: {} }];
    const edges = [{ id: 'e1', source: 'a', target: 'b' }];
    render(<EditorCanvas {...makeProps({ rfNodes: nodes as any, rfEdges: edges as any })} />);
    expect(screen.getByTestId('node-count').textContent).toBe('1');
    expect(screen.getByTestId('edge-count').textContent).toBe('1');
  });

  it('renders Background and Controls inside ReactFlow', () => {
    render(<EditorCanvas {...makeProps()} />);
    expect(screen.getByTestId('rf-background')).toBeInTheDocument();
    expect(screen.getByTestId('rf-controls')).toBeInTheDocument();
  });
});
