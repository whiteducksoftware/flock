import { Message } from '../types/graph';

// UI Optimization Migration (Phase 4.1 - Spec 002): OLD Phase 1 mock data (unused)
// Kept for potential future testing, but Agent type no longer exists
type LegacyAgent = {
  id: string;
  name: string;
  status: string;
  subscriptions: string[];
  lastActive: number;
  sentCount: number;
  recvCount: number;
  position: { x: number; y: number };
};

export const mockAgents: LegacyAgent[] = [
  {
    id: 'movie',
    name: 'movie',
    status: 'idle',
    subscriptions: [],
    lastActive: Date.now() - 5000,
    sentCount: 3,
    recvCount: 0,
    position: { x: 100, y: 100 },
  },
  {
    id: 'tagline',
    name: 'tagline',
    status: 'running',
    subscriptions: ['Movie'],
    lastActive: Date.now() - 2000,
    sentCount: 2,
    recvCount: 3,
    position: { x: 400, y: 100 },
  },
  {
    id: 'reviewer',
    name: 'reviewer',
    status: 'idle',
    subscriptions: ['Tagline'],
    lastActive: Date.now() - 1000,
    sentCount: 0,
    recvCount: 2,
    position: { x: 700, y: 100 },
  },
];

export const mockMessages: Message[] = [
  {
    id: 'msg-1',
    type: 'Movie',
    payload: { title: 'The Matrix', year: 1999, genre: 'Sci-Fi' },
    timestamp: Date.now() - 10000,
    correlationId: 'corr-123',
    producedBy: 'movie',
  },
  {
    id: 'msg-2',
    type: 'Movie',
    payload: { title: 'Inception', year: 2010, genre: 'Sci-Fi' },
    timestamp: Date.now() - 8344,
    correlationId: 'corr-123',
    producedBy: 'movie',
  },
  {
    id: 'msg-3',
    type: 'Movie',
    payload: { title: 'Interstellar', year: 2014, genre: 'Sci-Fi' },
    timestamp: Date.now() - 6000,
    correlationId: 'corr-123',
    producedBy: 'movie',
  },
  {
    id: 'msg-4',
    type: 'Tagline',
    payload: { movie: 'The Matrix', tagline: 'Reality is not what it seems' },
    timestamp: Date.now() - 5000,
    correlationId: 'corr-123',
    producedBy: 'tagline',
  },
  {
    id: 'msg-5',
    type: 'Tagline',
    payload: { movie: 'Inception', tagline: 'Your mind is the scene of the crime' },
    timestamp: Date.now() - 3000,
    correlationId: 'corr-123',
    producedBy: 'tagline',
  },
];

export function initializeMockData() {
  // This will be called from main.tsx to populate stores
  return {
    agents: mockAgents,
    messages: mockMessages,
  };
}
