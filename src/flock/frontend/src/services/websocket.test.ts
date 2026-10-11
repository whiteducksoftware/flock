import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { liveState } from '../components/layout/connection';
import { useGraphStore } from '../store/graphStore';
import { useWSStore } from '../store/wsStore';
import { useFilterStore } from '../store/filterStore';
import { WebSocketClient } from './websocket';

const fetchArtifactSummary = vi.hoisted(() => vi.fn());
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  fetchArtifactSummary,
}));

/** A socket the test opens, fails and closes by hand. */
class FakeSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static made: FakeSocket[] = [];

  readyState = FakeSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onmessage: ((event: unknown) => void) | null = null;

  constructor(public url: string) {
    FakeSocket.made.push(this);
  }

  open() {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
  }

  /** The server is gone: the browser reports an error, then the close. */
  fail() {
    this.readyState = FakeSocket.CLOSED;
    this.onerror?.(new Event('error'));
    this.onclose?.({ code: 1006, reason: '' });
  }

  close() {
    this.readyState = FakeSocket.CLOSED;
  }

  send() {}
}

const socket = (index: number): FakeSocket => {
  const made = FakeSocket.made[index];
  if (!made) throw new Error(`No socket ${index} was opened`);
  return made;
};

describe('WebSocketClient reconnects', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-11T12:00:00Z'));
    vi.stubGlobal('WebSocket', FakeSocket);
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
    FakeSocket.made = [];
    fetchArtifactSummary.mockReset().mockResolvedValue(null);
    useWSStore.setState({ status: 'connecting', reconnectAttempts: 0, nextRetryAt: null, lastError: null });
  });

  afterEach(() => {
    // A test's setState would carry its spies into the next test
    useGraphStore.setState(useGraphStore.getInitialState(), true);
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('schedules a retry after a failed connection and says when', () => {
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).open();

    socket(0).fail();

    const state = useWSStore.getState();
    expect(state.status).toBe('reconnecting');
    expect(state.reconnectAttempts).toBe(1);
    expect(state.nextRetryAt).toBe(Date.now() + 1000);

    vi.advanceTimersByTime(1000);
    expect(FakeSocket.made).toHaveLength(2);
    client.disconnect();
  });

  it('keeps retrying while the server stays away', () => {
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).fail();
    vi.advanceTimersByTime(1000);

    socket(1).fail();

    expect(useWSStore.getState().status).toBe('reconnecting');
    expect(useWSStore.getState().reconnectAttempts).toBe(2);
    expect(useWSStore.getState().nextRetryAt).toBe(Date.now() + 2000);
    client.disconnect();
  });

  it('retries at once when asked, and plans afresh when that fails too', () => {
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).fail();
    vi.advanceTimersByTime(500);

    client.reconnectManually();

    expect(FakeSocket.made).toHaveLength(2);
    expect(useWSStore.getState().nextRetryAt).toBeNull();
    socket(1).fail();
    // The retry the failure planned before does not stand in the way; the
    // wait starts over, and the manual try counts as an attempt
    expect(useWSStore.getState()).toMatchObject({
      status: 'reconnecting',
      reconnectAttempts: 3,
      nextRetryAt: Date.now() + 1000,
    });
    client.disconnect();
  });

  it('stays reconnecting while a retry asked for by hand is under way', () => {
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).open();
    socket(0).fail();

    client.reconnectManually();

    const { status, reconnectAttempts } = useWSStore.getState();
    expect(liveState(status, reconnectAttempts)).toBe('reconnecting');
    client.disconnect();
  });

  it('lets an attempt under way finish when asked to retry now', () => {
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).fail();
    vi.advanceTimersByTime(1000); // the planned attempt is connecting
    const before = useWSStore.getState().reconnectAttempts;

    client.reconnectManually();

    expect(FakeSocket.made).toHaveLength(2);
    expect(useWSStore.getState().reconnectAttempts).toBe(before);
    client.disconnect();
  });

  it('refreshes the board when a retry by hand ends an offline spell', () => {
    const refresh = vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).open();
    // A clean close: offline, with no retry planned
    socket(0).readyState = FakeSocket.CLOSED;
    socket(0).onclose?.({ code: 1000, reason: '' });
    expect(useWSStore.getState().status).toBe('disconnected');

    client.reconnectManually();
    socket(1).open();
    vi.advanceTimersByTime(1000);

    expect(refresh).toHaveBeenCalledOnce();
    client.disconnect();
  });

  it('refreshes the board after a reconnect, not after the first connect', () => {
    const refresh = vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).open();
    vi.advanceTimersByTime(1000);
    expect(refresh).not.toHaveBeenCalled();

    socket(0).fail();
    vi.advanceTimersByTime(1000);
    socket(1).open();
    vi.advanceTimersByTime(1000);

    // Events published while offline never arrived
    expect(refresh).toHaveBeenCalledOnce();
    client.disconnect();
  });

  it('reloads the blackboard summary after a reconnect', async () => {
    vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    const summary = { total: 7, by_type: {}, by_producer: {}, by_visibility: {}, tag_counts: {} };
    fetchArtifactSummary.mockResolvedValue(summary);
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).open();
    socket(0).fail();
    vi.advanceTimersByTime(1000);

    socket(1).open();
    await vi.waitFor(() => expect(useFilterStore.getState().summary).toEqual(summary));

    // Artifacts published while offline never counted
    expect(fetchArtifactSummary).toHaveBeenCalledOnce();
    client.disconnect();
  });

  it('forgets the live states from before an outage', () => {
    vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).open();
    // triage was running when the connection dropped, and finished meanwhile
    useGraphStore.setState({
      agentStatus: new Map([['triage', 'running']]),
      streamingTokens: new Map([['triage', ['Hel', 'lo']]]),
    });
    socket(0).fail();
    vi.advanceTimersByTime(1000);

    socket(1).open();

    // The refreshed snapshot says how things stand now
    expect(useGraphStore.getState().agentStatus.size).toBe(0);
    expect(useGraphStore.getState().streamingTokens.size).toBe(0);
    vi.advanceTimersByTime(1000); // the refresh
    client.disconnect();
  });

  it('refreshes the board after a retry asked for by hand too', () => {
    const refresh = vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).open();
    socket(0).fail();

    client.reconnectManually();
    socket(1).open();
    vi.advanceTimersByTime(1000);

    expect(refresh).toHaveBeenCalledOnce();
    client.disconnect();
  });

  it('is live again once a retry connects', () => {
    const client = new WebSocketClient('ws://test/ws');
    client.connect();
    socket(0).fail();
    vi.advanceTimersByTime(1000);

    socket(1).open();

    expect(useWSStore.getState()).toMatchObject({
      status: 'connected',
      reconnectAttempts: 0,
      nextRetryAt: null,
    });
    client.disconnect();
  });
});

describe('WebSocketClient run events', () => {
  /** Hand the client one event, as the server sends it. */
  const receive = (client: WebSocketClient, event_type: string, data: Record<string, unknown>) =>
    (client as unknown as { handleMessage: (event: MessageEvent) => void }).handleMessage(
      new MessageEvent('message', { data: JSON.stringify({ event_type, data, correlation_id: '', timestamp: '' }) }),
    );

  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(console, 'log').mockImplementation(() => {});
    useGraphStore.setState({ agentStatus: new Map(), inFlight: new Map() });
  });

  afterEach(() => {
    useGraphStore.setState(useGraphStore.getInitialState(), true);
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  const inFlightTypes = (agent: string) =>
    [...useGraphStore.getState().inFlight.values()]
      .filter((run) => run.agent === agent)
      .flatMap((run) => run.types)
      .sort();

  it('knows which types are in flight to a running agent, run by run', () => {
    vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    const client = new WebSocketClient('ws://test/ws');

    receive(client, 'agent_activated', { agent_name: 'billing', run_id: 'a', consumed_types: ['app.Ticket'] });
    receive(client, 'agent_activated', { agent_name: 'billing', run_id: 'b', consumed_types: ['app.Reply'] });
    expect(inFlightTypes('billing')).toEqual(['app.Reply', 'app.Ticket']);

    // The newer run ends first: the older one's type stays in flight
    receive(client, 'agent_completed', { agent_name: 'billing', run_id: 'b', agent_status: 'running' });
    expect(inFlightTypes('billing')).toEqual(['app.Ticket']);

    receive(client, 'agent_error', { agent_name: 'billing', run_id: 'a', agent_status: 'error' });
    expect(inFlightTypes('billing')).toEqual([]);
  });

  it('reloads the board after a failure, which says what failed', () => {
    const refresh = vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    const client = new WebSocketClient('ws://test/ws');
    receive(client, 'agent_activated', { agent_name: 'crm_sync', run_id: 'r1', consumed_types: ['app.Reply'] });
    vi.advanceTimersByTime(1000);
    refresh.mockClear();

    receive(client, 'agent_error', { agent_name: 'crm_sync', run_id: 'r1', agent_status: 'error' });
    vi.advanceTimersByTime(1000);

    expect(useGraphStore.getState().agentStatus.get('crm_sync')).toBe('error');
    expect(useGraphStore.getState().inFlight.size).toBe(0);
    expect(refresh).toHaveBeenCalledOnce();
  });
});
