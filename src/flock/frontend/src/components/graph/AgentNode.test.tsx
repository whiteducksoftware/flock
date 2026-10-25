import { afterEach, describe, it, expect, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { ReactFlowProvider, useStoreApi } from '@xyflow/react';
import { useLayoutEffect } from 'react';
import AgentNode from './AgentNode';
import { cardSizes } from './cardSizes';
import { MOVE_MS } from './animatePositions';
import { NodeProps } from '@xyflow/react';
import { useUIStore } from '../../store/uiStore';

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
    // yes from the left, no from the right, the unsure share between them
    expect(split.map((s) => s.dataset.option)).toEqual(['yes', 'UNSURE', 'no']);
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

  it('should lay out more than three questions in columns and widen the card', () => {
    const question = (name: string) => ({ name, kind: 'choice' as const, options: ['a', 'b'], counts: { a: 1, b: 0 } });
    const decider = (count: number): AgentNodeData => ({
      name: 'facets',
      status: 'idle',
      subscriptions: ['GameIdea'],
      sentCount: 6,
      recvCount: 1,
      decision: {
        model: 'azure/decision-1',
        threshold: 0.6,
        questions: ['Action', 'Board', 'Hidden', 'Time', 'Goal', 'Theme'].slice(0, count).map(question),
      },
    });

    const { container, unmount } = render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(decider(6))} />
      </ReactFlowProvider>
    );
    const card = container.querySelector('[data-status]') as HTMLElement;
    expect(card).toHaveAttribute('data-columns', '2');
    expect(card.style.getPropertyValue('--columns')).toBe('2');
    const columns = screen.getByTestId('decider-columns').children;
    expect([...columns].map((column) => column.textContent)).toEqual([
      expect.stringMatching(/^◆ Action.*◆ Board.*◆ Hidden/),
      expect.stringMatching(/^◆ Time.*◆ Goal.*◆ Theme/),
    ]);
    // The model and threshold stay below the columns, across the card
    expect(screen.getByTestId('decider-columns').nextElementSibling).toHaveTextContent('azure/decision-1 · threshold 0.60');
    unmount();

    const three = render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(decider(3))} />
      </ReactFlowProvider>
    );
    expect(three.container.querySelector('[data-status]')).not.toHaveAttribute('data-columns');
    expect(screen.queryByTestId('decider-columns')).not.toBeInTheDocument();
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

  it('should count the deliveries of a sink and show the last one', () => {
    const data: AgentNodeData = {
      name: 'billing-api',
      status: 'idle',
      subscriptions: ['Reply'],
      engineTag: '↗ POST /billing',
      sink: {
        method: 'POST',
        target: 'myapp:/billing',
        delivered: 12,
        failed: 1,
        last: { ok: false, status: 503, latencyMs: null, error: 'HTTP 503: down', at: '2026-10-12T08:24:00Z', correlationId: 'c-1' },
      },
    };

    render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );

    expect(screen.getByTestId('card-tag').textContent).toBe('↗ POST /billing');
    expect(screen.getByTestId('deliveries').textContent).toBe('12 delivered1 failedlast HTTP 503');
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

    it('says what failed and opens that run\'s traces in the timeline dock', () => {
      useUIStore.setState({ dockOpen: false, traceSearch: '' });
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

      expect(useUIStore.getState()).toMatchObject({ dockOpen: true, dockTab: 'traces', traceSearch: 'c-123' });
      useUIStore.setState({ dockOpen: false, traceSearch: '' });
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
      // The timer counts its fires from 0: iteration 14 is the 15th run
      expect(container.textContent).toContain('run 15 · last 23 h ago');
    });

    it('shows no run before the first one', () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2026-10-11T12:00:00Z'));
      const { container } = renderCard({
        scheduleSpec: { type: 'interval', interval: 'PT30S' },
        timerState: {
          iteration: 0,
          last_fire_time: null,
          next_fire_time: '2026-10-11T12:00:30Z',
          is_active: true,
          is_completed: false,
          is_stopped: false,
        },
      });

      expect(container.textContent).toContain('next in 30 s');
      expect(container.textContent).not.toContain('run ');
    });

    it('keeps two subscriptions to the same type apart', () => {
      const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
      // One subscription takes a ticket, the other two at once
      renderCard({ subscriptionGroups: [['app.Ticket'], ['app.Ticket', 'app.Ticket']], receivedByType: { 'app.Ticket': 2 } });

      expect(screen.getAllByTitle('app.Ticket')).toHaveLength(2);
      // React warns about duplicate keys on the console
      expect(errors.mock.calls.flat().join(' ')).not.toMatch(/same key/);
    });

    it('labels an AND gate and a join, and shows the open join', () => {
      renderCard({
        snapshotAt: performance.now(),
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
                  elapsed_seconds: 36,
                  expires_in_seconds: 24,
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
      // The bar's progress is readable without seeing it
      const progress = screen.getByRole('progressbar', { name: 'Join 9c34' });
      expect(progress.getAttribute('aria-valuenow')).toBe('1');
      expect(progress.getAttribute('aria-valuemax')).toBe('2');
    });

    it('shows a batch being collected, one cell per item', () => {
      renderCard({
        snapshotAt: performance.now(),
        logicOperations: [
          {
            subscription_index: 0,
            subscription_types: ['app.TeamReply'],
            batch: { strategy: 'hybrid', size: 5, timeout_seconds: 60 },
            waiting_state: {
              is_waiting: true,
              batch_state: { items_collected: 3, items_target: 5, timeout_seconds: 60, timeout_remaining_seconds: 41 },
            },
          },
        ],
      });

      const batch = screen.getByTestId('batch-wait');
      expect(batch.textContent).toBe('batch 3 / 5or in 0:41');
      expect(batch.querySelectorAll('.hatch')).toHaveLength(2);
      expect(batch.querySelector('[class*="urgent"]')).toBeNull();
    });

    it('counts a batch down on the local clock from the snapshot, amber under 30 s', () => {
      vi.useFakeTimers();
      renderCard({
        snapshotAt: performance.now(),
        logicOperations: [
          {
            subscription_index: 0,
            subscription_types: ['app.TeamReply'],
            batch: { strategy: 'timeout', timeout_seconds: 60 },
            waiting_state: {
              is_waiting: true,
              batch_state: { items_collected: 2, items_target: null, timeout_seconds: 60, timeout_remaining_seconds: 35 },
            },
          },
        ],
      });

      act(() => vi.advanceTimersByTime(6000));

      const batch = screen.getByTestId('batch-wait');
      expect(batch.textContent).toBe('batch 2 / ∞or in 0:29');
      expect(batch.querySelector('[class*="urgent"]')?.textContent).toBe('0:29');
    });
  });

  it('fades its card in when it folds back, instead of popping (#644)', () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ runs: [] }))));
    const animate = vi.fn();
    (HTMLElement.prototype as any).animate = animate;
    try {
      useUIStore.setState({ unfoldedNodeId: 'test-agent' });
      render(
        <ReactFlowProvider>
          <AgentNode {...createNodeProps({ name: 'test-agent', status: 'idle', subscriptions: ['app.Ticket'] })} />
        </ReactFlowProvider>,
      );
      animate.mockClear();
      act(() => useUIStore.setState({ unfoldedNodeId: null }));

      expect(screen.queryByTestId('unfolded')).toBeNull();
      expect(animate).toHaveBeenCalledWith([{ opacity: 0 }, { opacity: 1 }], expect.objectContaining({ duration: 200 }));
    } finally {
      delete (HTMLElement.prototype as any).animate;
      useUIStore.setState({ unfoldedNodeId: null });
      vi.unstubAllGlobals();
    }
  });

  it('opens the part a card grew by as the board makes room, instead of popping (#655)', () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ runs: [] }))));
    const animate = vi.fn();
    (HTMLElement.prototype as any).animate = animate;
    let height = 200;
    const tall = vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(() => height);
    try {
      const props = createNodeProps({ name: 'test-agent', status: 'idle', subscriptions: ['app.Ticket'] });
      const { rerender } = render(
        <ReactFlowProvider>
          <AgentNode {...props} />
        </ReactFlowProvider>,
      );
      animate.mockClear();
      // A new row of thumbnails: 60 px taller
      height = 260;
      rerender(
        <ReactFlowProvider>
          <AgentNode {...props} data={{ ...props.data, recvCount: 5 }} />
        </ReactFlowProvider>,
      );

      expect(animate).toHaveBeenCalledWith(
        [{ clipPath: 'inset(0px 0px 60px 0px)' }, { clipPath: 'inset(0px 0px 0px 0px)' }],
        expect.objectContaining({ duration: MOVE_MS }),
      );
    } finally {
      tall.mockRestore();
      delete (HTMLElement.prototype as any).animate;
      vi.unstubAllGlobals();
    }
  });

  it('lets go of the opening when the card shrinks again before it ended (#655)', () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ runs: [] }))));
    const cancel = vi.fn();
    (HTMLElement.prototype as any).animate = vi.fn(() => ({ cancel, onfinish: null }));
    let height = 200;
    const tall = vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(() => height);
    try {
      const props = createNodeProps({ name: 'test-agent', status: 'idle', subscriptions: ['app.Ticket'] });
      const view = (count: number) => (
        <ReactFlowProvider>
          <AgentNode {...props} data={{ ...props.data, recvCount: count }} />
        </ReactFlowProvider>
      );
      const { rerender } = render(view(1));
      height = 260;
      rerender(view(2));
      height = 200;
      rerender(view(3));

      expect(cancel).toHaveBeenCalled();
    } finally {
      tall.mockRestore();
      delete (HTMLElement.prototype as any).animate;
      vi.unstubAllGlobals();
    }
  });

  it('opens nothing when Auto-arrange is off: the board does not make room (#655)', () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ runs: [] }))));
    const animate = vi.fn();
    (HTMLElement.prototype as any).animate = animate;
    let height = 200;
    const tall = vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(() => height);
    useUIStore.setState({ autoLayoutEnabled: false });
    try {
      const props = createNodeProps({ name: 'test-agent', status: 'idle', subscriptions: ['app.Ticket'] });
      const { rerender } = render(
        <ReactFlowProvider>
          <AgentNode {...props} />
        </ReactFlowProvider>,
      );
      animate.mockClear();
      height = 260;
      rerender(
        <ReactFlowProvider>
          <AgentNode {...props} data={{ ...props.data, recvCount: 5 }} />
        </ReactFlowProvider>,
      );

      expect(animate).not.toHaveBeenCalled();
    } finally {
      useUIStore.setState({ autoLayoutEnabled: true });
      tall.mockRestore();
      delete (HTMLElement.prototype as any).animate;
      vi.unstubAllGlobals();
    }
  });

  it('keeps its card size up to date when the card resizes without rendering (fonts loading) (#655)', () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ runs: [] }))));
    const observers: ResizeObserverCallback[] = [];
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(callback: ResizeObserverCallback) {
          observers.push(callback);
        }
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    let height = 200;
    const tall = vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(() => height);
    try {
      render(
        <ReactFlowProvider>
          <AgentNode {...createNodeProps({ name: 'test-agent', status: 'idle', subscriptions: ['app.Ticket'] })} />
        </ReactFlowProvider>,
      );
      height = 230;
      act(() => observers.forEach((callback) => callback([], {} as ResizeObserver)));

      expect(cardSizes.get('test-agent')?.height).toBe(230);
    } finally {
      tall.mockRestore();
      vi.unstubAllGlobals();
    }
  });

  it('unfolds in place when it is the unfolded node, at any zoom', () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ runs: [] }))));
    useUIStore.setState({ unfoldedNodeId: 'test-agent' });
    const ZoomedOut = ({ children }: { children: React.ReactNode }) => {
      const store = useStoreApi();
      useLayoutEffect(() => {
        store.setState({ transform: [0, 0, 0.4] });
      }, [store]);
      return <>{children}</>;
    };

    render(
      <ReactFlowProvider>
        <ZoomedOut>
          <AgentNode {...createNodeProps({ name: 'test-agent', status: 'idle', subscriptions: ['app.Ticket'] })} />
        </ZoomedOut>
      </ReactFlowProvider>,
    );

    expect(screen.getByTestId('unfolded')).toBeTruthy();
    expect(screen.getByRole('tablist')).toBeTruthy();
    useUIStore.setState({ unfoldedNodeId: null });
    vi.unstubAllGlobals();
  });

  it('shows a chip while the timeline dock is expanded', () => {
    useUIStore.setState({ dockOpen: true });
    const { container } = render(
      <ReactFlowProvider>
        <AgentNode {...createNodeProps({ name: 'tech_support', status: 'idle', recvCount: 1, subscriptions: ['app.Ticket'] })} />
      </ReactFlowProvider>,
    );

    expect(container.textContent).toBe('tech_support1');
    useUIStore.setState({ dockOpen: false });
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
    // The dot's color is not the only way to learn the status
    expect(screen.getByRole('img', { name: 'idle' })).toBeTruthy();
  });
});
