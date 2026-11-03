import React from 'react';
import { AggregatorInfo, CoverageSummary, DeciderInfo, DeciderOptions } from '../DecisionDisplay';
import { lastText, type SinkInfo } from '../../sinks/deliveries';
import type { AgentRun } from './agentRuns';
import { count, usd } from './format';
import ReviewQueue from './ReviewQueue';
import styles from './Unfolded.module.css';

interface OverviewTabProps {
  runs: AgentRun[] | null;
  /** The card's live states: ticker, failure, schedule, open join, batch */
  states: React.ReactNode;
  decider?: DeciderInfo;
  aggregator?: AggregatorInfo;
  sink?: SinkInfo;
}

/** How many runs `GET /api/agents/{name}/runs` lists at most. */
const RUNS_LISTED = 50;

const Stat: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className={styles.stat}>
    <span className={styles.label}>{label}</span>
    <span className={`mono num ${styles.statValue}`}>{value}</span>
  </div>
);

/** What the agent is doing, what it decided, and its runs in numbers. */
const OverviewTab: React.FC<OverviewTabProps> = ({ runs, states, decider, aggregator, sink }) => {
  const finished = runs ?? [];
  const failed = finished.filter((run) => run.status === 'error').length;
  const tokens = finished.reduce((sum, run) => sum + (run.tokens ?? 0), 0);
  // Unpriced runs have no cost; the sum is of the priced ones
  const priced = finished.filter((run) => run.costUsd !== null);
  const cost = priced.reduce((sum, run) => sum + (run.costUsd ?? 0), 0);

  return (
    <div data-testid="overview">
      {states && <div className={styles.section}>{states}</div>}
      {decider && (
        <div className={styles.section}>
          <span className={styles.label}>Answers</span>
          <DeciderOptions decider={decider} />
        </div>
      )}
      {decider && <ReviewQueue decider={decider} />}
      {aggregator && (
        <div className={styles.section}>
          <span className={styles.label}>Coverage</span>
          <CoverageSummary aggregator={aggregator} />
        </div>
      )}
      {sink && (
        <section className={styles.section} aria-label="Deliveries">
          <span className={styles.label}>Deliveries</span>
          <div className={styles.stats}>
            <Stat label="Delivered" value={count(sink.delivered)} />
            <Stat label="Failed" value={count(sink.failed)} />
            <Stat label="Last" value={sink.last ? lastText(sink.last) : '—'} />
          </div>
          {sink.last && !sink.last.ok && sink.last.error && <p className={styles.error}>{sink.last.error}</p>}
        </section>
      )}
      <div className={styles.section}>
        {/* The server lists an agent's latest runs */}
        <span className={styles.label}>{finished.length >= RUNS_LISTED ? `Last ${RUNS_LISTED} runs` : 'Runs'}</span>
        <div className={styles.stats}>
          <Stat label="Runs" value={runs === null ? '…' : count(finished.length)} />
          <Stat label="Failed" value={runs === null ? '…' : count(failed)} />
          <Stat label="Tokens" value={runs === null ? '…' : count(tokens)} />
          <Stat label="Cost" value={runs === null ? '…' : priced.length > 0 ? usd(cost) : '—'} />
        </div>
      </div>
    </div>
  );
};

export default OverviewTab;
