import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import AgentNode from './AgentNode';
import { NodeProps } from '@xyflow/react';

// UI Optimization Migration (Phase 4.1 - Spec 002): AgentNodeData removed, use Record<string, any>
type AgentNodeData = Record<string, any>;

describe('AgentNode', () => {
  const createNodeProps = (data: AgentNodeData, selected = false): NodeProps =>
    ({
      id: 'test-agent',
      data,
      selected,
      type: 'agent',
      isConnectable: true,
      dragging: false,
      zIndex: 0,
      selectable: true,
      deletable: true,
      draggable: true,
    }) as unknown as NodeProps;

  it('should render agent name', () => {
    const data: AgentNodeData = {
      name: 'test-agent',
      status: 'idle',
      subscriptions: ['Movie'],
      sentCount: 5,
      recvCount: 3,
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText('test-agent')).toBeInTheDocument();
  });

  it('should render subscriptions', () => {
    const data: AgentNodeData = {
      name: 'test-agent',
      status: 'idle',
      subscriptions: ['Movie', 'Tagline'],
      sentCount: 5,
      recvCount: 3,
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText('Movie')).toBeInTheDocument();
    expect(screen.getByText('Tagline')).toBeInTheDocument();
  });

  it('should render sent and received counts', () => {
    const data: AgentNodeData = {
      name: 'test-agent',
      status: 'idle',
      subscriptions: [],
      sentCount: 5,
      recvCount: 3,
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText(/↑ 5/)).toBeInTheDocument();
    expect(screen.getByText(/↓ 3/)).toBeInTheDocument();
  });
});
