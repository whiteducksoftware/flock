import React from 'react';
import type { AgentRun } from '../unfold/agentRuns';
import { count, duration, shortId } from '../unfold/format';
import { TypeLabel } from '../unfold/HistoryTab';
import LiveTab from '../unfold/LiveTab';
import type { Message } from '../unfold/messageHistory';
import styles from './Focus.module.css';

/** The first fields of a payload, as text. */
const fieldsOf = (payload: unknown, limit = 6): [string, string][] =>
  payload && typeof payload === 'object'
    ? Object.entries(payload as Record<string, unknown>)
        .slice(0, limit)
        .map(([key, value]) => [key, typeof value === 'string' ? value : JSON.stringify(value)])
    : [];

const MessageCard: React.FC<{ title: string; message: Message | undefined; status?: React.ReactNode }> = ({
  title,
  message,
  status,
}) => (
  <div className={styles.card}>
    <div className={styles.cardHead}>
      <span className={styles.label}>{title}</span>
      {message && (
        <span className="mono">
          <TypeLabel type={message.type} />
        </span>
      )}
      {status ?? (message && <span className={`mono ${styles.faint} ${styles.end}`}>{shortId(message.correlationId, 4)}</span>)}
    </div>
    {message ? (
      <div className={styles.kv}>
        {fieldsOf(message.payload).map(([key, value]) => (
          <React.Fragment key={key}>
            <span className="mono">{key}</span>
            <span>{value}</span>
          </React.Fragment>
        ))}
      </div>
    ) : (
      <span className={styles.faint}>None yet</span>
    )}
  </div>
);

interface FocusLiveProps {
  agent: string;
  running: boolean;
  messages: Message[] | null;
  runs: AgentRun[] | null;
  /** Live tokens of the running run */
  tokens: string[];
  onRuns: () => void;
}

/** The stream on the left; on the right what the agent works on, its output so far and earlier runs. */
const FocusLive: React.FC<FocusLiveProps> = ({ agent, running, messages, runs, tokens, onRuns }) => {
  const input = messages?.find((message) => message.direction === 'consumed');
  const output = messages?.find((message) => message.direction === 'published');
  const earlier = (runs ?? []).filter((run) => run.status !== 'active').slice(0, 3);

  return (
    <div className={styles.live}>
      <section aria-label="Live output">
        <LiveTab agent={agent} running={running} />
      </section>
      <aside className={styles.aside}>
        <MessageCard title="Input" message={input} />
        {running ? (
          // This run's output only; an earlier run's is not this one's
          <div className={styles.card}>
            <div className={styles.cardHead}>
              <span className={styles.label}>Output</span>
              <span className={`${styles.quiet} ${styles.end}`}>{tokens.length > 0 ? 'streaming' : 'running'}</span>
            </div>
            {tokens.length > 0 ? (
              <span className="mono">…{tokens.join('').slice(-160)}</span>
            ) : (
              <span className={styles.faint}>Waiting for output</span>
            )}
          </div>
        ) : (
          <MessageCard title="Output" message={output} />
        )}
        <div className={styles.card}>
          <span className={styles.label}>Earlier runs</span>
          {earlier.length === 0 ? (
            <span className={styles.faint}>None yet</span>
          ) : (
            earlier.map((run) => (
              <button key={run.runId} type="button" className={styles.run} onClick={onRuns}>
                <span className="mono">{shortId(run.runId)}</span>
                <span className={`mono num ${styles.quiet}`}>
                  {run.status === 'error' ? (run.errorType ?? 'failed') : run.durationMs === null ? '—' : duration(run.durationMs)}
                  {run.tokens !== null && ` · ${count(run.tokens)} tok`}
                </span>
              </button>
            ))
          )}
        </div>
      </aside>
    </div>
  );
};

export default FocusLive;
