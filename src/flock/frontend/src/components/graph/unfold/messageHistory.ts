/** What an agent consumed and published, from `GET /api/artifacts/history/{agent}`. */

import { useEffect, useState } from 'react';
import type { ImageSummary } from '../../../utils/imageFields';

export interface Message {
  id: string;
  type: string;
  direction: 'consumed' | 'published';
  payload: unknown;
  images?: ImageSummary[];
  at: string;
  correlationId: string | null;
}

interface ApiMessage {
  id: string;
  type: string;
  direction: 'consumed' | 'published';
  payload: unknown;
  images?: ImageSummary[] | null;
  timestamp: string;
  consumed_at?: string | null;
  correlation_id?: string | null;
}

/** The agent's history, newest first; read again when `revision` (its message counts) changes. */
export function useMessageHistory(agent: string, revision: number): { messages: Message[] | null; error: string | null } {
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    fetch(`/api/artifacts/history/${encodeURIComponent(agent)}`)
      .then((response) => {
        if (!response.ok) throw new Error(`The history could not be read (${response.status})`);
        return response.json();
      })
      .then((data: { messages?: ApiMessage[] }) => {
        if (!current) return;
        setMessages(
          (data.messages ?? []).map((message) => ({
            id: message.id,
            type: message.type,
            direction: message.direction,
            payload: message.payload,
            images: message.images ?? undefined,
            at: message.consumed_at || message.timestamp,
            correlationId: message.correlation_id ?? null,
          })),
        );
        setError(null);
      })
      .catch((reason: unknown) => {
        if (current) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      current = false;
    };
  }, [agent, revision]);

  return { messages, error };
}
