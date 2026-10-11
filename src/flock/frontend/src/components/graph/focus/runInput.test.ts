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

    await waitFor(() => expect(result.current?.id).toBe('t-2'));
    expect(result.current?.payload).toEqual({ subject: 'Charged twice', photo: 'A photo, 1200 × 800 PNG' });
    expect(result.current?.images).toEqual([{ path: 'photo', mime_type: 'image/png' }]);
  });

  it('gives a consumer of the decision itself the decision', async () => {
    running(agent('audit'));
    const { result } = renderHook(() => useRunInput('audit'));

    await waitFor(() => expect(result.current?.id).toBe('d-1'));
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
