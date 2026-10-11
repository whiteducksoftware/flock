import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { Node } from '@xyflow/react';
import { useGraphStore } from '../../../store/graphStore';
import { useRunInput } from './runInput';

const decision = {
  id: 'd-1',
  type: 'flock.decisions.Decision[app.Route]',
  payload: { choice: 'billing', subject_ids: ['t-2'] },
  created_at: '2026-10-11T12:01:10Z',
  correlation_id: 'c-1',
};
const ticket = {
  id: 't-2',
  type: 'app.SupportTicket',
  payload: { subject: 'Charged twice', photo: 'A photo, 1200 × 800 PNG' },
  images: [{ path: 'photo', mime_type: 'image/png' }],
  created_at: '2026-10-11T12:01:08Z',
  correlation_id: 'c-1',
};

const agent = (id: string, typeLabels?: Record<string, string>): Node => ({
  id,
  type: 'agent',
  position: { x: 0, y: 0 },
  data: { name: id, typeLabels },
});

describe('useRunInput', () => {
  let fetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetch = vi.fn(async (url: string) => {
      const body = { '/api/v1/artifacts/d-1?images=thumbnails': decision, '/api/v1/artifacts/t-2?images=thumbnails': ticket }[url];
      return body ? new Response(JSON.stringify(body)) : new Response('', { status: 404 });
    });
    vi.stubGlobal('fetch', fetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    useGraphStore.setState(useGraphStore.getInitialState(), true);
  });

  const running = (node: Node) =>
    useGraphStore.setState({
      nodes: [node],
      inFlight: new Map([['r-1', { agent: node.id, types: ['flock.decisions.Decision[app.Route]'], artifacts: ['d-1'] }]]),
    });

  it('gives a handle the subject of its decision, with images as thumbnails', async () => {
    running(agent('billing_team', { 'flock.decisions.Decision[app.Route]': '◆ Route.billing' }));
    const { result } = renderHook(() => useRunInput('billing_team'));

    await waitFor(() => expect(result.current.inputs?.[0]?.id).toBe('t-2'));
    expect(result.current.inputs?.[0]?.payload).toEqual({ subject: 'Charged twice', photo: 'A photo, 1200 × 800 PNG' });
    expect(result.current.inputs?.[0]?.images).toEqual([{ path: 'photo', mime_type: 'image/png' }]);
  });

  it('gives every input of an AND gate or batch, and every subject of a decision, up to five', async () => {
    const artifact = (id: string, payload: unknown = { id }) => ({ id, type: 'app.Item', payload, created_at: '2026-10-11T12:00:00Z' });
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        const id = /artifacts\/([^?]+)/.exec(url)![1]!;
        if (id === 'd-2') return new Response(JSON.stringify({ ...decision, id, payload: { subject_ids: ['t-3', 't-4'] } }));
        return new Response(JSON.stringify(artifact(id)));
      }),
    );
    useGraphStore.setState({
      nodes: [agent('ranker', { 'Decision[app.Route]': '◆ Route.billing' })],
      inFlight: new Map([['r-1', { agent: 'ranker', types: ['app.Item'], artifacts: ['d-2', 'a-1', 'a-2', 'a-3', 'a-4', 'a-5', 'a-6'] }]]),
    });
    const { result } = renderHook(() => useRunInput('ranker'));

    await waitFor(() => expect(result.current.inputs?.map((input) => input.id)).toEqual(['t-3', 't-4', 'a-1', 'a-2', 'a-3', 'a-4']));
    expect(result.current).toMatchObject({ runId: 'r-1', more: 2 });
  });

  it('keeps the inputs it may read when others are private to the agent', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        const id = /artifacts\/([^?]+)/.exec(url)![1]!;
        if (id === 'd-3') return new Response(JSON.stringify({ ...decision, id, payload: { subject_ids: ['t-5', 'private-2'] } }));
        if (id.startsWith('private')) return new Response('', { status: 404 });
        return new Response(JSON.stringify({ ...ticket, id }));
      }),
    );
    useGraphStore.setState({
      nodes: [agent('ranker', { 'Decision[app.Route]': '◆ Route.billing' })],
      inFlight: new Map([['r-1', { agent: 'ranker', types: ['app.Item'], artifacts: ['a-1', 'private-1', 'd-3'] }]]),
    });
    const { result } = renderHook(() => useRunInput('ranker'));

    // Private ones are counted with the rest the stage does not show
    await waitFor(() => expect(result.current.inputs?.map((input) => input.id)).toEqual(['a-1', 't-5']));
    expect(result.current.more).toBe(2);
  });

  it('gives a consumer of the decision itself the decision', async () => {
    running(agent('audit'));
    const { result } = renderHook(() => useRunInput('audit'));

    await waitFor(() => expect(result.current.inputs?.map((input) => input.id)).toEqual(['d-1']));
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
