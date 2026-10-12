/**
 * An agent on the board, as a card or, zoomed out, as a chip
 * (docs/internal/design-system/README.md, Nodes: four levels).
 */

import { memo, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Handle, NodeProps, Position, useStore } from '@xyflow/react';
import { useUIStore } from '../../store/uiStore';
import { Icon } from '../icons/Icon';
import {
  AgentData,
  batchWait,
  CardTag,
  formatAgo,
  formatClock,
  formatSpan,
  joinWait,
  portRows,
  PortRow,
  tagOf,
} from './card/cardModel';
import { cardSizes } from './cardSizes';
import { AggregatorInfo, CoverageSummary, DeciderInfo, DeciderOptions } from './DecisionDisplay';
import { lastText, type SinkInfo } from '../sinks/deliveries';
import { count } from './unfold/format';
import { prefersLessMotion } from './animatePositions';
import UnfoldedAgent from './unfold/UnfoldedAgent';
import styles from './AgentNode.module.css';

/** Below this zoom the board shows chips instead of cards. */
export const CHIP_ZOOM = 0.55;

/** Expiry countdowns turn amber below this many seconds. */
const URGENT_SECONDS = 30;

/** The time now, ticking every second while `active`. */
const useNow = (active: boolean): number => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return now;
};

/** A count that flashes when it changes (the number, not its row). */
const Count: React.FC<{ value: number }> = ({ value }) => {
  const previous = useRef(value);
  const [flash, setFlash] = useState(false);
  useEffect(() => {
    if (previous.current === value) return;
    previous.current = value;
    setFlash(true);
    const timer = window.setTimeout(() => setFlash(false), 600);
    return () => window.clearTimeout(timer);
  }, [value]);
  return <span className={`mono num ${styles.count} ${flash ? styles.flash : ''}`}>{value}</span>;
};

export const Tag: React.FC<{ tag: CardTag }> = ({ tag }) => (
  <span className={styles.tag} data-testid="card-tag">
    {tag.kind === 'schedule' && <Icon name="scheduled" size={11} />}
    {tag.kind === 'decision' ? (
      <>
        <span className={styles.diamond}>◆</span>
        {/* Spaces for the text (screen readers); the gap spaces the look */}
        {` ${tag.text.replace(/^◆\s*/, '')}`}
        {tag.more > 0 && <span className={styles.more}>{` +${tag.more}`}</span>}
      </>
    ) : (
      tag.text
    )}
  </span>
);

const Port: React.FC<{ row: PortRow }> = ({ row }) => (
  <div className={styles.port} title={row.type}>
    <span className={styles.dir}>{row.dir}</span>
    <span className={`mono ${styles.type}`}>
      {row.decision && <span className={styles.diamond}>◆ </span>}
      {row.label}
      {row.times > 1 && <span className={styles.times}> ×{row.times}</span>}
    </span>
    <Count value={row.count} />
  </div>
);

/** Show a run's traces: the timeline dock's Traces tab, searching its correlation. */
export const openTrace = (correlationId: string) => {
  useUIStore.getState().openDock('traces', correlationId);
};

const ErrorRow: React.FC<{ error: AgentData['lastError'] }> = ({ error }) => {
  const at = error?.at ? new Date(error.at).toLocaleTimeString([], { hour12: false }) : null;
  const text = [error?.type ?? 'Failed', at].filter(Boolean).join(' · ');
  const correlationId = error?.correlationId;
  const content = (
    <>
      <Icon name="error" size={13} />
      <span className={`mono ${styles.errorText}`}>{text}</span>
    </>
  );
  return correlationId ? (
    <button
      type="button"
      className={`nodrag ${styles.error}`}
      title={`${error?.message ?? 'The run failed'} · open its trace`}
      onClick={() => openTrace(correlationId)}
    >
      {content}
    </button>
  ) : (
    <div className={styles.error} title={error?.message ?? undefined}>
      {content}
    </div>
  );
};

const ScheduleLine: React.FC<{ timer: NonNullable<AgentData['timerState']>; now: number }> = ({ timer, now }) => {
  const last = timer.last_fire_time ? (now - Date.parse(timer.last_fire_time)) / 1000 : null;
  // The timer counts its fires from 0
  const runs = [last !== null && `run ${timer.iteration + 1}`, last !== null && `last ${formatAgo(last)}`]
    .filter(Boolean)
    .join(' · ');
  let next: React.ReactNode = null;
  if (timer.is_completed) next = 'finished';
  else if (timer.is_stopped) next = 'stopped';
  else if (timer.next_fire_time) {
    next = (
      <>
        next in <span className={`mono num ${styles.strong}`}>{formatSpan((Date.parse(timer.next_fire_time) - now) / 1000)}</span>
      </>
    );
  }
  return (
    <div className={styles.schedule}>
      {next && <span>{next}</span>}
      {runs && <span className={styles.quiet}>{runs}</span>}
    </div>
  );
};

/** A sink's deliveries: how many went out, how many failed, and the last one. */
const DeliveryLine: React.FC<{ sink: SinkInfo }> = ({ sink }) => (
  <div className={styles.schedule} data-testid="deliveries">
    <span>
      <span className={`mono num ${styles.strong}`}>{count(sink.delivered)}</span> delivered
    </span>
    {sink.failed > 0 && (
      <span className={styles.failedCount}>
        <span className="mono num">{count(sink.failed)}</span> failed
      </span>
    )}
    {sink.last && <span className={sink.last.ok ? styles.quiet : styles.failedCount}>last {lastText(sink.last)}</span>}
  </div>
);

const JoinBox: React.FC<{ wait: NonNullable<ReturnType<typeof joinWait>> }> = ({ wait }) => {
  const share = wait.required > 0 ? Math.min(1, wait.collected / wait.required) : 0;
  const urgent = wait.secondsLeft !== null && wait.secondsLeft < URGENT_SECONDS;
  return (
    <div className={styles.wait} data-testid="join-wait">
      <div className={styles.waitHead}>
        <Icon name="join" size={13} />
        <span className={`mono ${styles.quietStrong}`}>{wait.key}</span>
        {wait.more > 0 && <span className={styles.quiet}>+{wait.more}</span>}
        {wait.secondsLeft !== null && (
          <span className={`mono num ${styles.end} ${urgent ? styles.urgent : styles.quietStrong}`}>
            {formatClock(wait.secondsLeft)}
          </span>
        )}
      </div>
      <div
        className={styles.track}
        title={`${wait.collected} of ${wait.required}`}
        role="progressbar"
        aria-label={`Join ${wait.key}`}
        aria-valuemin={0}
        aria-valuemax={wait.required}
        aria-valuenow={wait.collected}
      >
        <span className={styles.filled} style={{ width: `${share * 100}%` }} />
        <span className="hatch" style={{ width: `${(1 - share) * 100}%` }} />
      </div>
    </div>
  );
};

/** At most this many cells; a bigger batch is a bar. */
const MAX_CELLS = 24;

const BatchBox: React.FC<{ wait: NonNullable<ReturnType<typeof batchWait>> }> = ({ wait }) => {
  const target = wait.target;
  const urgent = wait.secondsLeft !== null && wait.secondsLeft < URGENT_SECONDS;
  return (
    <div className={styles.wait} data-testid="batch-wait">
      <div className={styles.waitHead}>
        <span className={`mono ${styles.quietStrong}`}>
          batch {wait.collected} / {target ?? '∞'}
        </span>
        {wait.secondsLeft !== null && (
          <span className={`${styles.end} ${styles.quiet}`}>
            or in{' '}
            <span className={`mono num ${urgent ? styles.urgent : styles.quietStrong}`}>{formatClock(wait.secondsLeft)}</span>
          </span>
        )}
      </div>
      {target !== null && target <= MAX_CELLS ? (
        <div className={styles.cells} style={{ gridTemplateColumns: `repeat(${target}, minmax(0, 1fr))` }}>
          {Array.from({ length: target }, (_, index) => (
            <span key={index} className={index < wait.collected ? styles.cellOn : `hatch ${styles.cell}`} />
          ))}
        </div>
      ) : (
        target !== null && (
          <div className={styles.track}>
            <span className={styles.filled} style={{ width: `${Math.min(1, wait.collected / target) * 100}%` }} />
            <span className="hatch" style={{ flex: 1 }} />
          </div>
        )
      )}
    </div>
  );
};

const AgentNode = memo(({ id, data, selected }: NodeProps) => {
  const agent = data as AgentData;
  // An unfolded node stays unfolded at any zoom; it is what the reader looks at
  const unfolded = useUIStore((state) => state.unfoldedNodeId === id);
  // Chips when zoomed out or while the timeline dock is expanded (the board is a strip then)
  const dockOpen = useUIStore((state) => state.dockOpen);
  const chip = (useStore((state) => state.transform[2] < CHIP_ZOOM) || dockOpen) && !unfolded;
  const card = useRef<HTMLDivElement>(null);
  const status = agent.status === 'running' ? 'running' : agent.status === 'error' ? 'error' : 'idle';
  const operations = agent.logicOperations ?? [];
  const timer = agent.scheduleSpec ? agent.timerState : undefined;
  const waits = operations.some((operation) => operation.waiting_state?.is_waiting);
  const now = useNow(!chip && (Boolean(timer) || waits));

  // Labelled: the color is not the only way to learn the status
  const dot = (
    <span
      className={`sdot ${status === 'running' ? 'run' : status === 'error' ? 'err' : ''}`}
      role="img"
      aria-label={status === 'error' ? 'failed' : status}
    />
  );
  const handles = (
    <>
      <Handle type="target" position={Position.Left} className={styles.handle} />
      <Handle type="source" position={Position.Right} className={styles.handle} />
    </>
  );

  // Making room for the unfolded node starts from its card's size
  useLayoutEffect(() => {
    if (card.current) cardSizes.set(id, { width: card.current.offsetWidth, height: card.current.offsetHeight });
  });

  // A card that comes back from being unfolded fades in instead of popping (#644)
  const wasUnfolded = useRef(unfolded);
  useLayoutEffect(() => {
    const element = card.current;
    if (wasUnfolded.current && !unfolded && element && !prefersLessMotion() && typeof element.animate === 'function') {
      element.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, easing: 'ease-out' });
    }
    wasUnfolded.current = unfolded;
  });

  if (chip) {
    return (
      <div className={styles.chip} data-status={status} data-selected={selected || undefined}>
        {handles}
        {dot}
        <span className={styles.name}>{agent.name}</span>
        <span className={`mono num ${styles.quiet}`}>{agent.recvCount ?? 0}</span>
      </div>
    );
  }

  const tag = tagOf(agent);
  const rows = portRows(agent);
  const decider = agent.decision as DeciderInfo | undefined;
  const aggregator = (data as Record<string, unknown>).coverage as AggregatorInfo | undefined;
  const sink = agent.sink;
  const tokens = agent.streamingTokens ?? [];
  // Seconds since the snapshot came, on the monotonic clock (`now` re-renders every second)
  const age = agent.snapshotAt !== undefined ? (performance.now() - agent.snapshotAt) / 1000 : 0;
  const join = waits ? joinWait(operations, age) : null;
  const batch = waits ? batchWait(operations, age) : null;
  const ticker = status === 'running' && tokens.length > 0 && (
    <div className={`mono ${styles.ticker}`} data-testid="ticker">
      …{tokens.join('').slice(-48)}
      <span className={styles.caret}>▍</span>
    </div>
  );
  const states = (ticker || status === 'error' || timer || join || batch) && (
    <>
      {ticker}
      {status === 'error' && <ErrorRow error={agent.lastError} />}
      {timer && <ScheduleLine timer={timer} now={now} />}
      {join && <JoinBox wait={join} />}
      {batch && <BatchBox wait={batch} />}
    </>
  );

  if (unfolded) {
    return (
      <UnfoldedAgent
        id={id}
        agent={agent}
        status={status}
        dot={dot}
        tag={tag && <Tag tag={tag} />}
        handles={handles}
        rows={rows}
        states={states}
        decider={decider}
        aggregator={aggregator}
        sink={sink}
        onOpenTrace={openTrace}
      />
    );
  }

  return (
    <div ref={card} className={styles.card} data-status={status} data-selected={selected || undefined}>
      {handles}
      <div className={styles.header}>
        {dot}
        <span className={styles.name}>{agent.name}</span>
        {tag && <Tag tag={tag} />}
      </div>
      {rows.length > 0 && (
        <div className={styles.ports}>
          {/* Two subscriptions can need the same type: the position tells them apart */}
          {rows.map((row, index) => (
            <Port key={`${index}:${row.dir}:${row.type}`} row={row} />
          ))}
        </div>
      )}
      {decider && <DeciderOptions decider={decider} />}
      {aggregator && <CoverageSummary aggregator={aggregator} />}
      {sink && <DeliveryLine sink={sink} />}
      {states}
    </div>
  );
});

AgentNode.displayName = 'AgentNode';

export default AgentNode;
