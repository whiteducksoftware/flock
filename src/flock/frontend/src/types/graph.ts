import { Node, Edge } from '@xyflow/react';

export interface Agent {
  id: string;
  name: string;
  status: 'idle' | 'running' | 'error';
  subscriptions: string[];
  lastActive: number;
  sentCount: number;
  recvCount: number;
  position?: { x: number; y: number };
  outputTypes?: string[]; // Artifact types this agent produces
  receivedByType?: Record<string, number>; // Count of messages received per type
  sentByType?: Record<string, number>; // Count of messages sent per type
  streamingTokens?: string[]; // Last 6 streaming tokens for news ticker effect
}

export interface Message {
  id: string;
  type: string;
  payload: any;
  timestamp: number;
  correlationId: string;
  producedBy: string;
  isStreaming?: boolean; // True while streaming, false when complete
  streamingText?: string; // Accumulated streaming text (raw)
}

export interface AgentNodeData extends Record<string, unknown> {
  name: string;
  status: 'idle' | 'running' | 'error';
  subscriptions: string[];
  outputTypes?: string[];
  sentCount: number;
  recvCount: number;
  receivedByType?: Record<string, number>;
  sentByType?: Record<string, number>;
  streamingTokens?: string[]; // Last 6 streaming tokens for news ticker effect
}

export interface MessageNodeData extends Record<string, unknown> {
  artifactType: string;
  payloadPreview: string;
  payload: any; // Full payload for display
  producedBy: string;
  consumedBy: string[];
  timestamp: number;
  isStreaming?: boolean; // True while streaming tokens
  streamingText?: string; // Raw streaming text
}

export type AgentViewNode = Node<AgentNodeData, 'agent'>;
export type MessageViewNode = Node<MessageNodeData, 'message'>;
export type GraphNode = AgentViewNode | MessageViewNode;
export type GraphEdge = Edge;
