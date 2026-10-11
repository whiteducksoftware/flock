import React from 'react';
import { useGraphStore } from '../../../store/graphStore';
import ImageThumbnails from '../../common/ImageThumbnails';
import type { AgentRun } from '../unfold/agentRuns';
import { count, duration, shortId } from '../unfold/format';
import { TypeLabel } from '../unfold/HistoryTab';
import LiveTab from '../unfold/LiveTab';
import type { Message } from '../unfold/messageHistory';
import styles from './Focus.module.css';
import { useRunInput } from './runInput';

/** The first fields of a payload, as text. */
const fieldsOf = (payload: unknown, limit = 6): [string, string][] =>
  payload && typeof payload === 'object'
    ? Object.entries(payload as Record<string, unknown>)
        .slice(0, limit)
        .map(([key, value]) => [key, typeof value === 'string' ? value : JSON.stringify(value)])
    : [];

const MessageCard: React.FC<{ title: string; message: Message | undefined; status?: React.ReactNode; empty?: string }> = ({
  title,
  message,
  status,
  empty = 'None yet',
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
      <>
        <div className={styles.kv}>
          {fieldsOf(message.payload).map(([key, value]) => (
            <React.Fragment key={key}>
              <span className="mono">{key}</span>
              <span>{value}</span>
            </React.Fragment>
          ))}
        </div>
        {message.images && message.images.length > 0 && <ImageThumbnails artifactId={message.id} images={message.images} />}
      </>
    ) : (
      <span className={styles.faint}>{empty}</span>
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
  // While it runs, the running run's inputs; the history has them only once the run has published
  const run = useRunInput(agent);
  // That run's output (the agent's ticker mixes overlapping runs); the ticker when no run is known
  const tail = useGraphStore((state) => (run.runId ? (state.runTails.get(run.runId) ?? '') : tokens.join('')));
  const inputs = running ? (run.inputs ?? []) : messages?.filter((message) => message.direction === 'consumed').slice(0, 1) ?? [];
  const output = messages?.find((message) => message.direction === 'published');
  const earlier = (runs ?? []).filter((run) => run.status !== 'active').slice(0, 3);

  return (
    <div className={styles.live}>
      <section aria-label="Live output">
        <LiveTab agent={agent} running={running} />
      </section>
      <aside className={styles.aside}>
        {inputs.length === 0 ? (
          <MessageCard
            title="Input"
            message={undefined}
            empty={!running ? 'None yet' : run.inputs === undefined ? 'Loading…' : 'Not known for this run'}
          />
        ) : (
          inputs.map((input, index) => (
            <MessageCard key={input.id} title={inputs.length > 1 ? `Input ${index + 1}` : 'Input'} message={input} />
          ))
        )}
        {running && run.more > 0 && <span className={styles.faint}>and {run.more} more consumed</span>}
        {running ? (
          // This run's output only; an earlier run's is not this one's
          <div className={styles.card}>
            <div className={styles.cardHead}>
              <span className={styles.label}>Output</span>
              <span className={`${styles.quiet} ${styles.end}`}>{tail ? 'streaming' : 'running'}</span>
            </div>
            {tail ? (
              <span className="mono">…{tail.slice(-160)}</span>
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
