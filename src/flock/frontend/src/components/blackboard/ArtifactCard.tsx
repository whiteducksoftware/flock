/**
 * An artifact in a run lane: type, producer and two fields of its payload,
 * or a decision's answer. A click unfolds it in place with everything about
 * it, read by ID (docs/internal/design-system/README.md, Blackboard view).
 */

import React from 'react';
import { useUIStore } from '../../store/uiStore';
import { shortTypeName } from '../../utils/typeName';
import ImageThumbnails from '../common/ImageThumbnails';
import type { DecisionInfo } from '../graph/DecisionDisplay';
import { Icon } from '../icons/Icon';
import JsonAttributeRenderer from '../modules/JsonAttributeRenderer';
import { clockTime, shortId } from '../graph/unfold/format';
import type { ImageSummary } from '../../utils/imageFields';
import ArtifactBody from './ArtifactBody';
import type { LaneCard } from './lanes';
import { useArtifact } from './useArtifact';
import styles from './Blackboard.module.css';

const DECISION = /^(?:.*\.)?Decision\[(.+)\]$/;

/** `◆ Route` for a decision, else the type without its module path. */
const labelOf = (type: string | null): string => {
  if (!type) return '…';
  const question = DECISION.exec(type);
  return question ? `◆ ${shortTypeName(question[1]!)}` : shortTypeName(type);
};

const text = (value: unknown): string => (typeof value === 'string' ? value : JSON.stringify(value));

/** A decision's answer in one line: the option (or UNSURE and the best guess) and its probability. */
const DecisionLine: React.FC<{ decision: DecisionInfo }> = ({ decision }) => {
  if (decision.kind === 'checklist') {
    const results = Object.values(decision.results ?? {});
    const yes = results.filter((result) => result === 'yes').length;
    const unsure = results.filter((result) => result === 'UNSURE').length;
    return (
      <span className={`mono ${styles.quiet}`}>
        {yes}/{results.length} yes{unsure > 0 && ` · ${unsure} unsure`}
      </span>
    );
  }
  if (decision.refused) return <span className={styles.faint}>refused</span>;
  const unsure = decision.choice === 'UNSURE';
  const shown = unsure ? decision.bestGuess : decision.choice;
  const probability = shown ? (decision.probabilities[shown] ?? null) : null;
  return (
    <div className={styles.decision}>
      <span className={`mono ${unsure ? styles.unsure : styles.sure}`}>{unsure ? 'UNSURE' : decision.choice}</span>
      <span className={styles.track}>
        <span
          className={`${styles.fill} ${unsure ? `hatch ${styles.fillUnsure}` : ''}`}
          style={{ width: `${Math.round((probability ?? 0) * 100)}%` }}
        />
      </span>
      <span className="mono num">
        {unsure && shown && <span className={styles.faint}>{shown} </span>}
        {probability === null ? '' : probability.toFixed(2)}
      </span>
    </div>
  );
};

/** What a folded card shows under its header. */
const Summary: React.FC<{ card: LaneCard }> = ({ card }) => {
  const data = card.data as { payload?: unknown; decision?: DecisionInfo; streamingText?: string; images?: ImageSummary[] };
  if (card.state === 'pending') {
    return (
      <div className={`${styles.waiting} ${styles.wait}`} aria-label="Not published yet">
        <span className="hatch" />
        <span className="hatch" />
      </div>
    );
  }
  if (card.state === 'streaming') {
    const streamed = data.streamingText ?? '';
    return streamed ? (
      <span className={`mono ${styles.stream}`}>
        {streamed.slice(-140)}
        <span className={styles.caret}>▍</span>
      </span>
    ) : (
      <div className={`${styles.waiting} ${styles.wait}`}>
        <span className="hatch" />
      </div>
    );
  }
  if (data.decision) return <DecisionLine decision={data.decision} />;
  const rows = data.payload && typeof data.payload === 'object' ? Object.entries(data.payload as Record<string, unknown>).slice(0, 2) : [];
  // A stream that just ended, before the board's snapshot has its payload
  if (rows.length === 0 && data.streamingText) return <span className={`mono ${styles.stream}`}>{data.streamingText.slice(-140)}</span>;
  return (
    <>
      {rows.length > 0 && (
        <div className={styles.kv}>
          {rows.map(([key, value]) => (
            <React.Fragment key={key}>
              <span className={styles.clip}>{key}</span>
              <span className={styles.clip}>{text(value)}</span>
            </React.Fragment>
          ))}
        </div>
      )}
      {data.images && data.images.length > 0 && (
        // The thumbnails open the image viewer, not the card
        <div onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
          <ImageThumbnails artifactId={card.id} images={data.images} />
        </div>
      )}
    </>
  );
};

/** Everything about an unfolded artifact: its views, who consumed it, its payload and history, read by ID. */
const Unfolded: React.FC<{ card: LaneCard }> = ({ card }) => {
  const { artifact, error } = useArtifact(card.id);
  const data = card.data as {
    decision?: DecisionInfo;
    consumedBy?: string[];
    visibilityKind?: string;
    tags?: string[];
    correlationId?: string | null;
    payload?: unknown;
  };
  const consumers = artifact?.consumed_by ?? data.consumedBy ?? [];
  const meta: [string, React.ReactNode][] = [
    ...(data.decision?.model ? [['model', data.decision.model] as [string, React.ReactNode]] : []),
    ['consumed by', consumers.length > 0 ? consumers.join(', ') : <span className={styles.faint}>no one yet</span>],
    ['visibility', artifact?.visibility_kind ?? data.visibilityKind ?? '—'],
    ...((artifact?.tags ?? data.tags ?? []).length > 0 ? [['tags', (artifact?.tags ?? data.tags ?? []).join(', ')] as [string, React.ReactNode]] : []),
    ['run', <span className="mono" title={data.correlationId ?? ''}>{shortId(data.correlationId, 8) || '—'}</span>],
    ['time', clockTime(card.timestamp)],
    ['id', <span className="mono">{card.id}</span>],
  ];
  const consumptions = artifact?.consumptions;

  return (
    <>
      <ArtifactBody id={card.id} data={card.data} />
      <div className={styles.meta}>
        {meta.map(([key, value]) => (
          <React.Fragment key={key}>
            <span>{key}</span>
            <span>{value}</span>
          </React.Fragment>
        ))}
      </div>
      <div className={styles.section}>
        <span className={styles.label}>Payload</span>
        <JsonAttributeRenderer value={JSON.stringify(artifact?.payload ?? data.payload ?? {}, null, 2)} />
      </div>
      <div className={styles.section}>
        <span className={styles.label}>Consumed</span>
        {error ? (
          <span className={styles.faint}>{error}</span>
        ) : !artifact ? (
          <span className={styles.faint}>Loading…</span>
        ) : !consumptions || consumptions.length === 0 ? (
          <span className={styles.faint}>No one consumed it yet</span>
        ) : (
          <ul className={styles.history}>
            {consumptions.map((entry) => (
              <li key={`${entry.consumer}-${entry.run_id}-${entry.consumed_at}`}>
                <span>{entry.consumer}</span>
                <span className={`mono ${styles.faint}`}>{entry.run_id ? `run ${shortId(entry.run_id)}` : ''}</span>
                <span className={`mono num ${styles.faint}`}>{clockTime(entry.consumed_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
};

const ArtifactCard: React.FC<{ card: LaneCard }> = ({ card }) => {
  const unfolded = useUIStore((state) => state.unfoldedArtifactId === card.id);
  const decision = (card.data as { decision?: DecisionInfo }).decision;
  const pending = card.state === 'pending';
  const classes = [
    styles.card,
    unfolded && styles.unfolded,
    card.state === 'streaming' && styles.streaming,
    pending && styles.pending,
    decision?.choice === 'UNSURE' && styles.unsureCard,
  ]
    .filter(Boolean)
    .join(' ');
  const head = (
    <div className={styles.cardHead}>
      <span className={`mono ${styles.clip}`} title={card.type ?? undefined}>
        {labelOf(card.type)}
      </span>
      <span className={`${styles.by} ${styles.clip}`}>
        by {card.producedBy}
        {unfolded && decision?.latencyMs != null && ` · ${Math.round(decision.latencyMs)} ms`}
      </span>
    </div>
  );

  // Pending cards have nothing to unfold yet
  if (pending) {
    return (
      <div className={classes}>
        {head}
        <Summary card={card} />
      </div>
    );
  }
  if (unfolded) {
    return (
      <article className={classes} aria-label={`${labelOf(card.type)} by ${card.producedBy}`}>
        <div className={styles.unfoldedHead}>
          {head}
          <button
            type="button"
            className="btn icon ghost sm"
            aria-label="Fold"
            onClick={() => useUIStore.getState().foldArtifact()}
          >
            <Icon name="fold" size={14} />
          </button>
        </div>
        <Unfolded card={card} />
      </article>
    );
  }
  return (
    <div
      className={classes}
      role="button"
      tabIndex={0}
      aria-expanded={false}
      aria-label={`${labelOf(card.type)} by ${card.producedBy}`}
      onClick={() => useUIStore.getState().unfoldArtifact(card.id)}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget || (event.key !== 'Enter' && event.key !== ' ')) return;
        event.preventDefault();
        useUIStore.getState().unfoldArtifact(card.id);
      }}
    >
      {head}
      <Summary card={card} />
    </div>
  );
};

export default ArtifactCard;
