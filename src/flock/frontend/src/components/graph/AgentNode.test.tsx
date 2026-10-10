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
        model: 'local/clef-flash',
        threshold: 0.8,
        questions: [
          {
            name: 'Route',
            kind: 'choice',
            instructions: 'Which team should handle this ticket?',
            options: ['billing', 'tech'],
            counts: { billing: 41, tech: 17, UNSURE: 2 },
          },
        ],
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
        model: 'openai/gpt-6-luna',
        threshold: 0.8,
        questions: [
          {
            name: 'Color',
            kind: 'choice',
            options: ['red', 'blue'],
            counts: { red: 9, blue: 1, UNSURE: 1 },
            samples: {
              red: [{ thumb, p: 0.97 }, { thumb, p: 0.95 }],
              UNSURE: [{ thumb, p: 0.5 }],
            },
          },
        ],
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

  it('should render every question of a decider by its kind', () => {
    const data: AgentNodeData = {
      name: 'triage',
      status: 'idle',
      subscriptions: ['Ticket'],
      outputTypes: ['Decision[__main__.Route]', 'Decision[__main__.Urgent]', 'Decision[__main__.Anger]'],
      sentCount: 33,
      recvCount: 11,
      decision: {
        model: 'azure/decision-1',
        threshold: 0.8,
        questions: [
          {
            name: 'Route',
            kind: 'choice',
            options: ['billing', 'tech'],
            counts: { billing: 7, tech: 3, UNSURE: 1 },
          },
          {
            name: 'Urgent',
            kind: 'yesno',
            instructions: 'Does the customer need an answer today?',
            options: ['yes', 'no'],
            counts: { yes: 7, no: 3, UNSURE: 1 },
            refused: 1,
          },
          {
            name: 'Anger',
            kind: 'scale',
            options: ['calm', 'annoyed', 'angry', 'furious'],
            counts: { calm: 1, annoyed: 2, angry: 6, furious: 2, UNSURE: 0 },
            meanScore: 1.9,
          },
        ],
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    // Header badge: first question plus how many more
    expect(screen.getByText('◆ Route +2')).toBeInTheDocument();
    expect(screen.getByText('Urgent')).toBeInTheDocument();
    expect(screen.getByText('Anger')).toBeInTheDocument();

    const split = screen.getAllByTestId('yesno-segment');
    expect(split.map((s) => s.dataset.option)).toEqual(['yes', 'no', 'UNSURE']);
    expect(split[0]?.style.width).toBe(`${(7 / 11) * 100}%`);
    expect(screen.getByText('1 refused')).toBeInTheDocument();

    const levels = screen.getAllByTestId('scale-level');
    expect(levels.map((l) => l.dataset.option)).toEqual(['calm', 'annoyed', 'angry', 'furious']);
    expect(levels[2]?.dataset.count).toBe('6');
    expect(screen.getByTestId('scale-mean')).toHaveAttribute('title', 'mean score 1.90');
  });

  it('should render a checklist decider with outcomes, item strip and top gaps', () => {
    const data: AgentNodeData = {
      name: 'audit',
      status: 'idle',
      subscriptions: ['Document'],
      outputTypes: ['Decision[__main__.Controls]'],
      sentCount: 4,
      recvCount: 4,
      decision: {
        model: 'azure/decision-1',
        threshold: 0.8,
        questions: [
          {
            name: 'Controls',
            kind: 'checklist',
            options: ['mfa', 'review', 'leaver', 'backup'],
            counts: { passed: 1, failed: 2, UNSURE: 1 },
            itemStats: [
              [3, 1, 0],
              [1, 3, 0],
              [2, 1, 1],
              [0, 4, 0],
            ],
            descriptions: { mfa: 'MFA for remote access', review: 'Access reviews', leaver: 'Leavers lose access', backup: 'Daily backups' },
          },
        ],
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    const outcomes = screen.getAllByTestId('checklist-outcome');
    expect(outcomes.map((o) => o.dataset.option)).toEqual(['passed', 'failed', 'UNSURE']);
    const items = screen.getAllByTestId('checklist-item-stat');
    expect(items).toHaveLength(4);
    expect(items[0]).toHaveAttribute('title', 'mfa: 3 yes · 1 no · 0 unsure — MFA for remote access');
    // Items answered "no" most often
    const gaps = screen.getAllByTestId('checklist-gap');
    expect(gaps.map((g) => g.dataset.item)).toEqual(['backup', 'review', 'mfa']);
  });

  it('should compact deciders with many options and show the tournament', () => {
    const options = Array.from({ length: 60 }, (_, i) => `c_${String(i).padStart(2, '0')}`);
    const counts: Record<string, number> = Object.fromEntries(options.map((o) => [o, 0]));
    counts.c_42 = 5;
    counts.c_07 = 2;
    counts.c_13 = 1;
    const data: AgentNodeData = {
      name: 'mapper',
      status: 'idle',
      subscriptions: ['Evidence'],
      sentCount: 8,
      recvCount: 8,
      decision: {
        model: 'azure/decision-1',
        threshold: null,
        tournament: { groupSize: 20, keep: 2 },
        questions: [{ name: 'Control', kind: 'choice', options, counts }],
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText('c_42')).toBeInTheDocument();
    expect(screen.getByText('c_13')).toBeInTheDocument();
    expect(screen.queryByText('c_00')).not.toBeInTheDocument();
    expect(screen.getByText('+57 more options')).toBeInTheDocument();
    expect(screen.getByText(/tournament: groups of 20, keep 2/)).toBeInTheDocument();
  });
});

