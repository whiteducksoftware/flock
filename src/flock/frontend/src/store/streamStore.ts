import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export interface StreamingOutputData {
  agent_name: string;
  run_id: string;
  output_type: 'llm_token' | 'log' | 'stdout' | 'stderr';
  content: string;
  sequence: number;
  is_final: boolean;
  timestamp?: string;
}

interface StreamState {
  // Map<agent_name, StreamingOutputData[]>
  outputs: Map<string, StreamingOutputData[]>;

  // Actions
  addOutput: (agentName: string, output: StreamingOutputData) => void;
  clearOutputs: (agentName: string) => void;
  getOutputs: (agentName: string) => StreamingOutputData[];
}

export const useStreamStore = create<StreamState>()(
  devtools(
    (set, get) => ({
      outputs: new Map(),

      addOutput: (agentName, output) =>
        set((state) => {
          const outputs = new Map(state.outputs);
          const existing = outputs.get(agentName) || [];

          // Check if this exact event already exists (by sequence number and run_id)
          // to prevent duplicates when loading history
          // const isDuplicate = existing.some(
          //   (e) => e.run_id === output.run_id && e.sequence === output.sequence
          // );

          // if (isDuplicate) {
          //   return state; // Skip duplicate
          // }

          // Just append - display events exactly as they arrive from backend
          const updated = [...existing, output];

          // Keep only last 1000 outputs per agent to prevent memory issues
          // const trimmed = updated.slice(-1000);

          outputs.set(agentName, updated);
          return { outputs };
        }),

      clearOutputs: (agentName) =>
        set((state) => {
          const outputs = new Map(state.outputs);
          outputs.delete(agentName);
          return { outputs };
        }),

      getOutputs: (agentName) => {
        const outputs = get().outputs.get(agentName) || [];
        return outputs;
      },
    }),
    { name: 'streamStore' }
  )
);
