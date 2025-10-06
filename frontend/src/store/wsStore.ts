import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

interface WSState {
  // Connection state
  status: ConnectionStatus;
  lastError: string | null;
  reconnectAttempts: number;

  // Actions
  setStatus: (status: ConnectionStatus) => void;
  setError: (error: string | null) => void;
  incrementAttempts: () => void;
  resetAttempts: () => void;
}

export const useWSStore = create<WSState>()(
  devtools(
    (set) => ({
      status: 'disconnected',
      lastError: null,
      reconnectAttempts: 0,

      setStatus: (status) => set({ status }),
      setError: (error) => set({ lastError: error }),
      incrementAttempts: () =>
        set((state) => ({ reconnectAttempts: state.reconnectAttempts + 1 })),
      resetAttempts: () => set({ reconnectAttempts: 0 }),
    }),
    { name: 'wsStore' }
  )
);
