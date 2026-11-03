import type { ConnectionStatus } from '../../store/wsStore';

/** What the dashboard tells about its connection: Live · Reconnecting (n) · Offline. */
export type LiveState = 'live' | 'connecting' | 'reconnecting' | 'offline';

export function liveState(status: ConnectionStatus, attempts: number): LiveState {
  if (status === 'connected') return 'live';
  if (status === 'disconnected') return 'offline';
  // An attempt in flight after a lost connection is still reconnecting
  return attempts > 0 ? 'reconnecting' : 'connecting';
}
