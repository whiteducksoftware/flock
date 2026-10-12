import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { Edge, Node } from '@xyflow/react';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import Blackboard from './Blackboard';


const artifact = (id: string, correlationId: string, type: string, producedBy: string, timestamp: number, data: Record<string, unknown> = {}): Node => ({
  id,
  type: 'message',
  position: { x: 0, y: 0 },
  data: { artifactType: type, producedBy, timestamp, correlationId, payload: {}, consumedBy: [], visibilityKind: 'Public', ...data },
});
const decision = (choice: string, probability: number, extra: Record<string, unknown> = {}) => ({
  decision: {
    question: 'Route',
    kind: 'choice',
    choice,
    bestGuess: null,
    probabilities: { [choice]: probability },
    confidence: probability,
    threshold: 0.8,
    model: 'azure/decision-1',
    latencyMs: 58,
    ...extra,
  },
});
const made = (source: string, target: string, agent: string): Edge => ({ id: `${source}__${target}`, source, target, type: 'transformation', data: { transformerAgent: agent } });

const nodes = [
  artifact('t1', 'aaaa1111-0000', 'app.SupportTicket', 'external', 1000, { payload: { subject: 'App crashes on login', message: 'It closes right after' } }),
  artifact('d1', 'aaaa1111-0000', 'Decision[app.Route]', 'triage', 1500, { ...decision('tech', 0.95), consumedBy: ['tech_support'] }),
  artifact('r1', 'aaaa1111-0000', 'app.TeamReply', 'tech_support', 4500, { payload: { team: 'tech', reply: 'Sorry about that' } }),
  artifact('t2', 'bbbb2222-0000', 'app.SupportTicket', 'external', 2000, { payload: { subject: 'Something odd with my account' } }),
  artifact('d2', 'bbbb2222-0000', 'Decision[app.Route]', 'triage', 2100, decision('UNSURE', 0.46, { bestGuess: 'shipping', probabilities: { shipping: 0.46, billing: 0.44 } })),
  artifact('t3', 'cccc3333-0000', 'app.SupportTicket', 'external', 3000, { payload: { subject: 'Refund not received' } }),
  artifact('s1', 'cccc3333-0000', 'app.TeamReply', 'billing_team', 3100, { isStreaming: true, streamingText: 'Hi, thanks for your patience' }),
];
const edges = [made('t1', 'd1', 'triage'), made('d1', 'r1', 'tech_support'), made('t2', 'd2', 'triage')];

const lane = (run: string) => screen.getByRole('region', { name: `Run ${run}` });

/**
 * jsdom lays nothing out: a lane's top and height come from these tables (a
 * running glide's offset in `shift`); what glides inside a lane (a card, the
 * header, an arrow) sits where `cards` says, 10 px down by default
 */
const layOut = (
  tops: Map<string, number>,
  {
    heights = new Map<string, number>(),
    shift = new Map<string, number>(),
    cards = new Map<string, { x: number; y: number; width?: number; height?: number }>(),
  } = {},
) =>
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    const slot = this.closest<HTMLElement>('[data-lane]');
    const label = slot?.querySelector('section')?.getAttribute('aria-label') ?? '';
    const top = (tops.get(label) ?? 0) + (shift.get(label) ?? 0);
    const item = this.dataset.glide;
    if (item) {
      const at = cards.get(item) ?? { x: 0, y: 10 };
      return { top: top + at.y, left: at.x, width: at.width ?? 200, height: at.height ?? 60 } as DOMRect;
    }
    return { top, left: 0, height: heights.get(label) ?? 100 } as DOMRect;
  });

describe('Blackboard', () => {
  beforeEach(() => {
    // React Flow (the graph) watches its sizes
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    useGraphStore.setState({
      viewMode: 'blackboard',
      nodes,
      edges,
      inFlight: new Map([['r-9', { agent: 'billing_team', types: ['app.SupportTicket'], artifacts: ['t3'], correlationId: 'cccc3333-0000' }]]),
      truncated: false,
    });
    useUIStore.setState({ blackboardView: 'lanes', needsReviewOnly: false, unfoldedArtifactId: null });
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url === '/api/v1/artifacts/d1?images=thumbnails&embed_meta=true'
          ? new Response(
              JSON.stringify({
                id: 'd1',
                type: 'Decision[app.Route]',
                payload: { choice: 'tech' },
                produced_by: 'triage',
                created_at: '2026-10-11T12:00:01Z',
                correlation_id: 'aaaa1111-0000',
                partition_key: null,
                tags: ['support'],
                visibility: { kind: 'Public' },
                visibility_kind: 'Public',
                consumed_by: ['tech_support'],
                consumptions: [{ artifact_id: 'd1', consumer: 'tech_support', run_id: '7f3a2b91-4c0d-4e2a-9b1e-3d5f6a7b8c9d', correlation_id: 'aaaa1111-0000', consumed_at: '2026-10-11T12:00:02Z' }],
              }),
            )
          : new Response('', { status: 404 }),
      ),
    );
  });

  afterEach(() => {
    // Also when a test fails before its own clean-up: geometry, styles, animations
    vi.restoreAllMocks();
    delete (HTMLElement.prototype as any).animate;
    vi.unstubAllGlobals();
    useGraphStore.setState(useGraphStore.getInitialState(), true);
    useUIStore.setState({ blackboardView: 'lanes', needsReviewOnly: false, unfoldedArtifactId: null });
  });

  it('shows each run as a lane, newest on top, with its status and its artifacts by column', () => {
    render(<Blackboard />);

    expect(screen.getAllByRole('region').map((region) => region.getAttribute('aria-label'))).toEqual(['Run cccc', 'Run bbbb', 'Run aaaa']);
    const done = lane('aaaa');
    expect(done.textContent).toContain('App crashes on login');
    expect(done.textContent).toContain('done in 3.5 s · 3 artifacts');
    // Type and producer, two fields of the payload, a decision's answer
    expect(within(done).getByRole('button', { name: 'SupportTicket by external' }).textContent).toContain('subjectApp crashes on login');
    expect(within(done).getByRole('button', { name: '◆ Route by triage' }).textContent).toContain('tech0.95');
  });

  it('shows an unsure decision with its best guess, and the run as needing review', () => {
    render(<Blackboard />);

    const review = lane('bbbb');
    expect(review.textContent).toContain('needs review');
    expect(within(review).getByRole('button', { name: '◆ Route by triage' }).textContent).toContain('UNSUREshipping 0.46');
  });

  it('shows what a running agent writes as it streams', () => {
    render(<Blackboard />);

    const running = lane('cccc');
    expect(running.textContent).toContain('billing_team is writing');
    expect(within(running).getByRole('button', { name: 'TeamReply by billing_team' }).textContent).toContain('Hi, thanks for your patience');
  });

  it('keeps the placeholder of a run that ended until its output is on the board (#642)', () => {
    useGraphStore.setState({
      settling: new Map([['r-8', { agent: 'urgency', types: ['app.SupportTicket'], artifacts: ['t2'], correlationId: 'bbbb2222-0000', known: [] }]]),
    });
    render(<Blackboard />);

    const waiting = lane('bbbb');
    // A placeholder card by urgency next to triage's decision, and the run still going
    expect(within(waiting).getByLabelText('Not published yet')).toBeTruthy();
    expect(waiting.textContent).toContain('by urgency');
    expect(waiting.textContent).toContain('urgency is running');
  });

  it('opens a lane that arrives while it shows, and only that one (#642)', () => {
    const { rerender } = render(<Blackboard />);
    expect(screen.getAllByRole('region').filter((region) => region.hasAttribute('data-entering'))).toEqual([]);

    act(() => {
      useGraphStore.setState({ nodes: [...nodes, artifact('t4', 'dddd4444-0000', 'app.SupportTicket', 'external', 5000, { payload: { subject: 'New one' } })] });
    });
    rerender(<Blackboard />);

    expect(screen.getAllByRole('region').filter((region) => region.hasAttribute('data-entering')).map((region) => region.getAttribute('aria-label'))).toEqual(['Run dddd']);
  });

  it('lets the lanes below a lane that grows glide to their place (#642)', () => {
      const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const animate = vi.fn(() => ({ cancel: vi.fn(), onfinish: null }));
    const rect = layOut(tops);
    (HTMLElement.prototype as any).animate = animate;
    const { rerender } = render(<Blackboard />);
    expect(animate).not.toHaveBeenCalled();

    // The top lane grows by 40 px: the two below move down
    tops.set('Run bbbb', 140);
    tops.set('Run aaaa', 240);
    act(() => {
      useGraphStore.setState({ nodes: [...nodes] });
    });
    rerender(<Blackboard />);

    expect(animate).toHaveBeenCalledTimes(2);
    expect((animate.mock.calls[0] as unknown[])[0]).toEqual([{ transform: 'translateY(-40px)' }, { transform: 'translateY(0)' }]);
    rect.mockRestore();
    delete (HTMLElement.prototype as any).animate;
  });

  it('does not glide the lanes after a scroll (#642)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const animate = vi.fn();
    const rect = layOut(tops);
    (HTMLElement.prototype as any).animate = animate;
    const { container, rerender } = render(<Blackboard />);

    // Scrolled down by 60 px: every lane shows 60 px higher, none moved on the board
    for (const [label, top] of tops) tops.set(label, top - 60);
    fireEvent.scroll(container.querySelector('.board')!);
    act(() => {
      useGraphStore.setState({ nodes: [...nodes] });
    });
    rerender(<Blackboard />);

    expect(animate).not.toHaveBeenCalled();
    rect.mockRestore();
    delete (HTMLElement.prototype as any).animate;
  });

  it('continues a glide that another change interrupts from where the lane shows (#642)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    // How far a running glide moves each lane right now
    const shift = new Map<string, number>();
    const labelOf = (element: Element) => element.querySelector('section')?.getAttribute('aria-label') ?? '';
    const rect = layOut(tops, { shift });
    const real = window.getComputedStyle.bind(window);
    const style = vi.spyOn(window, 'getComputedStyle').mockImplementation((element: Element) => {
      const computed = real(element);
      const y = (element as HTMLElement).dataset?.lane ? shift.get(labelOf(element)) : undefined;
      if (y === undefined) return computed;
      return new Proxy(computed, { get: (target, prop) => (prop === 'transform' ? `matrix(1, 0, 0, 1, 0, ${y})` : Reflect.get(target, prop, target)) });
    });
    const animate = vi.fn(function (this: HTMLElement) {
      const label = labelOf(this);
      return { cancel: () => shift.delete(label), onfinish: null };
    });
    (HTMLElement.prototype as any).animate = animate;
    const { rerender } = render(<Blackboard />);

    // The top lane grows by 40 px; halfway through the glides the second grows by 40 px too
    tops.set('Run bbbb', 140);
    tops.set('Run aaaa', 240);
    act(() => {
      useGraphStore.setState({ nodes: [...nodes] });
    });
    rerender(<Blackboard />);
    shift.set('Run bbbb', -20);
    shift.set('Run aaaa', -20);
    tops.set('Run aaaa', 280);
    act(() => {
      useGraphStore.setState({ nodes: [...nodes] });
    });
    rerender(<Blackboard />);

    // aaaa showed at 220 (240 - 20): its new glide starts there, 60 px above its place
    expect(animate).toHaveBeenCalledTimes(3);
    expect((animate.mock.calls[2] as unknown[])[0]).toEqual([{ transform: 'translateY(-60px)' }, { transform: 'translateY(0)' }]);
    rect.mockRestore();
    style.mockRestore();
    delete (HTMLElement.prototype as any).animate;
  });

  it('lets the lanes below a lane that resizes without a new snapshot glide (a card unfolds) (#642)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const rect = layOut(tops);
    const animate = vi.fn(() => ({ cancel: vi.fn(), onfinish: null }));
    (HTMLElement.prototype as any).animate = animate;
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
    render(<Blackboard />);

    // A card in the top lane unfolds: the lane grows by 300 px, the board does not render
    tops.set('Run bbbb', 400);
    tops.set('Run aaaa', 500);
    act(() => observers.forEach((callback) => callback([], {} as ResizeObserver)));

    expect(animate).toHaveBeenCalledTimes(2);
    expect((animate.mock.calls[0] as unknown[])[0]).toEqual([{ transform: 'translateY(-300px)' }, { transform: 'translateY(0)' }]);
    rect.mockRestore();
    vi.unstubAllGlobals();
    delete (HTMLElement.prototype as any).animate;
  });

  it('aligns a lane with an unfolded card to its top, as the mockup does (#652)', () => {
    render(<Blackboard />);

    fireEvent.click(within(lane('aaaa')).getByRole('button', { name: '◆ Route by triage', expanded: false }));

    expect(lane('aaaa').hasAttribute('data-unfolded')).toBe(true);
    expect(lane('bbbb').hasAttribute('data-unfolded')).toBe(false);
  });

  it('opens a lane that grows downwards as the lanes below glide away (#652)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const heights = new Map<string, number>([['Run cccc', 100]]);
    const rect = layOut(tops, { heights });
    const animate = vi.fn(() => ({ cancel: vi.fn(), onfinish: null }));
    (HTMLElement.prototype as any).animate = animate;
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
    render(<Blackboard />);

    // A card in the top lane unfolds: it grows by 300 px, the lanes below move down
    heights.set('Run cccc', 400);
    tops.set('Run bbbb', 400);
    tops.set('Run aaaa', 500);
    act(() => observers.forEach((callback) => callback([], {} as ResizeObserver)));

    const clips = animate.mock.calls.map((call) => (call as unknown[])[0] as Keyframe[]).filter((frames) => 'clipPath' in frames[0]!);
    // Its sides reach far past the lane: columns wider than the board scroll sideways and stay visible
    expect(clips).toEqual([[{ clipPath: 'inset(0px -100000px 300px -100000px)' }, { clipPath: 'inset(0px -100000px 0px -100000px)' }]]);
    rect.mockRestore();
  });

  it('continues a reveal that a second growth interrupts from what shows, and lets go of it when the lane shrinks (#652)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const heights = new Map<string, number>([['Run cccc', 100]]);
    const rect = layOut(tops, { heights });
    // How much of the top lane a running reveal hides right now
    let hidden: number | null = null;
    const real = window.getComputedStyle.bind(window);
    const style = vi.spyOn(window, 'getComputedStyle').mockImplementation((element: Element) => {
      const computed = real(element);
      if (hidden === null || (element as HTMLElement).dataset?.lane === undefined) return computed;
      const label = element.querySelector('section')?.getAttribute('aria-label');
      if (label !== 'Run cccc') return computed;
      return new Proxy(computed, { get: (target, prop) => (prop === 'clipPath' ? `inset(0px -100000px ${hidden}px -100000px)` : Reflect.get(target, prop, target)) });
    });
    const clips: { frames: Keyframe[]; cancel: ReturnType<typeof vi.fn> }[] = [];
    (HTMLElement.prototype as any).animate = vi.fn((frames: Keyframe[]) => {
      const animation = { cancel: vi.fn(), onfinish: null };
      if ('clipPath' in frames[0]!) clips.push({ frames, ...animation });
      return animation;
    });
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
    render(<Blackboard />);
    const resize = () => act(() => observers.forEach((callback) => callback([], {} as ResizeObserver)));

    // It grows by 300 px; halfway through, 120 px still hidden, its details add 50 px
    heights.set('Run cccc', 400);
    resize();
    hidden = 120;
    heights.set('Run cccc', 450);
    resize();
    expect(clips[1]!.frames[0]).toEqual({ clipPath: 'inset(0px -100000px 170px -100000px)' });

    // Folded again before the reveal ended: nothing stays hidden
    heights.set('Run cccc', 100);
    resize();
    expect(clips[1]!.cancel).toHaveBeenCalled();
    rect.mockRestore();
    style.mockRestore();
  });

  it('opens a lane that arrives downwards as the lanes below make room for it (#652)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const rect = layOut(tops);
    const clips: { lane: string | undefined; frames: Keyframe[] }[] = [];
    (HTMLElement.prototype as any).animate = vi.fn(function (this: HTMLElement, frames: Keyframe[]) {
      if ('clipPath' in frames[0]!) clips.push({ lane: this.dataset.lane, frames });
      return { cancel: vi.fn(), onfinish: null };
    });
    const { rerender } = render(<Blackboard />);

    tops.set('Run dddd', 0);
    tops.set('Run cccc', 100);
    tops.set('Run bbbb', 200);
    tops.set('Run aaaa', 300);
    act(() => {
      useGraphStore.setState({ nodes: [...nodes, artifact('t4', 'dddd4444-0000', 'app.SupportTicket', 'external', 5000, { payload: { subject: 'New one' } })] });
    });
    rerender(<Blackboard />);

    expect(clips).toEqual([
      { lane: 'dddd4444-0000', frames: [{ clipPath: 'inset(0px -100000px 100px -100000px)' }, { clipPath: 'inset(0px -100000px 0px -100000px)' }] },
    ]);
    rect.mockRestore();
  });

  it('opens a card that grows from its folded box, as its neighbours make room (#652)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const cards = new Map<string, { x: number; y: number; width?: number; height?: number }>([['d1', { x: 300, y: 10, width: 236, height: 65 }]]);
    const rect = layOut(tops, { cards });
    const played: { card: string | undefined; frames: Keyframe[] }[] = [];
    (HTMLElement.prototype as any).animate = vi.fn(function (this: HTMLElement, frames: Keyframe[]) {
      played.push({ card: this.dataset.glide, frames });
      return { cancel: vi.fn(), onfinish: null };
    });
    const { rerender } = render(<Blackboard />);

    cards.set('d1', { x: 300, y: 10, width: 420, height: 470 });
    act(() => {
      useGraphStore.setState({ nodes: [...nodes] });
    });
    rerender(<Blackboard />);

    expect(played).toContainEqual({ card: 'd1', frames: [{ clipPath: 'inset(0px 184px 405px 0px)' }, { clipPath: 'inset(0px 0px 0px 0px)' }] });
    rect.mockRestore();
  });

  it('measures when a card unfolds though no lane changes its size (#652)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const cards = new Map<string, { x: number; y: number }>([['head', { x: 0, y: 40 }]]);
    const rect = layOut(tops, { cards });
    const moved: (string | undefined)[] = [];
    (HTMLElement.prototype as any).animate = vi.fn(function (this: HTMLElement) {
      moved.push(this.dataset.glide);
      return { cancel: vi.fn(), onfinish: null };
    });
    render(<Blackboard />);

    // Unfolding aligns the lanes' content to the top: the headers move up
    cards.set('head', { x: 0, y: 10 });
    fireEvent.click(within(lane('aaaa')).getByRole('button', { name: '◆ Route by triage', expanded: false }));

    expect(moved).toContain('head');
    rect.mockRestore();
  });

  it('lets a card that changes its place in a lane glide there (#652)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const cards = new Map<string, { x: number; y: number }>([['d1', { x: 300, y: 10 }]]);
    const rect = layOut(tops, { cards });
    const moved: { card: string | undefined; frames: Keyframe[] }[] = [];
    (HTMLElement.prototype as any).animate = vi.fn(function (this: HTMLElement, frames: Keyframe[]) {
      moved.push({ card: this.dataset.glide, frames });
      return { cancel: vi.fn(), onfinish: null };
    });
    const { rerender } = render(<Blackboard />);

    // The decision's card moves 40 px down in its lane (the lane's alignment changed)
    cards.set('d1', { x: 300, y: 50 });
    act(() => {
      useGraphStore.setState({ nodes: [...nodes] });
    });
    rerender(<Blackboard />);

    expect(moved).toEqual([{ card: 'd1', frames: [{ transform: 'translate(0px, -40px)' }, { transform: 'translate(0px, 0px)' }] }]);
    rect.mockRestore();
  });

  it('lets go of glides that ended and of lanes that left (#642)', () => {
    const tops = new Map<string, number>([['Run cccc', 0], ['Run bbbb', 100], ['Run aaaa', 200]]);
    const glides: { cancel: ReturnType<typeof vi.fn>; onfinish: null | (() => void) }[] = [];
    const rect = layOut(tops);
    (HTMLElement.prototype as any).animate = vi.fn(() => {
      const glide = { cancel: vi.fn(), onfinish: null };
      glides.push(glide);
      return glide;
    });
    const { rerender } = render(<Blackboard />);
    tops.set('Run bbbb', 140);
    tops.set('Run aaaa', 240);
    act(() => {
      useGraphStore.setState({ nodes: [...nodes] });
    });
    rerender(<Blackboard />);
    expect(glides).toHaveLength(2);

    // bbbb's glide ends; aaaa's lane leaves the board while it glides
    act(() => glides[0]!.onfinish?.());
    act(() => {
      useGraphStore.setState({ nodes: nodes.filter((node) => node.data.correlationId !== 'aaaa1111-0000') });
    });
    rerender(<Blackboard />);

    expect(glides[0]!.cancel).not.toHaveBeenCalled();
    expect(glides[1]!.cancel).toHaveBeenCalledTimes(1);
    rect.mockRestore();
    delete (HTMLElement.prototype as any).animate;
  });

  it('counts runs, artifacts and reviews, and narrows to the runs that need a review', () => {
    render(<Blackboard />);
    expect(screen.getByText('3 runs · 7 artifacts · 1 needs review')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Needs review only' }));
    expect(screen.getAllByRole('region').map((region) => region.getAttribute('aria-label'))).toEqual(['Run bbbb']);
    expect(screen.getByRole('button', { name: 'Needs review only' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('unfolds a card in place with what it read by ID, and folds it', async () => {
    render(<Blackboard />);

    fireEvent.click(within(lane('aaaa')).getByRole('button', { name: '◆ Route by triage', expanded: false }));
    const card = screen.getByRole('article', { name: '◆ Route by triage' });
    expect(card.textContent).toContain('by triage · 58 ms');
    expect(card.textContent).toContain('azure/decision-1');
    // Its head names the question; the decision does not again
    expect(within(card).queryByText('Choice')).toBeNull();
    // Its consumption history, from the artifact read by ID
    expect(await within(card).findByText('run 7f3a2b')).toBeTruthy();
    expect(card.textContent).toContain('support');

    fireEvent.click(within(card).getByRole('button', { name: 'Fold' }));
    expect(screen.queryByRole('article')).toBeNull();
  });

  it('keeps the output so far of a streaming card it unfolds, and reads it once it is published', async () => {
    render(<Blackboard />);

    fireEvent.click(within(lane('cccc')).getByRole('button', { name: 'TeamReply by billing_team', expanded: false }));
    const card = screen.getByRole('article', { name: 'TeamReply by billing_team' });
    expect(card.textContent).toContain('Hi, thanks for your patience');
    // Not on the record yet: nothing to read
    expect(card.textContent).toContain('Not published yet');
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).not.toContain('/api/v1/artifacts/s1?images=thumbnails&embed_meta=true');

    act(() =>
      useGraphStore.setState({
        nodes: nodes.map((node) =>
          node.id === 's1' ? { ...node, data: { ...node.data, isStreaming: false, payload: { reply: 'Hi, thanks for your patience.' } } } : node,
        ),
        edges: [...edges, made('t3', 's1', 'billing_team')],
      }),
    );
    await waitFor(() =>
      expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toContain('/api/v1/artifacts/s1?images=thumbnails&embed_meta=true'),
    );
  });

  it('unfolds a card with the keyboard', () => {
    render(<Blackboard />);

    fireEvent.keyDown(within(lane('aaaa')).getByRole('button', { name: 'SupportTicket by external', expanded: false }), { key: 'Enter' });
    expect(useUIStore.getState().unfoldedArtifactId).toBe('t1');
  });

  it('says when the lanes hold only the newest artifacts', () => {
    useGraphStore.setState({ truncated: true });
    render(<Blackboard />);

    expect(screen.getByText(/newest 500 artifacts/)).toBeTruthy();
  });

  it('switches to the graph: every artifact a card, no table', async () => {
    render(<Blackboard />);

    expect(screen.queryByRole('button', { name: 'Table' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Graph' }));
    expect(useUIStore.getState().blackboardView).toBe('graph');
    expect(screen.queryAllByRole('region')).toHaveLength(0);

    // jsdom measures nothing, so React Flow draws no arrows here (graph.test.ts has them)
    await waitFor(() => expect(document.querySelectorAll('.react-flow__node')).toHaveLength(nodes.length));
    // The streaming reply is a streaming card; a click unfolds a card in place.
    // React Flow hides a node until it is measured, which jsdom does not do, so
    // the cards have no accessible name here: they are found by their label
    const card = (label: string) => document.querySelector<HTMLElement>(`[role="button"][aria-label="${label}"]`)!;
    expect(card('TeamReply by billing_team').textContent).toContain('Hi, thanks');
    fireEvent.click(card('◆ Route by triage'));
    expect(useUIStore.getState().unfoldedArtifactId).toBe('d1');
  });

  it('keeps a selected card on Backspace: the graph shows artifacts, it does not delete them', async () => {
    useUIStore.setState({ blackboardView: 'graph' });
    render(<Blackboard />);
    await waitFor(() => expect(document.querySelectorAll('.react-flow__node')).toHaveLength(nodes.length));

    const node = document.querySelector<HTMLElement>('.react-flow__node[data-id="t1"]')!;
    fireEvent.click(node);
    fireEvent.keyDown(node, { key: 'Backspace' });
    fireEvent.keyDown(document.body, { key: 'Backspace' });
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(document.querySelectorAll('.react-flow__node')).toHaveLength(nodes.length);
  });

  it('folds a card from the keyboard after it was unfolded with the mouse', async () => {
    useUIStore.setState({ blackboardView: 'graph' });
    render(<Blackboard />);
    await waitFor(() => expect(document.querySelectorAll('.react-flow__node')).toHaveLength(nodes.length));
    const card = document.querySelector<HTMLElement>('[role="button"][aria-label="SupportTicket by external"]')!;

    fireEvent.pointerDown(card, { clientX: 100, clientY: 100 });
    fireEvent.click(card, { clientX: 100, clientY: 100, detail: 1 });
    expect(useUIStore.getState().unfoldedArtifactId).toBe('t1');

    // Enter or Space on the Fold button: a click at (0, 0) with no pointer behind it
    const fold = document.querySelector<HTMLElement>('[aria-label="Fold"]')!;
    fireEvent.click(fold, { clientX: 0, clientY: 0, detail: 0 });
    expect(useUIStore.getState().unfoldedArtifactId).toBeNull();
  });

  it('lays a run out again when an edge between its cards arrives before the first view', async () => {
    useUIStore.setState({ blackboardView: 'graph' });
    render(<Blackboard />);
    await waitFor(() => expect(document.querySelectorAll('.react-flow__node')).toHaveLength(nodes.length));
    // jsdom measures nothing, so the first view never comes: the board is still before it
    const top = (id: string) => Number(/translate\([-\d.]+px, ?([-\d.]+)px\)/.exec(document.querySelector<HTMLElement>(`.react-flow__node[data-id="${id}"]`)!.style.transform)![1]);
    // The refund run has no edge yet: its ticket and reply stand side by side
    expect(top('s1')).toBe(top('t3'));

    act(() => useGraphStore.setState({ edges: [...edges, made('t3', 's1', 'billing_team')] }));

    // Top down, the reply goes under the ticket it answers
    await waitFor(() => expect(top('s1')).toBeGreaterThan(top('t3')));
  });

  it('narrows the graph to the runs that need a review', async () => {
    useUIStore.setState({ blackboardView: 'graph', needsReviewOnly: true });
    render(<Blackboard />);

    // Only the run whose decision is unsure: its ticket and the decision
    await waitFor(() => expect(document.querySelectorAll('.react-flow__node')).toHaveLength(2));
    expect([...document.querySelectorAll('.react-flow__node')].map((node) => node.getAttribute('data-id')).sort()).toEqual(['d2', 't2']);
  });
});
