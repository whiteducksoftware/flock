import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import MessageNode from './MessageNode';
import { NodeProps } from '@xyflow/react';

// UI Optimization Migration (Phase 4.1 - Spec 002): MessageNodeData removed, use Record<string, any>
type MessageNodeData = Record<string, any>;

describe('MessageNode', () => {
  const createNodeProps = (data: MessageNodeData, selected = false): NodeProps =>
    ({
      id: 'msg-1',
      data,
      selected,
      type: 'message',
      isConnectable: true,
      dragging: false,
      zIndex: 0,
      selectable: true,
      deletable: true,
      draggable: true,
    }) as unknown as NodeProps;

  it('should render artifact type', () => {
    const data: MessageNodeData = {
      artifactType: 'Movie',
      payloadPreview: '{"title": "Test Movie"}',
      payload: { title: 'Test Movie' },
      producedBy: 'movie',
      consumedBy: ['tagline'],
      timestamp: Date.now(),
    };

    render(
      <ReactFlowProvider>
        <MessageNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText('Movie')).toBeInTheDocument();
  });

  it('should render produced by', () => {
    const data: MessageNodeData = {
      artifactType: 'Movie',
      payloadPreview: '{"title": "Test Movie"}',
      payload: { title: 'Test Movie' },
      producedBy: 'movie',
      consumedBy: [],
      timestamp: Date.now(),
    };

    render(
      <ReactFlowProvider>
        <MessageNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    // Text is split across elements: <div>by: <span>movie</span></div>
    // Use getByText with function matcher to find text across elements
    expect(screen.getByText((_content, element) => {
      return element?.textContent === 'by: movie';
    })).toBeInTheDocument();
  });
});
