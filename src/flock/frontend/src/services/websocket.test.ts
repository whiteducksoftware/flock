import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGraphStore } from '../store/graphStore';
import { useWSStore } from '../store/wsStore';
import { WebSocketClient } from './websocket';

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
    useWSStore.setState({ status: 'connecting', reconnectAttempts: 0, nextRetryAt: null, lastError: null });
  });

  afterEach(() => {
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
    // The retry the failure planned before does not stand in the way
    expect(useWSStore.getState()).toMatchObject({
      status: 'reconnecting',
      reconnectAttempts: 1,
      nextRetryAt: Date.now() + 1000,
    });
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
