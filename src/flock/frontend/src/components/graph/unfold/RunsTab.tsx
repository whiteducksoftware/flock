import React from 'react';
import type { AgentRun } from './agentRuns';
import { clockTime, count, duration, shortId, usd } from './format';
import styles from './Unfolded.module.css';

const Result: React.FC<{ run: AgentRun }> = ({ run }) => {
  if (run.status === 'active') {
    return (
      <span className={styles.running}>
        <span className="sdot run" aria-hidden /> running
      </span>
    );
  }
  if (run.status === 'error') return <span className={styles.failed}>{run.errorType ?? 'failed'}</span>;
  return (
    <span className={styles.quiet}>
      {run.artifacts} {run.artifacts === 1 ? 'artifact' : 'artifacts'}
    </span>
  );
};

/** The agent's runs: when, how long, the result, tokens and cost. */
const RunsTab: React.FC<{ runs: AgentRun[] | null; error: string | null }> = ({ runs, error }) => {
  if (error) return <div className={`${styles.empty} ${styles.failed}`}>{error}</div>;
  if (runs === null) return <div className={styles.empty}>Loading runs…</div>;
  if (runs.length === 0) return <div className={styles.empty}>No runs yet</div>;

  return (
    <div className={styles.rows} data-testid="runs">
      <div className={`${styles.row} ${styles.runRow} ${styles.head} ${styles.label}`}>
        <span>Run</span>
        <span>Started</span>
        <span>Took</span>
        <span>Result</span>
        <span>Tokens</span>
        <span>Cost</span>
      </div>
      {runs.map((run) => (
        <React.Fragment key={run.runId}>
          <div className={`${styles.row} ${styles.runRow}`} data-testid={`run-${run.runId}`}>
            <span className={`mono ${styles.quiet}`} title={run.runId}>
              {shortId(run.runId)}
            </span>
            <span className={`mono num ${styles.faint}`}>{clockTime(run.startedAt)}</span>
            <span className="mono num">{run.durationMs === null ? '—' : duration(run.durationMs)}</span>
            <Result run={run} />
            <span className="mono num">{run.tokens === null ? '—' : count(run.tokens)}</span>
            {/* No cost: a model of the run has no price */}
            <span className="mono num">{run.costUsd === null ? '—' : usd(run.costUsd)}</span>
          </div>
          {run.status === 'error' && run.errorMessage && <div className={`mono ${styles.error}`}>{run.errorMessage}</div>}
        </React.Fragment>
      ))}
    </div>
  );
};

export default RunsTab;
