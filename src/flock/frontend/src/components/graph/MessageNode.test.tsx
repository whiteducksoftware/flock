import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import MessageNode from './MessageNode';
import { useGraphStore } from '../../store/graphStore';
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

  it('should render a decision as probability bars', () => {
    const data: MessageNodeData = {
      artifactType: 'Decision[__main__.Route]',
      payload: { choice: 'billing' },
      producedBy: 'triage',
      consumedBy: ['billing'],
      timestamp: Date.now(),
      decision: {
        question: 'Route',
        choice: 'billing',
        bestGuess: 'billing',
        probabilities: { tech: 0.04, billing: 0.94, shipping: 0.02 },
        confidence: 0.9,
        threshold: 0.8,
        model: 'local/clef-flash',
        latencyMs: 84.2,
      },
    };

    render(
      <ReactFlowProvider>
        <MessageNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    const options = screen.getAllByTestId('decision-option');
    expect(options.map((o) => o.dataset.option)).toEqual(['billing', 'tech', 'shipping']);
    expect(options[0]?.dataset.chosen).toBe('true');
    expect(screen.getByText('94%')).toBeInTheDocument();
    expect(screen.getByText(/threshold 0\.80/)).toBeInTheDocument();
    expect(screen.getByText(/local\/clef-flash · 84 ms/)).toBeInTheDocument();
  });

  it('should mark an unsure decision and its best guess', () => {
    const data: MessageNodeData = {
      artifactType: 'Decision[__main__.Route]',
      payload: { choice: 'UNSURE' },
      producedBy: 'triage',
      consumedBy: ['supervisor'],
      timestamp: Date.now(),
      decision: {
        question: 'Route',
        choice: 'UNSURE',
        bestGuess: 'billing',
        probabilities: { billing: 0.53, shipping: 0.31, tech: 0.16 },
        confidence: 0.4,
        threshold: 0.8,
        model: 'fake',
        latencyMs: 1,
      },
    };

    render(
      <ReactFlowProvider>
        <MessageNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByText(/UNSURE/)).toBeInTheDocument();
    const options = screen.getAllByTestId('decision-option');
    expect(options.every((o) => o.dataset.chosen === 'false')).toBe(true);
    expect(options[0]?.dataset.bestGuess).toBe('true');
  });

  it('should show image thumbnails for image fields', () => {
    const data: MessageNodeData = {
      artifactType: 'Swatch',
      payload: { name: 'red one', photo: '🖼 image/jpeg · 4 KB' },
      producedBy: 'external',
      consumedBy: [],
      timestamp: Date.now(),
      images: [{ path: 'photo', mime: 'image/jpeg', bytes: 4096, thumb: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==' }],
    };

    render(
      <ReactFlowProvider>
        <MessageNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByAltText('photo')).toHaveAttribute('src', 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==');
    expect(screen.getByText(/photo · image\/jpeg · 4 KB/)).toBeInTheDocument();
  });

  it('should show the decided image next to the probability bars', () => {
    const data: MessageNodeData = {
      artifactType: 'Decision[__main__.Color]',
      payload: { choice: 'red' },
      producedBy: 'painter',
      consumedBy: [],
      timestamp: Date.now(),
      decision: {
        question: 'Color',
        choice: 'red',
        bestGuess: 'red',
        probabilities: { red: 0.97, blue: 0.03 },
        confidence: 0.97,
        threshold: 0.8,
        model: 'openai/gpt-6-luna',
        latencyMs: 300,
        subjectThumb: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
      },
    };

    render(
      <ReactFlowProvider>
        <MessageNode {...createNodeProps(data)} />
      </ReactFlowProvider>
    );
    expect(screen.getByAltText('decided image')).toHaveAttribute('src', 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==');
    expect(screen.getAllByTestId('decision-option')).toHaveLength(2);
  });

  const decisionNode = (decision: Record<string, unknown>): MessageNodeData => ({
    artifactType: `Decision[__main__.${decision.question}]`,
    payload: { choice: decision.choice },
    producedBy: 'triage',
    consumedBy: [],
    timestamp: Date.now(),
    decision,
  });

  it('should render a yes/no decision as one split bar with the unsure zone', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Urgent',
              kind: 'yesno',
              choice: 'yes',
              bestGuess: 'yes',
              probabilities: { yes: 0.9, no: 0.1 },
              confidence: 0.9,
              threshold: 0.8,
              model: 'azure/decision-1',
              latencyMs: 170,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByText('◆ Urgent: yes')).toBeInTheDocument();
    const bar = screen.getByTestId('decision-yesno');
    expect(bar.dataset.yes).toBe('0.9');
    expect(screen.getByText('yes 90%')).toBeInTheDocument();
    expect(screen.getByText('no 10%')).toBeInTheDocument();
    expect(screen.getByTestId('decision-unsure-zone').style.left).toBe('20%');
  });

  it('should render a scale decision as ordered levels with the weighted score', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Anger',
              kind: 'scale',
              choice: 'angry',
              bestGuess: 'angry',
              probabilities: { furious: 0.3, angry: 0.6, annoyed: 0.1, calm: 0.0 },
              levels: ['calm', 'annoyed', 'angry', 'furious'],
              confidence: 0.6,
              threshold: null,
              model: 'openai/gpt-6-luna',
              latencyMs: 300,
              score: 2.2,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    const options = screen.getAllByTestId('decision-option');
    expect(options.map((o) => o.dataset.option)).toEqual(['calm', 'annoyed', 'angry', 'furious']);
    expect(options[2]?.dataset.chosen).toBe('true');
    expect(screen.getByText('◆ Anger: angry · score 2.20')).toBeInTheDocument();
    expect(screen.getByTestId('decision-score').style.left).toBe(`${((2.2 + 0.5) / 4) * 100}%`);
  });

  it('should show a refused decision without bars', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Urgent',
              kind: 'yesno',
              choice: 'UNSURE',
              bestGuess: null,
              probabilities: {},
              confidence: null,
              threshold: null,
              model: 'openai/gpt-6-luna',
              latencyMs: 250,
              score: null,
              refused: true,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByText('◆ Urgent: refused')).toBeInTheDocument();
    expect(screen.queryByTestId('decision-yesno')).not.toBeInTheDocument();
    expect(screen.queryAllByTestId('decision-option')).toHaveLength(0);
  });

  it('should render a checklist decision as a grid of item results', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Controls',
              kind: 'checklist',
              choice: 'failed',
              bestGuess: 'failed',
              probabilities: { mfa: 0.98, review: 0.04, leaver: 0.7 },
              items: ['mfa', 'review', 'leaver', 'backup'],
              results: { mfa: 'yes', review: 'no', leaver: 'UNSURE', backup: 'UNSURE' },
              refusedItems: ['backup'],
              confidence: null,
              threshold: 0.9,
              model: 'azure/decision-1',
              latencyMs: 560,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByText('◆ Controls: failed · 1 yes · 1 no · 2 unsure')).toBeInTheDocument();
    const cells = screen.getAllByTestId('checklist-cell');
    expect(cells.map((c) => c.dataset.result)).toEqual(['yes', 'no', 'UNSURE', 'UNSURE']);
    expect(cells[0]).toHaveAttribute('title', 'mfa · yes · p 0.98');
    expect(cells[3]).toHaveAttribute('title', 'backup · refused');
    // Screen readers get each item's result as text, not only as a color
    expect(screen.getByRole('img', { name: 'mfa · yes · p 0.98' })).toBe(cells[0]);
    expect(screen.getByRole('group', { name: 'Controls items' })).toBeInTheDocument();
  });

  it('should show tournament rounds above the final probabilities', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Control',
              kind: 'choice',
              choice: 'c_42',
              bestGuess: 'c_42',
              probabilities: { c_42: 0.8, c_41: 0.1, c_07: 0.05, c_13: 0.05 },
              rounds: [
                { candidates: 1000, groups: 50, survivors: Array.from({ length: 100 }, (_, i) => `s${i}`) },
                { candidates: 100, groups: 5, survivors: ['c_42', 'c_41', 'c_07', 'c_13'] },
              ],
              confidence: 0.8,
              threshold: null,
              model: 'azure/decision-1',
              latencyMs: 900,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    const rounds = screen.getAllByTestId('tournament-round');
    expect(rounds.map((r) => r.textContent)).toEqual([
      '1000 options · 50 groups → 100',
      '100 options · 5 groups → 4',
    ]);
    expect(screen.getAllByTestId('decision-option')).toHaveLength(4);
  });

  it('should show the most probable options of a large choice', () => {
    const probabilities: Record<string, number> = { c_42: 0.9, c_07: 0.05 };
    for (let i = 0; i < 98; i++) probabilities[`x_${i}`] = 0.05 / 98;
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Control',
              kind: 'choice',
              choice: 'c_42',
              bestGuess: 'c_42',
              probabilities,
              confidence: 0.9,
              threshold: null,
              model: 'azure/decision-1',
              latencyMs: 180,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    const options = screen.getAllByTestId('decision-option');
    expect(options).toHaveLength(8);
    expect(options[0]?.dataset.option).toBe('c_42');
    expect(screen.getByText('+92 more options, each below 1%')).toBeInTheDocument();
  });

  it('should open the tournament bracket from the decision card', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Control',
              kind: 'choice',
              choice: 'c_42',
              bestGuess: 'c_42',
              probabilities: { c_42: 0.8, c_07: 0.2 },
              rounds: [
                {
                  candidates: 40,
                  groups: 2,
                  group_size: 20,
                  refused_groups: 0,
                  survivors: ['c_07', 'c_42'],
                  group_results: [
                    { size: 20, refused: false, top: [['c_07', 0.9], ['c_01', 0.1]] },
                    { size: 20, refused: false, top: [['c_42', 0.8], ['c_33', 0.1]] },
                  ],
                },
              ],
              confidence: 0.8,
              threshold: null,
              model: 'fake',
              latencyMs: 400,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /bracket/i }));
    expect(screen.getByRole('dialog', { name: /tournament/i })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('should name how many candidates a restricted decision chose among', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Control',
              kind: 'choice',
              choice: 'sup_05',
              bestGuess: 'sup_05',
              probabilities: { sup_05: 0.9, acc_01: 0.06, phy_03: 0.04 },
              candidates: ['acc_01', 'phy_03', 'sup_05'],
              confidence: 0.9,
              threshold: null,
              model: 'azure/decision-1',
              latencyMs: 150,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByText(/among 3 candidates/)).toBeInTheDocument();
  });

  it('should show the escalation trail of a decision answered one tier up', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Route',
              kind: 'choice',
              choice: 'billing',
              bestGuess: 'billing',
              probabilities: { billing: 0.97, tech: 0.03 },
              tier: 2,
              attempts: [
                { model: 'fast', choice: 'billing', probabilities: { billing: 0.6, tech: 0.4 }, confidence: 0.6, refused: false },
                { model: 'medium', choice: null, probabilities: {}, confidence: null, refused: true },
              ],
              confidence: 0.97,
              threshold: 0.9,
              model: 'strong',
              latencyMs: 700,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    const attempts = screen.getAllByTestId('escalation-attempt');
    expect(attempts.map((a) => a.textContent)).toEqual(['fast · billing 0.60', 'medium · refused']);
    expect(screen.getByTestId('escalation-final')).toHaveTextContent('strong · tier 2');
  });

  it('should fall back to the confidence when an attempt has no probability for its choice', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Route',
              kind: 'choice',
              choice: 'billing',
              bestGuess: 'billing',
              probabilities: { billing: 0.97, tech: 0.03 },
              tier: 1,
              attempts: [{ model: 'custom', choice: 'tech', probabilities: {}, confidence: 0.55, refused: false }],
              confidence: 0.97,
              threshold: 0.9,
              model: 'strong',
              latencyMs: 700,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByTestId('escalation-attempt')).toHaveTextContent('custom · tech 0.55');
  });

  it('should count the escalated items of a checklist attempt', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Controls',
              kind: 'checklist',
              choice: 'passed',
              bestGuess: 'passed',
              probabilities: { mfa: 0.98, backup: 0.97 },
              items: ['mfa', 'backup'],
              results: { mfa: 'yes', backup: 'yes' },
              refusedItems: [],
              tier: 1,
              attempts: [{ model: 'fast', results: { backup: 'UNSURE' } }],
              confidence: null,
              threshold: 0.9,
              model: 'strong',
              latencyMs: 400,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByTestId('escalation-attempt')).toHaveTextContent('fast · 1 unsure');
    expect(screen.getByTestId('escalation-attempt')).toHaveAttribute('title', expect.stringContaining('backup'));
  });

  it('should show every vote of an ensemble decision', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Route',
              kind: 'choice',
              choice: 'billing',
              bestGuess: 'billing',
              probabilities: { billing: 0.71, tech: 0.29 },
              votes: [
                { model: 'a', choice: 'billing', probabilities: { billing: 0.95, tech: 0.05 }, confidence: 0.95, refused: false },
                { model: 'b', choice: 'tech', probabilities: { billing: 0.08, tech: 0.92 }, confidence: 0.92, refused: false },
                { model: 'c', choice: 'tech', probabilities: { billing: 0.2, tech: 0.8 }, confidence: 0.8, refused: false },
                { model: 'd', choice: null, probabilities: {}, confidence: null, refused: true },
              ],
              confidence: 0.71,
              threshold: 0.9,
              model: 'a + b + c',
              latencyMs: 300,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    const votes = screen.getAllByTestId('decision-vote');
    expect(votes.map((v) => v.textContent)).toEqual(['a · billing 0.95', 'b · tech 0.92', 'c · tech 0.80', 'd · refused']);
    // Firm and agreeing, firm but different, below the threshold, refused
    expect(votes.map((v) => v.getAttribute('data-vote'))).toEqual(['agrees', 'differs', 'unsure', 'unsure']);
  });

  const shadowedDecision = (shadow: Record<string, unknown>) =>
    decisionNode({
      question: 'Route',
      kind: 'choice',
      choice: 'billing',
      bestGuess: 'billing',
      probabilities: { billing: 0.95, tech: 0.05 },
      shadow,
      confidence: 0.95,
      threshold: 0.8,
      model: 'live',
      latencyMs: 200,
      score: null,
      refused: false,
    });

  it('should show where the shadow model would have routed differently', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            shadowedDecision({
              model: 'candidate',
              choice: 'tech',
              best_guess: 'tech',
              probabilities: { billing: 0.1, tech: 0.9 },
              confidence: 0.9,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    const shadow = screen.getByTestId('decision-shadow');
    expect(shadow).toHaveTextContent('shadow candidate · tech 0.90');
    expect(shadow).toHaveAttribute('data-agrees', 'false');
  });

  it('should show an unsure shadow with its best guess', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            shadowedDecision({
              model: 'candidate',
              choice: 'UNSURE',
              best_guess: 'billing',
              probabilities: { billing: 0.6, tech: 0.4 },
              confidence: 0.6,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByTestId('decision-shadow')).toHaveTextContent('shadow candidate · UNSURE (billing 0.60)');
  });

  it('should show a failed shadow with its error', () => {
    render(
      <ReactFlowProvider>
        <MessageNode {...createNodeProps(shadowedDecision({ model: 'candidate', error: 'TimeoutError: no reply' }))} />
      </ReactFlowProvider>
    );
    const shadow = screen.getByTestId('decision-shadow');
    expect(shadow).toHaveTextContent('shadow candidate · error');
    expect(shadow).toHaveAttribute('title', 'TimeoutError: no reply');
  });

  it('should name the section a long-document decision came from', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Topic',
              kind: 'choice',
              choice: 'backup',
              bestGuess: 'backup',
              probabilities: { access: 0.05, backup: 0.95 },
              sections: { field: 'text', spans: [[0, 30], [32, 60], [62, 90]], answeredBy: { Topic: 1 } },
              confidence: 0.95,
              threshold: 0.9,
              model: 'fake',
              latencyMs: 100,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByText(/3 sections of text · from section 2/)).toBeInTheDocument();
  });

  it('should name the section of each checklist item', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Controls',
              kind: 'checklist',
              choice: 'passed',
              bestGuess: 'passed',
              probabilities: { mfa: 0.97, backup: 0.96 },
              results: { mfa: 'yes', backup: 'yes', logs: 'UNSURE' },
              items: ['mfa', 'backup', 'logs'],
              refusedItems: ['logs'],
              sections: { field: 'text', spans: [[0, 30], [32, 60]], answeredBy: { mfa: 0, backup: 1, logs: 1 } },
              confidence: null,
              threshold: 0.9,
              model: 'fake',
              latencyMs: 100,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByRole('img', { name: 'backup · yes · p 0.96 · section 2' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'logs · refused · section 2' })).toBeInTheDocument();
    expect(screen.getByText(/2 sections of text/)).toBeInTheDocument();
  });

  const unsureRoute = (extra: Record<string, unknown> = {}) =>
    decisionNode({
      question: 'Route',
      kind: 'choice',
      choice: 'UNSURE',
      bestGuess: 'billing',
      probabilities: { billing: 0.55, tech: 0.45 },
      confidence: 0.55,
      threshold: 0.8,
      model: 'fast',
      latencyMs: 100,
      score: null,
      refused: false,
      ...extra,
    });

  it('should let a person review an unsure decision', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ artifact_id: 'r-1', choice: 'tech', correlation_id: 'c-1' }), { status: 200 })
    );
    const refreshSpy = vi.spyOn(useGraphStore.getState(), 'scheduleRefresh').mockImplementation(() => {});
    try {
      render(
        <ReactFlowProvider>
          <MessageNode {...createNodeProps(unsureRoute())} />
        </ReactFlowProvider>
      );
      // Options by probability; the best guess first
      const buttons = screen.getAllByRole('button', { name: /^Review as / });
      expect(buttons.map((b) => b.textContent)).toEqual(['billing', 'tech']);

      fireEvent.click(screen.getByRole('button', { name: 'Review as tech' }));

      await waitFor(() => expect(screen.getByTestId('decision-review')).toHaveTextContent('reviewed as tech'));
      // The review is a new decision: the graph refreshes to show it
      expect(refreshSpy).toHaveBeenCalled();
      const [url, init] = fetchSpy.mock.calls[0] ?? [];
      expect(url).toBe('/api/control/decisions/msg-1/review');
      expect(JSON.parse(String((init as RequestInit).body))).toEqual({ choice: 'tech' });
    } finally {
      fetchSpy.mockRestore();
      refreshSpy.mockRestore();
    }
  });

  it('should offer the question options to review a refused decision', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            unsureRoute({ bestGuess: null, probabilities: {}, refused: true, options: ['billing', 'tech'] })
          )}
        />
      </ReactFlowProvider>
    );
    const buttons = screen.getAllByRole('button', { name: /^Review as / });
    expect(buttons.map((b) => b.textContent)).toEqual(['billing', 'tech']);
  });

  it('should offer the options a sparse answer left out', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            unsureRoute({ probabilities: { billing: 0.6 }, options: ['billing', 'tech', 'shipping'] })
          )}
        />
      </ReactFlowProvider>
    );
    const buttons = screen.getAllByRole('button', { name: /^Review as / });
    expect(buttons.map((b) => b.textContent)).toEqual(['billing', 'tech', 'shipping']);
  });

  it('should show the review of a reviewed decision instead of the controls', () => {
    render(
      <ReactFlowProvider>
        <MessageNode {...createNodeProps(unsureRoute({ review: { choice: 'tech', by: 'alice' } }))} />
      </ReactFlowProvider>
    );
    expect(screen.getByTestId('decision-review')).toHaveTextContent('reviewed as tech by alice');
    expect(screen.queryAllByRole('button', { name: /^Review as / })).toHaveLength(0);
  });

  it('should name the decision a review replaces', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            unsureRoute({ choice: 'tech', bestGuess: 'tech', probabilities: { tech: 1 }, model: 'alice', reviewOf: 'abcdef12-3456-7890' })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByText(/review of abcdef12/)).toBeInTheDocument();
    expect(screen.queryAllByRole('button', { name: /^Review as / })).toHaveLength(0);
  });

  it('should show a coverage as a checklist grid for its group', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps({
            artifactType: 'Coverage[__main__.Controls]',
            payload: { group: 'acme' },
            producedBy: 'coverage',
            consumedBy: [],
            timestamp: Date.now(),
            coverage: {
              question: 'Controls',
              kind: 'checklist',
              group: 'acme',
              combine: 'any',
              documents: 2,
              choice: 'UNSURE',
              results: { mfa: 'yes', backup: 'yes', logs: 'UNSURE' },
              items: ['mfa', 'backup', 'logs'],
              probabilities: {},
              refusedItems: [],
            },
          })}
        />
      </ReactFlowProvider>
    );
    const card = screen.getByTestId('coverage-card');
    expect(card).toHaveTextContent('Controls coverage of acme: UNSURE');
    expect(card).toHaveTextContent('2 yes · 0 no · 1 unsure');
    expect(card).toHaveTextContent('any of 2 documents');
    expect(screen.getByRole('group', { name: 'Controls items' })).toBeInTheDocument();
  });

  it('should show an explanation as text instead of JSON', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps({
            artifactType: 'flock.decisions.explain.Explanation',
            payload: { explanation: 'Both a crash and a charge.' },
            producedBy: 'explainer',
            consumedBy: [],
            timestamp: Date.now(),
            explanation: {
              explanation: 'Both a crash and a charge.',
              missing: 'Which came first.',
              model: 'openai/gpt-4.1',
              questions: ['Route'],
            },
          })}
        />
      </ReactFlowProvider>
    );
    const card = screen.getByTestId('explanation-card');
    expect(card).toHaveTextContent('Explains Route');
    expect(card).toHaveTextContent('Both a crash and a charge.');
    expect(card).toHaveTextContent('Would settle it: Which came first.');
    expect(card).toHaveTextContent('openai/gpt-4.1');
  });

  it('should show the explanation of a decision on its card', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Route',
              kind: 'choice',
              choice: 'UNSURE',
              bestGuess: 'billing',
              probabilities: { billing: 0.55, tech: 0.45 },
              explanation: {
                explanation: 'Both a crash and a charge.',
                missing: 'Which came first.',
                model: 'openai/gpt-4.1',
                by: 'explainer',
              },
              confidence: 0.55,
              threshold: 0.8,
              model: 'fast',
              latencyMs: 100,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    const note = screen.getByTestId('decision-explanation');
    expect(note).toHaveTextContent('explainer: Both a crash and a charge.');
    expect(note).not.toHaveTextContent('Which came first.');
    // The whole explanation opens with a focusable control, not only on hover
    const toggle = screen.getByRole('button', { name: 'Show the whole explanation' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(note).toHaveTextContent('Would settle it: Which came first.');
    expect(screen.getByRole('button', { name: 'Show less of the explanation' })).toHaveAttribute('aria-expanded', 'true');
  });

  it('should summarize the checklist votes of an ensemble', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Controls',
              kind: 'checklist',
              choice: 'UNSURE',
              bestGuess: 'passed',
              probabilities: { mfa: 0.68, backup: 0.52 },
              items: ['mfa', 'backup'],
              results: { mfa: 'yes', backup: 'UNSURE' },
              refusedItems: [],
              votes: [
                { model: 'a', results: { mfa: 'yes', backup: 'no' } },
                { model: 'b', results: { mfa: 'yes', backup: 'UNSURE' } },
                { model: 'c', results: { mfa: 'UNSURE', backup: 'UNSURE' } },
              ],
              confidence: null,
              threshold: 0.9,
              model: 'a + b',
              latencyMs: 400,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    const votes = screen.getAllByTestId('decision-vote');
    expect(votes[0]).toHaveTextContent('a · 1 yes · 1 no');
    // a contradicts the result for backup, b matches every item, c gave no firm answer
    expect(votes.map((v) => v.getAttribute('data-vote'))).toEqual(['differs', 'agrees', 'unsure']);
  });

  it('should count an all-unsure checklist vote as no vote, even when every result is unsure', () => {
    render(
      <ReactFlowProvider>
        <MessageNode
          {...createNodeProps(
            decisionNode({
              question: 'Controls',
              kind: 'checklist',
              choice: 'UNSURE',
              bestGuess: 'passed',
              probabilities: { mfa: 0.6 },
              items: ['mfa'],
              results: { mfa: 'UNSURE' },
              refusedItems: [],
              votes: [{ model: 'a', results: { mfa: 'UNSURE' } }],
              confidence: null,
              threshold: 0.9,
              model: 'a + b',
              latencyMs: 400,
              score: null,
              refused: false,
            })
          )}
        />
      </ReactFlowProvider>
    );
    expect(screen.getByTestId('decision-vote')).toHaveAttribute('data-vote', 'unsure');
  });
});

