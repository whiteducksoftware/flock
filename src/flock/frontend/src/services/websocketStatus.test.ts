import { beforeEach, describe, expect, it } from 'vitest';
import { useGraphStore } from '../store/graphStore';
import { WebSocketClient } from './websocket';

/** Hand the client one event, as the server sends it. */
const receive = (client: WebSocketClient, event_type: string, data: Record<string, unknown>) =>
  (client as unknown as { handleMessage: (event: MessageEvent) => void }).handleMessage(
    new MessageEvent('message', { data: JSON.stringify({ event_type, data, correlation_id: '', timestamp: '' }) }),
  );

describe('WebSocketClient agent status', () => {
  beforeEach(() => {
    useGraphStore.setState({ agentStatus: new Map() });
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
