/**
 * An agent unfolded on the board: its card header with description and
 * model, its ports, and tabs for everything about it
 * (docs/internal/design-system/README.md, Nodes: four levels).
 */

import React, { useId, useState } from 'react';
import { useUIStore } from '../../../store/uiStore';
import { Icon } from '../../icons/Icon';
import { nextTab } from '../tabKeys';
import type { AgentData, PortRow } from '../card/cardModel';
import type { AggregatorInfo, DeciderInfo } from '../DecisionDisplay';
import { useAgentRuns } from './agentRuns';
import { count } from './format';
import HistoryTab from './HistoryTab';
import LiveTab from './LiveTab';
import OverviewTab from './OverviewTab';
import RunsTab from './RunsTab';
import TracesTab from './TracesTab';
import styles from './Unfolded.module.css';

export type UnfoldTab = 'overview' | 'live' | 'history' | 'runs' | 'traces';

const TABS: { key: UnfoldTab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'live', label: 'Live' },
  { key: 'history', label: 'History' },
  { key: 'runs', label: 'Runs' },
  { key: 'traces', label: 'Traces' },
];

interface UnfoldedAgentProps {
  id: string;
  agent: AgentData & { description?: string | null; model?: string | null; sentCount?: number };
  status: 'idle' | 'running' | 'error';
  /** The card's status dot, tag and handles */
  dot: React.ReactNode;
  tag: React.ReactNode;
  handles: React.ReactNode;
  rows: PortRow[];
  /** The card's live states (ticker, failure, schedule, join, batch) for the Overview */
  states: React.ReactNode;
  decider?: DeciderInfo;
  aggregator?: AggregatorInfo;
  onOpenTrace: (correlationId: string) => void;
}

const UnfoldedAgent: React.FC<UnfoldedAgentProps> = ({
  id,
  agent,
  status,
  dot,
  tag,
  handles,
  rows,
  states,
  decider,
  aggregator,
  onOpenTrace,
}) => {
  const [tab, setTab] = useState<UnfoldTab>('overview');
  const messages = (agent.recvCount ?? 0) + (agent.sentCount ?? 0);
  const { runs, error } = useAgentRuns(id, agent.status, messages);
  const tabIds = useId();
  const model = decider
    ? [decider.model, decider.threshold !== null ? `threshold ${decider.threshold.toFixed(2)}` : null].filter(Boolean).join(' · ')
    : agent.model;
  const counts: Partial<Record<UnfoldTab, number>> = { history: messages, runs: runs?.length };

  return (
    <div className={styles.node} data-status={status} data-testid="unfolded" aria-label={`${agent.name ?? id}, unfolded`}>
      {handles}
      <div className={styles.header}>
        {dot}
        <span className={styles.name}>{agent.name ?? id}</span>
        <span className={styles.tagSlot}>{tag}</span>
        <span className={styles.state} data-status={status}>
          {status === 'running' ? 'running' : status === 'error' ? 'failed' : ''}
        </span>
        <button
          type="button"
          className="btn icon ghost nodrag"
          aria-label="Fold back to a card"
          title="Fold back to a card (Space)"
          onClick={(event) => {
            // The click would reach the node and unfold it again
            event.stopPropagation();
            useUIStore.getState().fold();
          }}
        >
          <Icon name="fold" size={15} />
        </button>
      </div>
      {(agent.description || model) && (
        <div className={styles.about}>
          {agent.description && (
            <span className={styles.description} title={agent.description}>
              {agent.description}
            </span>
          )}
          {model && <span className={`mono ${styles.model}`}>{model}</span>}
        </div>
      )}
      {rows.length > 0 && (
        <div className={styles.pills}>
          {rows.map((row, index) => (
            <div key={`${index}:${row.dir}:${row.type}`} className={styles.pill} title={row.type}>
              <span className={styles.pillDir}>{row.dir}</span>
              <span className="mono">
                {row.decision && <span className={styles.diamond}>◆ </span>}
                {row.label}
                {row.times > 1 && ` ×${row.times}`}
              </span>
              <span className={`mono num ${styles.pillCount}`}>{count(row.count)}</span>
            </div>
          ))}
        </div>
      )}
      <div role="tablist" aria-label={`About ${agent.name ?? id}`} className={`nodrag ${styles.tabs}`}>
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`${tabIds}-${key}`}
            aria-selected={tab === key}
            aria-controls={`${tabIds}-panel`}
            // Only the selected tab is in the Tab order; the arrows move between them
            tabIndex={tab === key ? 0 : -1}
            className={styles.tab}
            onClick={() => setTab(key)}
            onKeyDown={(event) => {
              const next = nextTab(
                TABS.map((entry) => entry.key),
                tab,
                event.key,
              );
              if (!next) return;
              event.preventDefault();
              setTab(next);
              document.getElementById(`${tabIds}-${next}`)?.focus();
            }}
          >
            {label}
            {/* The space is for the tab's name ("History 15"); the flex gap spaces the look */}
            {counts[key] !== undefined && ' '}
            {counts[key] !== undefined && <span className={`mono num ${styles.tabCount}`}>{count(counts[key]!)}</span>}
          </button>
        ))}
      </div>
      {/* Scrolls and selects text instead of moving the board */}
      <div
        id={`${tabIds}-panel`}
        role="tabpanel"
        aria-labelledby={`${tabIds}-${tab}`}
        className={`nodrag nowheel nopan ${styles.body}`}
        data-scroll
      >
        {tab === 'overview' && <OverviewTab runs={runs} states={states} decider={decider} aggregator={aggregator} />}
        {tab === 'live' && <LiveTab agent={id} running={status === 'running'} />}
        {tab === 'history' && <HistoryTab agent={id} revision={messages} />}
        {tab === 'runs' && <RunsTab runs={runs} error={error} />}
        {tab === 'traces' && <TracesTab agent={id} onOpenTrace={onOpenTrace} />}
      </div>
    </div>
  );
};

export default UnfoldedAgent;
