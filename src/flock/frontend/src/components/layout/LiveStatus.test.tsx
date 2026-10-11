import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useGraphStore } from '../../store/graphStore';
import { useWSStore } from '../../store/wsStore';
import LiveStatus from './LiveStatus';

const agent = (id: string) => ({ id, type: 'agent', position: { x: 0, y: 0 }, data: {} });

describe('LiveStatus', () => {
  beforeEach(() => {
    useGraphStore.setState({ nodes: [], agentStatus: new Map() });
    useWSStore.setState({ status: 'connected', reconnectAttempts: 0, nextRetryAt: null });
  });

  it('is live and counts the agents and the running ones', () => {
    useGraphStore.setState({
      nodes: [agent('triage'), agent('billing'), agent('tech')] as never,
      agentStatus: new Map([
        ['triage', 'running'],
        ['billing', 'idle'],
        ['tech', 'running'],
      ]),
    });

    render(<LiveStatus />);

    expect(screen.getByRole('status').textContent).toBe('Live3 agents · 2 running');
  });

  it('says how often it tried to reconnect', () => {
    useWSStore.setState({ status: 'reconnecting', reconnectAttempts: 2 });

    render(<LiveStatus />);

    expect(screen.getByRole('status').textContent).toBe('Reconnecting (2)');
  });

  it('counts an attempt in flight as reconnecting too', () => {
    useWSStore.setState({ status: 'connecting', reconnectAttempts: 3 });

    render(<LiveStatus />);

    expect(screen.getByRole('status').textContent).toBe('Reconnecting (3)');
  });

  it('is offline when no retry is planned', () => {
    useWSStore.setState({ status: 'disconnected' });

    render(<LiveStatus />);

    expect(screen.getByRole('status').textContent).toBe('Offline');
  });
});
