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

  it('drops the ticker of a run that failed, unless another run goes on', () => {
    vi.useFakeTimers();
    const client = new WebSocketClient('ws://test/ws');
    useGraphStore.setState({ streamingTokens: new Map([['billing', ['we have']]]) });

    receive(client, 'agent_error', { agent_name: 'billing', agent_status: 'running' });
    expect(useGraphStore.getState().streamingTokens.get('billing')).toEqual(['we have']);

    receive(client, 'agent_error', { agent_name: 'billing', agent_status: 'error' });
    expect(useGraphStore.getState().streamingTokens.get('billing')).toEqual([]);
  });

  it('drops the streaming preview of a run that ended without publishing it', () => {
    vi.useFakeTimers();
    const client = new WebSocketClient('ws://test/ws');
    const preview = (id: string, producedBy: string, correlationId: string) => ({
      id,
      type: 'message',
      position: { x: 0, y: 0 },
      data: { artifactType: 'TeamReply', producedBy, correlationId, isStreaming: true },
    });
    useGraphStore.setState({ nodes: [preview('p1', 'billing', 'c-1'), preview('p2', 'billing', 'c-2')] as never });

    receive(client, 'agent_error', { agent_name: 'billing', correlation_id: 'c-1', agent_status: 'error' });

    expect(useGraphStore.getState().nodes.map((node) => node.id)).toEqual(['p2']);
  });

  it('remembers what a starting run consumed, and its run', () => {
    vi.useFakeTimers();
    const client = new WebSocketClient('ws://test/ws');

    receive(client, 'agent_activated', {
      agent_name: 'billing',
      run_id: 'r-1',
      consumed_types: ['Decision[app.Route]'],
      consumed_artifacts: ['d-1'],
      correlation_id: 'c-1',
    });
    expect(useGraphStore.getState().inFlight.get('r-1')).toEqual({
      agent: 'billing',
      types: ['Decision[app.Route]'],
      artifacts: ['d-1'],
      correlationId: 'c-1',
    });
  });

  it('keeps the end of each running run\'s output apart, until the run ends', () => {
    vi.useFakeTimers();
    vi.spyOn(console, 'log').mockImplementation(() => {});
    const client = new WebSocketClient('ws://test/ws');
    const token = (run_id: string, content: string) =>
      receive(client, 'streaming_output', { agent_name: 'billing', run_id, content, output_type: 'llm_token', sequence: 1 });

    token('r-1', 'Your refund ');
    token('r-2', 'The second ');
    token('r-1', 'is on its way');
    expect(useGraphStore.getState().runTails.get('r-1')).toBe('Your refund is on its way');
    expect(useGraphStore.getState().runTails.get('r-2')).toBe('The second ');

    token('r-1', 'x'.repeat(200));
    expect(useGraphStore.getState().runTails.get('r-1')).toHaveLength(160);

    receive(client, 'agent_completed', { agent_name: 'billing', run_id: 'r-1', agent_status: 'running' });
    receive(client, 'agent_error', { agent_name: 'billing', run_id: 'r-2', agent_status: 'error' });
    expect(useGraphStore.getState().runTails.size).toBe(0);
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
