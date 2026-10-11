import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useFilterStore } from '../../store/filterStore';
import { useGraphStore } from '../../store/graphStore';
import { useUIStore } from '../../store/uiStore';
import { useWSStore } from '../../store/wsStore';
import BoardStates from './BoardStates';

const retryConnectionNow = vi.hoisted(() => vi.fn());
vi.mock('../../services/websocket', () => ({ retryConnectionNow }));

const summary = (total: number) => ({
  total,
  by_type: {},
  by_producer: {},
  by_visibility: {},
  tag_counts: {},
  earliest_created_at: null,
  latest_created_at: null,
});

describe('BoardStates', () => {
  beforeEach(() => {
    useGraphStore.setState({ nodes: [], isLoading: false, error: null });
    useWSStore.setState({ status: 'connected', reconnectAttempts: 0, nextRetryAt: null });
    useUIStore.setState({ mode: 'blackboard' });
    useFilterStore.setState({ summary: summary(0) });
    retryConnectionNow.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('shows a skeleton while the first board loads', () => {
    useGraphStore.setState({ isLoading: true });

    render(<BoardStates onPublish={() => {}} />);

    expect(screen.getByRole('status', { name: 'Loading the board' })).toBeTruthy();
    expect(screen.queryByText('Nothing on the blackboard yet')).toBeNull();
  });

  it('invites the first publish on an empty blackboard', () => {
    const onPublish = vi.fn();
    render(<BoardStates onPublish={onPublish} />);

    fireEvent.click(screen.getByRole('button', { name: 'Publish' }));

    expect(screen.getByText('Nothing on the blackboard yet')).toBeTruthy();
    expect(onPublish).toHaveBeenCalledOnce();
  });

  it('tells filtered-out artifacts from an empty blackboard', () => {
    vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    useFilterStore.setState({ summary: summary(42), selectedProducers: ['triage'], timeRange: { preset: 'last5min' } });
    render(<BoardStates onPublish={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: 'Show all' }));

    expect(screen.getByText('Nothing matches these filters')).toBeTruthy();
    expect(screen.getByText('42 artifacts are on the blackboard.')).toBeTruthy();
    expect(useFilterStore.getState()).toMatchObject({ selectedProducers: [], timeRange: { preset: 'all' } });
  });

  it('shows nothing over a board with nodes', () => {
    useGraphStore.setState({ nodes: [{ id: 'a', type: 'agent', position: { x: 0, y: 0 }, data: {} }] as never });

    const { container } = render(<BoardStates onPublish={() => {}} />);

    expect(container.textContent).toBe('');
  });

  it('shows a load error on the board and retries', () => {
    const refresh = vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    useGraphStore.setState({ error: 'Graph API error: Bad Gateway' });
    render(<BoardStates onPublish={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(screen.getByRole('alert').textContent).toContain('Graph API error: Bad Gateway');
    expect(refresh).toHaveBeenCalledOnce();
    // An error is not an empty blackboard
    expect(screen.queryByText('Nothing on the blackboard yet')).toBeNull();
  });

  it('counts down to the next reconnect and retries now on request', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-11T12:00:00Z'));
    useWSStore.setState({ status: 'reconnecting', reconnectAttempts: 3, nextRetryAt: Date.now() + 4000 });
    render(<BoardStates onPublish={() => {}} />);

    expect(screen.getByText(/reconnecting in/).textContent).toBe('Connection lost · reconnecting in 4 s');
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText(/reconnecting in/).textContent).toBe('Connection lost · reconnecting in 3 s');
    expect(screen.getByText('attempt 3')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Retry now' }));
    expect(retryConnectionNow).toHaveBeenCalledOnce();
  });

  it('shows the offline banner when no retry is planned', () => {
    useWSStore.setState({ status: 'disconnected' });

    render(<BoardStates onPublish={() => {}} />);

    expect(screen.getByText('Offline · the board gets no updates')).toBeTruthy();
  });
});
