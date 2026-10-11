import React, { useEffect, useState } from 'react';
import ImageThumbnails from '../../common/ImageThumbnails';
import type { ImageSummary } from '../../../utils/imageFields';
import { shortTypeName } from '../../../utils/typeName';
import { clockTime, shortId } from './format';
import styles from './Unfolded.module.css';

interface Message {
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

/** One line of a payload: a decision's answer, else its first text, else its JSON. */
export function summary(payload: unknown): string {
  if (payload === null || typeof payload !== 'object') return String(payload ?? '');
  const record = payload as Record<string, unknown>;
  if (typeof record.choice === 'string') {
    const probability = typeof record.probability === 'number' ? ` · ${record.probability.toFixed(2)}` : '';
    return `${record.choice}${probability}`;
  }
  const text = Object.values(record).find((value) => typeof value === 'string' && value.trim() !== '');
  return typeof text === 'string' ? text : JSON.stringify(payload);
}

const json = (payload: unknown): string => {
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
};

/**
 * What the agent consumed (↓) and published (↑), newest first; a row opens
 * its payload. Read again when the agent's counts change.
 */
const HistoryTab: React.FC<{ agent: string; revision: number }> = ({ agent, revision }) => {
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());

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

  const toggle = (id: string) =>
    setOpen((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (error) return <div className={`${styles.empty} ${styles.failed}`}>{error}</div>;
  if (messages === null) return <div className={styles.empty}>Loading history…</div>;
  if (messages.length === 0) return <div className={styles.empty}>No messages yet</div>;

  return (
    <div className={styles.rows} data-testid="history">
      <div className={`${styles.row} ${styles.historyRow} ${styles.head} ${styles.label}`}>
        <span>Time</span>
        <span />
        <span>Type</span>
        <span>Content</span>
        <span>Run</span>
      </div>
      {messages.map((message) => {
        const consumed = message.direction === 'consumed';
        const expanded = open.has(message.id);
        return (
          <React.Fragment key={`${message.direction}:${message.id}`}>
            <button
              type="button"
              className={`${styles.row} ${styles.historyRow} ${styles.rowButton}`}
              aria-expanded={expanded}
              onClick={() => toggle(message.id)}
            >
              <span className={`mono num ${styles.faint}`}>{clockTime(message.at)}</span>
              <span className={styles.faint} title={consumed ? 'Consumed' : 'Published'} aria-label={consumed ? 'Consumed' : 'Published'}>
                {consumed ? '↓' : '↑'}
              </span>
              <span className="mono" title={message.type}>
                {shortTypeName(message.type)}
              </span>
              <span className={styles.quiet}>{summary(message.payload)}</span>
              <span className={`mono ${styles.faint}`} title={message.correlationId ?? undefined}>
                {shortId(message.correlationId, 4)}
              </span>
            </button>
            {expanded && (
              <div>
                <pre className={`mono ${styles.payload}`}>{json(message.payload)}</pre>
                {message.images && <ImageThumbnails artifactId={message.id} images={message.images} />}
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

export default HistoryTab;
