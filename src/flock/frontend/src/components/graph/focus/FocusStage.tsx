/**
 * A node in focus: a full stage over the dimmed board, with its place in the
 * flow on top (docs/internal/design-system/README.md, Nodes: four levels).
 */

import React, { useEffect, useId, useRef, useState } from 'react';
import { useGraphStore } from '../../../store/graphStore';
import { useUIStore } from '../../../store/uiStore';
import { Icon } from '../../icons/Icon';
import { Tag } from '../AgentNode';
import { nextTab } from '../tabKeys';
import { type AgentData, formatAgo, tagOf } from '../card/cardModel';
import type { DeciderInfo } from '../DecisionDisplay';
import { useAgentRuns } from '../unfold/agentRuns';
import { count, duration } from '../unfold/format';
import { HistoryList } from '../unfold/HistoryTab';
import { useMessageHistory } from '../unfold/messageHistory';
import RunsTab from '../unfold/RunsTab';
import TracesTab from '../unfold/TracesTab';
import ContractTab from './ContractTab';
import FocusLive from './FocusLive';
import { lineageOf } from './lineage';
import styles from './Focus.module.css';
import { useSince } from './useSince';

type FocusTab = 'live' | 'history' | 'runs' | 'contract' | 'traces';

const TABS: { key: FocusTab; label: string }[] = [
  { key: 'live', label: 'Live' },
  { key: 'history', label: 'History' },
  { key: 'runs', label: 'Runs' },
  { key: 'contract', label: 'Contract' },
  { key: 'traces', label: 'Traces' },
];

type FocusData = AgentData & { description?: string | null; model?: string | null; sentCount?: number };

const dotClass = (status: string | undefined) => `sdot ${status === 'running' ? 'run' : status === 'error' ? 'err' : ''}`;

interface FocusStageProps {
  /** Opens the trace viewer on a correlation */
  onOpenTrace: (correlationId: string) => void;
}

const FocusStage: React.FC<FocusStageProps> = ({ onOpenTrace }) => {
  const id = useUIStore((state) => state.focusedNodeId);
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const node = nodes.find((candidate) => candidate.id === id);
  // Leaving the board (the other view) ends the focus
  useEffect(() => {
    if (id && !node) useUIStore.getState().unfocus();
  }, [id, node]);
  if (!id || !node) return null;
  return <Stage key={id} id={id} data={node.data as FocusData} nodes={nodes} edges={edges} onOpenTrace={onOpenTrace} />;
};

interface StageProps extends FocusStageProps {
  id: string;
  data: FocusData;
  nodes: ReturnType<typeof useGraphStore.getState>['nodes'];
  edges: ReturnType<typeof useGraphStore.getState>['edges'];
}

const Stage: React.FC<StageProps> = ({ id, data, nodes, edges, onOpenTrace }) => {
  const [tab, setTab] = useState<FocusTab>('live');
  const tabIds = useId();
  const back = useRef<HTMLButtonElement>(null);
  const status = data.status === 'running' ? 'running' : data.status === 'error' ? 'error' : 'idle';
  const messagesCount = (data.recvCount ?? 0) + (data.sentCount ?? 0);
  const { runs, error } = useAgentRuns(id, data.status, messagesCount);
  // Read once, for Live and History
  const { messages, error: historyError } = useMessageHistory(id, messagesCount);
  const active = runs?.find((run) => run.status === 'active');
  // Running: since the active run started (none yet: no duration); idle: since the last run ended
  const last = runs?.find((run) => run.status !== 'active');
  const lastEnd =
    last?.startedAt && last.durationMs !== null ? new Date(Date.parse(last.startedAt) + last.durationMs).toISOString() : (last?.startedAt ?? null);
  const since = useSince(status === 'running' ? (active?.startedAt ?? null) : lastEnd);
  const lineage = lineageOf(id, nodes, edges);
  const tag = tagOf(data);
  const decider = data.decision as DeciderInfo | undefined;
  const model = decider
    ? [decider.model, decider.threshold !== null ? `threshold ${decider.threshold.toFixed(2)}` : null].filter(Boolean).join(' · ')
    : data.model;
  const statusOf = (other: string) => (nodes.find((candidate) => candidate.id === other)?.data as AgentData | undefined)?.status;
  const focus = (other: string) => useUIStore.getState().focus(other);
  const counts: Partial<Record<FocusTab, number>> = { history: messagesCount, runs: runs?.length };

  // The stage takes the keyboard focus, and gives it back when it closes
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    back.current?.focus();
    return () => previous?.focus?.();
  }, []);

  const activity =
    status === 'running'
      ? `running${since !== null ? ` · ${duration(since * 1000)}` : ''}`
      : status === 'error'
        ? `failed${data.lastError?.type ? ` · ${data.lastError.type}` : ''}`
        : since !== null
          ? `last run ${formatAgo(since)}`
          : '';

  return (
    <div className={styles.overlay}>
      <div className={styles.scrim} aria-hidden onClick={() => useUIStore.getState().unfocus()} />
      {/* Not modal: the header (filters, publish) stays usable while a node is in focus */}
      <div role="dialog" aria-label={`${data.name ?? id} in focus`} className={`nodrag nowheel ${styles.stage}`}>
        <div className={styles.header}>
          <button ref={back} type="button" className={`btn ghost ${styles.back}`} onClick={() => useUIStore.getState().unfocus()}>
            <Icon name="chevronLeft" size={15} />
            <span>Board</span>
            <kbd className="kbd">Esc</kbd>
          </button>
          <span className={styles.divider} />
          <span className={dotClass(data.status)} role="img" aria-label={status === 'error' ? 'failed' : status} />
          <h1 className={styles.name}>{data.name ?? id}</h1>
          {tag && (
            <span className={styles.tagSlot}>
              <Tag tag={tag} />
            </span>
          )}
          {model && <span className={`mono ${styles.model}`}>{model}</span>}
          <span className={styles.activity} data-status={status}>
            {activity}
          </span>
          <button
            type="button"
            className="btn icon ghost"
            aria-label="Close focus mode"
            onClick={() => useUIStore.getState().unfocus()}
          >
            <Icon name="close" size={15} />
          </button>
        </div>
        {data.description && <p className={styles.description}>{data.description}</p>}
        <nav aria-label="Lineage" className={styles.lineage}>
          {lineage.upstream.map((entry) => (
            <React.Fragment key={`${entry.node}:${entry.label}`}>
              <button type="button" className={styles.entry} onClick={() => focus(entry.node)}>
                <span className={dotClass(statusOf(entry.node))} aria-hidden />
                <span>{entry.node}</span>
                <span className={`mono ${styles.entryType}`}>
                  {entry.decision && <span className={styles.diamond}>◆ </span>}
                  {entry.label}
                </span>
              </button>
              <span className={styles.arrow} aria-hidden>
                <Icon name="chevronRight" size={14} />
              </span>
            </React.Fragment>
          ))}
          <span className={styles.entry} aria-current="true">
            <span className={dotClass(data.status)} aria-hidden />
            <span>{data.name ?? id}</span>
          </span>
          {lineage.outputs.map((output) => (
            <React.Fragment key={output.type}>
              <span className={styles.arrow} aria-hidden>
                <Icon name="chevronRight" size={14} />
              </span>
              <span className={styles.entry} title={output.type}>
                <span className="mono">
                  {output.decision && <span className={styles.diamond}>◆ </span>}
                  {output.label}
                </span>
                {output.consumers.length === 0 && <span className={styles.none}>no consumers yet</span>}
              </span>
              {output.consumers.map((consumer) => (
                <button
                  key={`${consumer.node}:${consumer.label ?? ''}`}
                  type="button"
                  className={styles.entry}
                  onClick={() => focus(consumer.node)}
                >
                  <span className={dotClass(statusOf(consumer.node))} aria-hidden />
                  <span>{consumer.node}</span>
                  {consumer.label && <span className={`mono ${styles.entryType}`}>{consumer.label}</span>}
                </button>
              ))}
            </React.Fragment>
          ))}
        </nav>
        <div role="tablist" aria-label={`About ${data.name ?? id}`} className={styles.tabs}>
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              role="tab"
              id={`${tabIds}-${key}`}
              aria-selected={tab === key}
              aria-controls={`${tabIds}-panel`}
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
              {counts[key] !== undefined && ' '}
              {counts[key] !== undefined && <span className={`mono num ${styles.count}`}>{count(counts[key]!)}</span>}
            </button>
          ))}
        </div>
        {/* In the Tab order: Live and Contract may hold nothing focusable to scroll by */}
        <div
          id={`${tabIds}-panel`}
          role="tabpanel"
          aria-labelledby={`${tabIds}-${tab}`}
          tabIndex={0}
          className={styles.body}
          data-scroll
        >
          {tab === 'live' && (
            <FocusLive
              agent={id}
              running={status === 'running'}
              messages={messages}
              runs={runs}
              tokens={data.streamingTokens ?? []}
              onRuns={() => setTab('runs')}
            />
          )}
          {tab === 'history' && <HistoryList messages={messages} error={historyError} />}
          {tab === 'runs' && <RunsTab runs={runs} error={error} />}
          {tab === 'contract' && <ContractTab id={id} nodes={nodes} edges={edges} />}
          {tab === 'traces' && <TracesTab agent={id} onOpenTrace={onOpenTrace} />}
        </div>
      </div>
    </div>
  );
};

export default FocusStage;
