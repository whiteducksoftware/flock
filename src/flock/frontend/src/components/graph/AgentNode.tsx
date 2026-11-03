/**
 * An agent on the board, as a card or, zoomed out, as a chip
 * (docs/internal/design-system/README.md, Nodes: four levels).
 */

import { memo, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react';
import { Handle, NodeProps, Position, useStore } from '@xyflow/react';
import { useUIStore } from '../../store/uiStore';
import { Icon } from '../icons/Icon';
import {
  AgentData,
  batchWait,
  CardTag,
  formatAgo,
  formatClock,
  FoldedPorts,
  foldPorts,
  formatSpan,
  isFolded,
  joinWait,
  portRows,
  PortRow,
  tagOf,
} from './card/cardModel';
import { cardSizes } from './cardSizes';
import { AggregatorInfo, CoverageSummary, DeciderInfo, DeciderOptions, deciderLayout } from './DecisionDisplay';
import { lastText, type SinkInfo } from '../sinks/deliveries';
import { count } from './unfold/format';
import { MOVE_MS, prefersLessMotion } from './animatePositions';
import { RESIZE_THRESHOLD_PX } from './autoLayoutTrigger';
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

/** The rows of one direction a card leaves out: `+N more` with their summed count, the types in the tooltip. */
const FoldedRow: React.FC<{ fold: FoldedPorts }> = ({ fold }) => (
  <div
    className={styles.port}
    data-testid="ports-folded"
    title={fold.rows.map((row) => `${row.decision ? '◆ ' : ''}${row.label} ${row.count}`).join('\n')}
  >
    <span className={styles.dir}>{fold.dir}</span>
    <span className={`mono ${styles.type} ${styles.foldedType}`}>+{fold.rows.length} more</span>
    <Count value={fold.count} />
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

  // Making room for the unfolded node starts from its card's size; Auto-arrange
  // compares it with the last layout's (#655). Kept up to date also when the
  // card resizes without rendering (fonts loading)
  useLayoutEffect(() => {
    if (card.current) cardSizes.set(id, { width: card.current.offsetWidth, height: card.current.offsetHeight });
  });
  const shownAsCard = !chip && !unfolded;
  useEffect(() => {
    const element = card.current;
    if (!shownAsCard || !element || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => cardSizes.set(id, { width: element.offsetWidth, height: element.offsetHeight }));
    observer.observe(element);
    return () => observer.disconnect();
  }, [id, shownAsCard]);

  // A card that grows (a new row of thumbnails) opens the part it grew by while
  // the board lays itself out around it, instead of popping (#655)
  const lastHeight = useRef<number | null>(null);
  const opening = useRef<Animation | null>(null);
  const autoArrange = useUIStore((state) => state.autoLayoutEnabled);
  useLayoutEffect(() => {
    const element = card.current;
    if (!element) {
      lastHeight.current = null;
      return;
    }
    const was = lastHeight.current;
    const height = element.offsetHeight;
    lastHeight.current = height;
    if (was === null) return;
    // Smaller again before the opening ended: it would clip what is left
    if (height < was) {
      opening.current?.cancel();
      opening.current = null;
      return;
    }
    // Only when the board makes room (Auto-arrange); a board arranged by hand keeps still
    if (height - was < RESIZE_THRESHOLD_PX || !autoArrange || prefersLessMotion() || typeof element.animate !== 'function') return;
    // Growing again while it opens: from what it hides now, read before the opening is cancelled
    const clip = getComputedStyle(element).clipPath;
    const hidden = opening.current && clip?.startsWith('inset(') ? parseFloat(clip.slice(6).split(/\s+/)[2] ?? '0') || 0 : 0;
    opening.current?.cancel();
    opening.current = element.animate([{ clipPath: `inset(0px 0px ${hidden + height - was}px 0px)` }, { clipPath: 'inset(0px 0px 0px 0px)' }], {
      duration: MOVE_MS,
      // animatePositions' easeOut, for CSS
      easing: 'cubic-bezier(0.33, 1, 0.68, 1)',
    });
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

  // More than eight ports fold into `+N more` rows; the unfolded node shows them all
  const ports = foldPorts(rows);
  // Columns from four questions, compact rows (always a full 300 px column) from seven
  const layout = decider ? deciderLayout(decider.questions) : null;
  const columns = layout && (layout.compact || layout.columns.length > 1) ? layout.columns.length : 0;
  return (
    <div
      ref={card}
      className={styles.card}
      data-status={status}
      data-selected={selected || undefined}
      data-columns={columns || undefined}
      style={columns ? ({ '--columns': columns } as CSSProperties) : undefined}
    >
      {handles}
      <div className={styles.header}>
        {dot}
        <span className={styles.name}>{agent.name}</span>
        {tag && <Tag tag={tag} />}
      </div>
      {ports.length > 0 && (
        <div className={styles.ports}>
          {/* Two subscriptions can need the same type: the position tells them apart */}
          {ports.map((entry, index) =>
            isFolded(entry) ? (
              <FoldedRow key={`${entry.dir}:more`} fold={entry} />
            ) : (
              <Port key={`${index}:${entry.dir}:${entry.type}`} row={entry} />
            )
          )}
        </div>
      )}
      {decider && <DeciderOptions decider={decider} columns />}
      {aggregator && <CoverageSummary aggregator={aggregator} />}
      {sink && <DeliveryLine sink={sink} />}
      {states}
    </div>
  );
});

AgentNode.displayName = 'AgentNode';

export default AgentNode;
