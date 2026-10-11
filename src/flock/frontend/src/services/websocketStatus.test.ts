import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useGraphStore } from '../store/graphStore';
import { WebSocketClient } from './websocket';

/** Hand the client one event, as the server sends it. */
const receive = (client: WebSocketClient, event_type: string, data: Record<string, unknown>) =>
  (client as unknown as { handleMessage: (event: MessageEvent) => void }).handleMessage(
    new MessageEvent('message', { data: JSON.stringify({ event_type, data, correlation_id: '', timestamp: '' }) }),
  );

describe('WebSocketClient agent status', () => {
  beforeEach(() => {
    useGraphStore.setState({ agentStatus: new Map(), streamingTokens: new Map() });
  });

  afterEach(() => {
    useGraphStore.setState(useGraphStore.getInitialState(), true);
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('keeps the ticker while another run of the agent goes on', () => {
    const client = new WebSocketClient('ws://test/ws');
    useGraphStore.setState({ streamingTokens: new Map([['billing', ['we have']]]) });

    receive(client, 'agent_completed', { agent_name: 'billing', agent_status: 'running' });
    expect(useGraphStore.getState().streamingTokens.get('billing')).toEqual(['we have']);

    receive(client, 'agent_completed', { agent_name: 'billing', agent_status: 'idle' });
    expect(useGraphStore.getState().streamingTokens.get('billing')).toEqual([]);
  });

  it('reloads the board when an agent ends failed, which says what failed', () => {
    vi.useFakeTimers();
    vi.spyOn(console, 'log').mockImplementation(() => {});
    const refresh = vi.spyOn(useGraphStore.getState(), 'refreshCurrentView').mockResolvedValue();
    const client = new WebSocketClient('ws://test/ws');

    receive(client, 'agent_error', { agent_name: 'crm_sync', agent_status: 'error' });
    vi.advanceTimersByTime(1000);
    expect(refresh).toHaveBeenCalledOnce();

    // A run completing after a newer one failed: the card stays failed and learns why
    receive(client, 'agent_completed', { agent_name: 'crm_sync', agent_status: 'error' });
    vi.advanceTimersByTime(1000);
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it('takes the status the server derived from all of the agent\'s runs', () => {
    const client = new WebSocketClient('ws://test/ws');

    // A run completed while a newer one had failed: the agent stays failed
    receive(client, 'agent_completed', { agent_name: 'triage', agent_status: 'error' });
    expect(useGraphStore.getState().agentStatus.get('triage')).toBe('error');

    // A run failed while another one goes on: the agent is still running
    receive(client, 'agent_error', { agent_name: 'triage', agent_status: 'running' });
    expect(useGraphStore.getState().agentStatus.get('triage')).toBe('running');
  });

  it('falls back to the event itself from an older server', () => {
    const client = new WebSocketClient('ws://test/ws');

    receive(client, 'agent_error', { agent_name: 'triage' });
    expect(useGraphStore.getState().agentStatus.get('triage')).toBe('error');

    receive(client, 'agent_completed', { agent_name: 'triage' });
    expect(useGraphStore.getState().agentStatus.get('triage')).toBe('idle');
  });
});
