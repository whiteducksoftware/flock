/**
 * An agent on the board, as a card or, zoomed out, as a chip
 * (docs/internal/design-system/README.md, Nodes: four levels).
 */

import { memo, useEffect, useRef, useState } from 'react';
import { Handle, NodeProps, Position, useStore } from '@xyflow/react';
import { v4 as uuidv4 } from 'uuid';
import { useModuleStore } from '../../store/moduleStore';
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
import { AggregatorInfo, CoverageSummary, DeciderInfo, DeciderOptions } from './DecisionDisplay';
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

const Tag: React.FC<{ tag: CardTag }> = ({ tag }) => (
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

/** Open the trace viewer on the failed run's correlation. */
const openTrace = (correlationId: string) => {
  useModuleStore.getState().addModule({
    id: uuidv4(),
    type: 'traceViewerJaeger',
    position: { x: 120, y: 120 },
    size: { width: 820, height: 520 },
    visible: true,
    search: correlationId,
  });
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
      <div className={styles.track} title={`${wait.collected} of ${wait.required}`}>
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

const AgentNode = memo(({ data, selected }: NodeProps) => {
  const agent = data as AgentData;
  const chip = useStore((state) => state.transform[2] < CHIP_ZOOM);
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
  const tokens = agent.streamingTokens ?? [];
  // Seconds since the snapshot came, on the monotonic clock (`now` re-renders every second)
  const age = agent.snapshotAt !== undefined ? (performance.now() - agent.snapshotAt) / 1000 : 0;
  const join = waits ? joinWait(operations, age) : null;
  const batch = waits ? batchWait(operations, age) : null;

  return (
    <div className={styles.card} data-status={status} data-selected={selected || undefined}>
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
      {status === 'running' && tokens.length > 0 && (
        <div className={`mono ${styles.ticker}`} data-testid="ticker">
          …{tokens.join('').slice(-48)}
          <span className={styles.caret}>▍</span>
        </div>
      )}
      {status === 'error' && <ErrorRow error={agent.lastError} />}
      {timer && <ScheduleLine timer={timer} now={now} />}
      {join && <JoinBox wait={join} />}
      {batch && <BatchBox wait={batch} />}
    </div>
  );
});

AgentNode.displayName = 'AgentNode';

export default AgentNode;
