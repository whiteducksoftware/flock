import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

interface WSState {
  // Connection state
  status: ConnectionStatus;
  lastError: string | null;
  reconnectAttempts: number;
  /** When the next reconnect attempt starts (epoch ms), while one is scheduled */
  nextRetryAt: number | null;

  // Actions
  setStatus: (status: ConnectionStatus) => void;
  setError: (error: string | null) => void;
  incrementAttempts: () => void;
  resetAttempts: () => void;
  setNextRetryAt: (at: number | null) => void;
}

export const useWSStore = create<WSState>()(
  devtools(
    (set) => ({
      // The dashboard connects as it starts
      status: 'connecting',
      lastError: null,
      reconnectAttempts: 0,
      nextRetryAt: null,

      setStatus: (status) => set({ status }),
      setError: (error) => set({ lastError: error }),
      incrementAttempts: () =>
        set((state) => ({ reconnectAttempts: state.reconnectAttempts + 1 })),
      resetAttempts: () => set({ reconnectAttempts: 0 }),
      setNextRetryAt: (at) => set({ nextRetryAt: at }),
    }),
    { name: 'wsStore' }
  )
);
