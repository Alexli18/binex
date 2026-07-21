import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ReactFlowProvider } from 'reactflow';
import { CustomNode } from './CustomNode';
import type { WorkflowNode } from '../../lib/yaml-to-graph';

function renderNode(data: WorkflowNode) {
  // CustomNode uses reactflow <Handle>, which needs a provider.
  return render(
    <ReactFlowProvider>
      <CustomNode
        id={data.id}
        type="custom"
        data={data}
        selected={false}
        zIndex={0}
        isConnectable
        xPos={0}
        yPos={0}
        dragging={false}
      />
    </ReactFlowProvider>,
  );
}

const base: WorkflowNode = { id: 'n', label: 'n', type: 'llm' };

describe('CustomNode', () => {
  it('shows a ×N runtime badge on foreach nodes', () => {
    renderNode({ ...base, id: 'work', label: 'work', foreach: 'plan' });
    expect(screen.getByText(/×N runtime/)).toBeInTheDocument();
  });

  it('has no badge on ordinary nodes', () => {
    renderNode(base);
    expect(screen.queryByText(/×N runtime/)).not.toBeInTheDocument();
  });
});
