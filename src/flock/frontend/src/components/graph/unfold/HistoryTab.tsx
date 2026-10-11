import React, { useState } from 'react';
import ImageThumbnails from '../../common/ImageThumbnails';
import { shortTypeName } from '../../../utils/typeName';
import { clockTime, shortId } from './format';
import { useMessageHistory } from './messageHistory';
import styles from './Unfolded.module.css';

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

/** `◆ Route` for a decision, else the type without its module. */
export const TypeLabel: React.FC<{ type: string }> = ({ type }) => {
  const decision = /^(?:.*\.)?Decision\[(.+)\]$/.exec(type);
  if (!decision) return <>{shortTypeName(type)}</>;
  return (
    <>
      <span className={styles.diamond}>◆</span> {shortTypeName(decision[1]!)}
    </>
  );
};

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
  const { messages, error } = useMessageHistory(agent, revision);
  const [open, setOpen] = useState<Set<string>>(new Set());

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
                <TypeLabel type={message.type} />
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
