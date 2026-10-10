import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
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
});

