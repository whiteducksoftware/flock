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

  it('should render OpenClaw badge for OpenClaw agents', () => {
    const data: AgentNodeData = {
      name: 'remote-writer',
      status: 'idle',
      subscriptions: ['Idea'],
      sentCount: 0,
      recvCount: 0,
      isOpenClawAgent: true,
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );

    expect(screen.getByLabelText('OpenClaw agent')).toBeInTheDocument();
    expect(screen.getByText('🦞 OpenClaw')).toBeInTheDocument();
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

  it('should render a decision agent with its options and counts', () => {
    const data: AgentNodeData = {
      name: 'triage',
      status: 'idle',
      subscriptions: ['Ticket'],
      outputTypes: ['Decision[__main__.Route]'],
      sentByType: { 'Decision[__main__.Route]': 60 },
      sentCount: 60,
      recvCount: 60,
      decision: {
        question: 'Route',
        instructions: 'Which team should handle this ticket?',
        options: ['billing', 'tech'],
        threshold: 0.8,
        model: 'local/clef-flash',
        counts: { billing: 41, tech: 17, UNSURE: 2 },
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText('◆ Route')).toBeInTheDocument();
    expect(screen.getByText('billing')).toBeInTheDocument();
    expect(screen.getByText('41')).toBeInTheDocument();
    expect(screen.getByText('UNSURE')).toBeInTheDocument();
    expect(screen.getByText(/local\/clef-flash/)).toBeInTheDocument();
    expect(screen.queryByText('Decision[__main__.Route]')).not.toBeInTheDocument();
  });

  it('should label choice subscriptions with their handle', () => {
    const data: AgentNodeData = {
      name: 'billing',
      status: 'idle',
      subscriptions: ['Decision[__main__.Route]'],
      receivedByType: { 'Decision[__main__.Route]': 41 },
      typeLabels: { 'Decision[__main__.Route]': '◆ Route.billing' },
      sentCount: 41,
      recvCount: 41,
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText('◆ Route.billing')).toBeInTheDocument();
    expect(screen.queryByText('Decision[__main__.Route]')).not.toBeInTheDocument();
  });

  it('should show thumbnail lanes of decided images per option', () => {
    const thumb = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
    const data: AgentNodeData = {
      name: 'painter',
      status: 'idle',
      subscriptions: ['Swatch'],
      sentCount: 4,
      recvCount: 4,
      decision: {
        question: 'Color',
        options: ['red', 'blue'],
        threshold: 0.8,
        model: 'openai/gpt-6-luna',
        counts: { red: 9, blue: 1, UNSURE: 1 },
        samples: {
          red: [{ thumb, p: 0.97 }, { thumb, p: 0.95 }],
          UNSURE: [{ thumb, p: 0.5 }],
        },
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getAllByAltText(/^red · p 0\.9/)).toHaveLength(2);
    expect(screen.getByAltText('UNSURE · p 0.50')).toBeInTheDocument();
    expect(screen.getByText('+7')).toBeInTheDocument();
    expect(screen.queryAllByAltText(/^blue/)).toHaveLength(0);
  });
});
