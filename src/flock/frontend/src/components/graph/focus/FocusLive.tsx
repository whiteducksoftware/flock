import React from 'react';
import { useGraphStore } from '../../../store/graphStore';
import ImageThumbnails from '../../common/ImageThumbnails';
import { DecisionBars, type DeciderInfo, type DeciderQuestion, type DecisionInfo } from '../DecisionDisplay';
import type { AgentRun } from '../unfold/agentRuns';
import { count, duration, shortId } from '../unfold/format';
import { TypeLabel } from '../unfold/HistoryTab';
import LiveTab from '../unfold/LiveTab';
import type { Message } from '../unfold/messageHistory';
import styles from './Focus.module.css';
import { useRunInput } from './runInput';

/** Entries of a list or map shown before `… N more`. */
const PREVIEW_ENTRIES = 8;

/** A field's value as text; a long list or map stops after a few entries (a checklist has hundreds). */
export function preview(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value) && value.length > PREVIEW_ENTRIES) {
    return `${JSON.stringify(value.slice(0, PREVIEW_ENTRIES)).slice(0, -1)}, … ${value.length - PREVIEW_ENTRIES} more]`;
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value);
    if (entries.length > PREVIEW_ENTRIES) {
      return `${JSON.stringify(Object.fromEntries(entries.slice(0, PREVIEW_ENTRIES))).slice(0, -1)}, … ${entries.length - PREVIEW_ENTRIES} more}`;
    }
  }
  return JSON.stringify(value);
}

/** The first fields of a payload, as text. */
const fieldsOf = (payload: unknown, limit = 6): [string, string][] =>
  payload && typeof payload === 'object'
    ? Object.entries(payload as Record<string, unknown>)
        .slice(0, limit)
        .map(([key, value]) => [key, preview(value)])
    : [];

const DECISION = /^(?:.*\.)?Decision\[(.+)\]$/;

/**
 * A decision artifact's payload as the dashboard's decision view (`decision_view` in flock/decisions/graph.py).
 * A payload holds only the answers it got, so a scale's levels and a checklist's items in order come from the
 * decider's question (`questions`); a scale whose levels are unknown stays its payload.
 */
export function decisionOf(message: Message, questions: DeciderQuestion[] = []): DecisionInfo | null {
  if (!DECISION.test(message.type) || !message.payload || typeof message.payload !== 'object') return null;
  const p = message.payload as Record<string, unknown>;
  const kind = (p.kind as DecisionInfo['kind']) ?? 'choice';
  const question = questions.find((each) => each.name === p.question);
  if (kind === 'scale' && !question) return null;
  const results = (p.results as Record<string, string> | undefined) ?? {};
  return {
    question: String(p.question ?? ''),
    kind,
    choice: String(p.choice ?? ''),
    bestGuess: (p.best_guess as string | null | undefined) ?? null,
    probabilities: (p.probabilities as Record<string, number> | undefined) ?? {},
    confidence: (p.confidence as number | null | undefined) ?? null,
    threshold: (p.threshold as number | null | undefined) ?? null,
    model: String(p.model ?? ''),
    latencyMs: (p.latency_ms as number | null | undefined) ?? null,
    score: (p.score as number | null | undefined) ?? null,
    refused: Boolean(p.refused),
    ...(kind === 'checklist'
      ? {
          items: question?.options ?? Object.keys(results),
          results,
          refusedItems: (p.refused_items as string[] | undefined) ?? [],
        }
      : kind === 'scale'
        ? { levels: question!.options }
        : {}),
  };
}

export const MessageCard: React.FC<{
  title: string;
  message: Message | undefined;
  status?: React.ReactNode;
  empty?: string;
  /** The questions of the decider that published the message, for a decision's levels and items */
  questions?: DeciderQuestion[];
}> = ({ title, message, status, empty = 'None yet', questions }) => {
  const decision = message ? decisionOf(message, questions) : null;
  return (
    <div className={styles.card}>
      <div className={styles.cardHead}>
        <span className={styles.label}>{title}</span>
        {message && (
          <span className="mono">
            <TypeLabel type={message.type} />
          </span>
        )}
        {status ??
          (message && (
            <span className={`mono ${styles.faint} ${styles.end}`}>{shortId(message.correlationId, 4)}</span>
          ))}
      </div>
      {decision ? (
        // A decision reads as on the Blackboard, not as its payload (a checklist's are hundreds of probabilities)
        <DecisionBars decision={decision} header={false} />
      ) : message ? (
        <>
          <div className={styles.kv}>
            {fieldsOf(message.payload).map(([key, value]) => (
              <React.Fragment key={key}>
                <span className="mono">{key}</span>
                <span>{value}</span>
              </React.Fragment>
            ))}
          </div>
          {message.images && message.images.length > 0 && (
            <ImageThumbnails artifactId={message.id} images={message.images} />
          )}
        </>
      ) : (
        <span className={styles.faint}>{empty}</span>
      )}
    </div>
  );
};

/** The newest answer to each of the decider's questions, in the order of its questions. */
export function latestDecisions(messages: Message[], questions: DeciderQuestion[]): { message: Message; decision: DecisionInfo }[] {
  const newest = new Map<string, Message>();
  for (const message of messages) {
    const question = (message.payload as { question?: unknown } | null)?.question;
    if (message.direction === 'published' && typeof question === 'string' && !newest.has(question)) newest.set(question, message);
  }
  return questions.flatMap((question) => {
    const message = newest.get(question.name);
    const decision = message ? decisionOf(message, questions) : null;
    return message && decision ? [{ message, decision }] : [];
  });
}

/**
 * A decider streams nothing: its last answers take the stream's place, a checklist across the whole width.
 * Its first cards line up with the side column's; whether it runs, the stage's head says.
 */
export const FocusDecisions: React.FC<{ messages: Message[] | null; questions: DeciderQuestion[] }> = ({ messages, questions }) => {
  if (messages === null) return <div className={styles.empty}>Loading decisions…</div>;
  const latest = latestDecisions(messages, questions);
  if (latest.length === 0) return <div className={styles.empty}>No decisions yet</div>;
  return (
    <div className={styles.decisionGrid}>
      {latest.map(({ message, decision }) => (
        <div key={message.id} className={styles.card} data-kind={decision.kind}>
          <DecisionBars decision={decision} scroll={false} />
        </div>
      ))}
    </div>
  );
};

interface FocusLiveProps {
  agent: string;
  running: boolean;
  messages: Message[] | null;
  runs: AgentRun[] | null;
  /** Live tokens of the running run */
  tokens: string[];
  onRuns: () => void;
}

/**
 * The stream on the left; on the right what the agent works on, its output so far and earlier runs.
 * A decider shows its last decisions on the left, which are its output.
 */
const FocusLive: React.FC<FocusLiveProps> = ({ agent, running, messages, runs, tokens, onRuns }) => {
  // While it runs, the running run's inputs; the history has them only once the run has published
  const run = useRunInput(agent);
  // The agent's own questions when it decides: its output's scale levels and checklist items
  const questions = useGraphStore(
    (state) => (state.nodes.find((node) => node.id === agent)?.data as { decision?: DeciderInfo } | undefined)?.decision?.questions,
  );
  // That run's output (the agent's ticker mixes overlapping runs); the ticker when no run is known
  const tail = useGraphStore((state) => (run.runId ? (state.runTails.get(run.runId) ?? '') : tokens.join('')));
  const inputs = running ? (run.inputs ?? []) : messages?.filter((message) => message.direction === 'consumed').slice(0, 1) ?? [];
  const output = messages?.find((message) => message.direction === 'published');
  const earlier = (runs ?? []).filter((run) => run.status !== 'active').slice(0, 3);

  const decides = (questions?.length ?? 0) > 0;

  return (
    <div className={styles.live}>
      {decides ? (
        <section aria-label="Decisions">
          <FocusDecisions messages={messages} questions={questions!} />
        </section>
      ) : (
        <section aria-label="Live output">
          <LiveTab agent={agent} running={running} />
        </section>
      )}
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
        {decides ? null : running ? (
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
          <MessageCard title="Output" message={output} questions={questions} />
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
