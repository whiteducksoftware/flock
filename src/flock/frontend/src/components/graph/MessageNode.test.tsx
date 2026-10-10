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
});
