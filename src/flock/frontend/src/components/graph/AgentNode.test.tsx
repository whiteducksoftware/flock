import { afterEach, describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ReactFlowProvider, useStoreApi } from '@xyflow/react';
import { useLayoutEffect } from 'react';
import AgentNode from './AgentNode';
import { NodeProps } from '@xyflow/react';
import { useModuleStore } from '../../store/moduleStore';

// UI Optimization Migration (Phase 4.1 - Spec 002): AgentNodeData removed, use Record<string, any>
type AgentNodeData = Record<string, any>;

/** Text split over nested elements (a colored ◆), matched on its innermost element. */
const byText = (text: string) =>
  screen.getByText(
    (_, element) =>
      element?.textContent === text && ![...(element?.children ?? [])].some((child) => child.textContent === text),
  );

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

    expect(screen.getByTestId('card-tag').textContent).toBe('OpenClaw');
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

  it('should show each port with its count', () => {
    const data: AgentNodeData = {
      name: 'test-agent',
      status: 'idle',
      subscriptions: ['__main__.Movie'],
      outputTypes: ['__main__.Tagline'],
      receivedByType: { '__main__.Movie': 3 },
      sentByType: { '__main__.Tagline': 5 },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    // Type names without their module path; the full one in the tooltip
    expect(screen.getByTitle('__main__.Movie').textContent).toBe('inMovie3');
    expect(screen.getByTitle('__main__.Tagline').textContent).toBe('outTagline5');
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
    expect(byText('◆ Route')).toBeInTheDocument();
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
    expect(byText('◆ Route.billing')).toBeInTheDocument();
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
    expect(byText('◆ Route +2')).toBeInTheDocument();
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

  it('should show the escalation cascade of a decider', () => {
    const data: AgentNodeData = {
      name: 'triage',
      status: 'idle',
      subscriptions: ['Ticket'],
      sentCount: 2,
      recvCount: 2,
      decision: {
        model: 'fast',
        threshold: 0.9,
        escalate: ['medium', 'strong'],
        questions: [{ name: 'Route', kind: 'choice', options: ['billing', 'tech'], counts: { billing: 2, tech: 0 } }],
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText(/fast › medium › strong/)).toBeInTheDocument();
  });

  it('should show the models and the vote of an ensemble decider', () => {
    const data: AgentNodeData = {
      name: 'triage',
      status: 'idle',
      subscriptions: ['Ticket'],
      sentCount: 1,
      recvCount: 1,
      decision: {
        model: 'a',
        threshold: 0.9,
        ensemble: ['a', 'b', 'c'],
        vote: 'majority',
        questions: [{ name: 'Route', kind: 'choice', options: ['billing', 'tech'], counts: { billing: 1, tech: 0 } }],
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText(/majority of a \+ b \+ c/)).toBeInTheDocument();
  });

  it('should show how often a shadow model agrees', () => {
    const data: AgentNodeData = {
      name: 'triage',
      status: 'idle',
      subscriptions: ['Ticket'],
      sentCount: 3,
      recvCount: 3,
      decision: {
        model: 'live',
        threshold: 0.8,
        shadow: { model: 'candidate', compared: 3, agree: 2 },
        questions: [{ name: 'Route', kind: 'choice', options: ['billing', 'tech'], counts: { billing: 3, tech: 0 } }],
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByTestId('decider-shadow')).toHaveTextContent('shadow candidate · agrees 2/3');
  });

  it('should summarize the coverage of an aggregating agent', () => {
    const data: AgentNodeData = {
      name: 'coverage',
      status: 'idle',
      subscriptions: ['Decision'],
      sentCount: 3,
      recvCount: 3,
      coverage: { question: 'Controls', by: 'organisation', combine: 'any', groups: { passed: 1, failed: 10, UNSURE: 1 } },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    const summary = screen.getByTestId('coverage-summary');
    expect(summary).toHaveTextContent('Controls by organisation (any)');
    expect(summary).toHaveTextContent('1 passed · 10 failed · 1 unsure');
  });

  it('should count the item thresholds of a calibrated checklist decider', () => {
    const data: AgentNodeData = {
      name: 'audit',
      status: 'idle',
      subscriptions: ['Document'],
      sentCount: 1,
      recvCount: 1,
      decision: {
        model: 'fast',
        threshold: 0.8,
        itemThresholds: { mfa: 0.7, logs: 0.9 },
        questions: [{ name: 'Controls', kind: 'checklist', options: ['mfa', 'logs'], counts: {} }],
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText(/2 item thresholds/)).toBeInTheDocument();
    // The thresholds are in a disclosure, reachable without hover
    expect(screen.getByText('2 item thresholds').closest('summary')).not.toBeNull();
    expect(screen.getByText('mfa 0.70 · logs 0.90')).toBeInTheDocument();
  });

  it('should say item threshold for a single one', () => {
    const data: AgentNodeData = {
      name: 'audit',
      status: 'idle',
      subscriptions: ['Document'],
      sentCount: 1,
      recvCount: 1,
      decision: {
        model: 'fast',
        threshold: 0.8,
        itemThresholds: { mfa: 0.7 },
        questions: [{ name: 'Controls', kind: 'checklist', options: ['mfa'], counts: {} }],
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText(/1 item threshold$/)).toBeInTheDocument();
  });

  describe('states', () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    const renderCard = (data: AgentNodeData) =>
      render(
        <ReactFlowProvider>
          <AgentNode {...createNodeProps({ name: 'agent', status: 'idle', ...data })} />
        </ReactFlowProvider>,
      );

    it('shows the latest tokens of a running LLM agent with a caret', () => {
      const { container } = renderCard({ status: 'running', streamingTokens: ['we have', ' issued the refund'] });

      expect(screen.getByTestId('ticker').textContent).toBe('…we have issued the refund▍');
      expect(container.querySelector('[data-status="running"]')).not.toBeNull();
    });

    it('shows no ticker once the agent is idle again', () => {
      renderCard({ status: 'idle', streamingTokens: ['left over'] });

      expect(screen.queryByTestId('ticker')).toBeNull();
    });

    it('says what failed and opens that run in the trace viewer', () => {
      useModuleStore.setState({ instances: new Map() });
      renderCard({
        status: 'error',
        lastError: {
          type: 'RateLimitError',
          message: '429 Too Many Requests',
          at: '2026-10-11T13:20:44Z',
          correlationId: 'c-123',
        },
      });
      const time = new Date('2026-10-11T13:20:44Z').toLocaleTimeString([], { hour12: false });

      fireEvent.click(screen.getByRole('button', { name: `RateLimitError · ${time}` }));

      const [viewer] = [...useModuleStore.getState().instances.values()];
      expect(viewer).toMatchObject({ type: 'traceViewerJaeger', search: 'c-123' });
    });

    it('says only that it failed when the server does not say why', () => {
      renderCard({ status: 'error' });

      expect(screen.getByText('Failed')).toBeTruthy();
      expect(screen.queryByRole('button')).toBeNull();
    });

    it('shows a scheduled agent\'s schedule, next run, run number and last run', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-10-11T12:00:00Z'));
      const { container } = renderCard({
        scheduleSpec: { type: 'cron', cron: '0 9 * * 1-5' },
        timerState: {
          iteration: 14,
          last_fire_time: '2026-10-10T13:00:00Z',
          next_fire_time: '2026-10-12T04:34:00Z',
          is_active: true,
          is_completed: false,
          is_stopped: false,
        },
      });

      expect(screen.getByTestId('card-tag').textContent).toBe('0 9 * * 1-5');
      expect(container.textContent).toContain('next in 16 h 34 m');
      expect(container.textContent).toContain('run 14 · last 23 h ago');
    });

    it('labels an AND gate and a join, and shows the open join', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-10-11T12:00:36Z'));
      renderCard({
        subscriptionGroups: [['app.TeamReply', 'app.CustomerScore']],
        receivedByType: { 'app.TeamReply': 1 },
        logicOperations: [
          {
            subscription_index: 0,
            subscription_types: ['app.TeamReply', 'app.CustomerScore'],
            join: { window_type: 'time', window_value: 60, window_unit: 'seconds' },
            waiting_state: {
              is_waiting: true,
              correlation_groups: [
                {
                  correlation_key: "('9c34',)",
                  created_at: '2026-10-11T12:00:00Z',
                  collected_types: { 'app.TeamReply': 1 },
                  required_types: { 'app.TeamReply': 1, 'app.CustomerScore': 1 },
                  is_complete: false,
                  is_expired: false,
                },
              ],
            },
          },
        ],
      });

      expect(screen.getByTitle('app.CustomerScore').textContent).toBe('joinCustomerScore0');
      expect(screen.getByTestId('join-wait').textContent).toBe('9c340:24');
    });

    it('shows a batch being collected, one cell per item', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-10-11T12:00:19Z'));
      renderCard({
        logicOperations: [
          {
            subscription_index: 0,
            subscription_types: ['app.TeamReply'],
            batch: { strategy: 'hybrid', size: 5, timeout_seconds: 60 },
            waiting_state: {
              is_waiting: true,
              batch_state: { created_at: '2026-10-11T12:00:00Z', items_collected: 3, items_target: 5, timeout_seconds: 60 },
            },
          },
        ],
      });

      const batch = screen.getByTestId('batch-wait');
      expect(batch.textContent).toBe('batch 3 / 5or in 0:41');
      expect(batch.querySelectorAll('.hatch')).toHaveLength(2);
    });
  });

  it('shows a chip when the board is zoomed out', () => {
    const ZoomedOut = ({ children }: { children: React.ReactNode }) => {
      const store = useStoreApi();
      useLayoutEffect(() => {
        store.setState({ transform: [0, 0, 0.4] });
      }, [store]);
      return <>{children}</>;
    };

    const { container } = render(
      <ReactFlowProvider>
        <ZoomedOut>
          <AgentNode {...createNodeProps({ name: 'tech_support', status: 'idle', recvCount: 1, subscriptions: ['app.Ticket'] })} />
        </ZoomedOut>
      </ReactFlowProvider>,
    );

    expect(container.textContent).toBe('tech_support1');
    expect(screen.queryByTitle('app.Ticket')).toBeNull();
  });
});
