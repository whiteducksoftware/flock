import { memo } from 'react';

/**
 * Decision models: displays for decision agents (Agent View) and decision
 * artifacts (Blackboard View). Backend fields: GraphAssembler node data
 * `decision` (see flock.decisions.graph).
 */

export const DECISION_COLOR = 'rgb(139, 92, 246)';
export const DECISION_TEXT = 'rgb(167, 139, 250)';
const DECISION_BG = 'rgba(139, 92, 246, 0.12)';
const DECISION_BORDER = 'rgba(139, 92, 246, 0.4)';
const UNSURE = 'UNSURE';

export interface DecisionSample {
  thumb: string;
  p: number;
}

export interface DeciderInfo {
  question: string;
  instructions?: string;
  options: string[];
  threshold: number | null;
  model: string;
  counts: Record<string, number>;
  samples?: Record<string, DecisionSample[]>;
}

export interface ImageSummary {
  path: string;
  mime: string;
  bytes: number;
  thumb: string;
}

export interface DecisionInfo {
  question: string;
  choice: string;
  bestGuess: string;
  probabilities: Record<string, number>;
  confidence: number | null;
  threshold: number | null;
  model: string;
  latencyMs: number | null;
  subjectThumb?: string;
}

// Hover zoom for thumbnails (inline styles cannot express :hover)
const THUMB_CSS = `
  .decision-thumb { transition: transform 0.15s ease, box-shadow 0.15s ease; transform-origin: center; }
  .decision-thumb:hover { transform: scale(3.2); z-index: 50; position: relative; box-shadow: 0 6px 18px rgba(0,0,0,0.45); }
`;

/** The latest images that landed in one option, newest first. */
const ThumbLane = memo(
  ({ option, samples, total }: { option: string; samples: DecisionSample[]; total: number }) => {
    const unsure = option === UNSURE;
    const color = unsure ? 'var(--color-warning)' : DECISION_COLOR;
    const hidden = total - samples.length;
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px', margin: '2px 0 4px 0' }}>
        {samples.map((sample, index) => {
          const label = `${option} · p ${sample.p.toFixed(2)}`;
          return (
            <img
              key={index}
              className="decision-thumb nodrag"
              src={sample.thumb}
              alt={label}
              title={label}
              style={{
                width: '26px',
                height: '26px',
                objectFit: 'cover',
                borderRadius: '5px',
                border: `1.5px solid ${color}`,
                opacity: unsure ? 0.8 : 1,
              }}
            />
          );
        })}
        {hidden > 0 && (
          <span
            style={{
              fontSize: '10px',
              fontWeight: 700,
              color,
              padding: '1px 5px',
              borderRadius: '999px',
              border: `1px solid ${color}`,
            }}
          >
            +{hidden}
          </span>
        )}
      </div>
    );
  }
);
ThumbLane.displayName = 'ThumbLane';

export const DecisionBadge = memo(({ question, compact }: { question: string; compact: boolean }) => (
  <span
    aria-label="Decision agent"
    title="Decision agent: answers a Choice question with a decision model"
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: compact ? '1px 6px' : '2px 8px',
      borderRadius: '999px',
      background: DECISION_BG,
      border: `1px solid ${DECISION_BORDER}`,
      color: DECISION_TEXT,
      fontSize: compact ? '10px' : '11px',
      fontWeight: 700,
      lineHeight: 1.2,
      whiteSpace: 'nowrap',
    }}
  >
    ◆ {question}
  </span>
));
DecisionBadge.displayName = 'DecisionBadge';

/** Options of a decision agent with how often each was chosen. */
export const DeciderOptions = memo(({ decider }: { decider: DeciderInfo }) => {
  const rows = [...decider.options];
  if (UNSURE in decider.counts) rows.push(UNSURE);
  const max = Math.max(1, ...rows.map((option) => decider.counts[option] ?? 0));

  return (
    <div
      title={decider.instructions}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        padding: '6px 10px',
        background: DECISION_BG,
        borderLeft: `3px solid ${DECISION_COLOR}`,
        borderRadius: 'var(--radius-md)',
      }}
    >
      {decider.samples && <style>{THUMB_CSS}</style>}
      {rows.map((option) => {
        const count = decider.counts[option] ?? 0;
        const unsure = option === UNSURE;
        const color = unsure ? 'var(--color-warning)' : DECISION_COLOR;
        const samples = decider.samples?.[option] ?? [];
        return (
          <div key={option}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span
              style={{
                width: '84px',
                fontSize: '11px',
                fontFamily: 'var(--font-family-mono)',
                color: unsure ? 'var(--color-warning-light)' : 'var(--color-text-secondary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {option}
            </span>
            <span style={{ flex: 1, height: '6px', borderRadius: '3px', background: 'rgba(148, 163, 184, 0.15)' }}>
              <span
                style={{
                  display: 'block',
                  height: '100%',
                  width: `${(count / max) * 100}%`,
                  borderRadius: '3px',
                  background: color,
                  transition: 'width 0.3s ease',
                }}
              />
            </span>
            <span style={{ minWidth: '22px', textAlign: 'right', fontSize: '11px', fontWeight: 700, color }}>
              {count}
            </span>
          </div>
          {samples.length > 0 && <ThumbLane option={option} samples={samples} total={count} />}
          </div>
        );
      })}
      <div style={{ fontSize: '10px', color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-family-mono)' }}>
        {decider.model}
        {decider.threshold !== null ? ` · threshold ${decider.threshold.toFixed(2)}` : ''}
      </div>
    </div>
  );
});
DeciderOptions.displayName = 'DeciderOptions';

/** One decision: probability per option, chosen option, threshold marker. */
export const DecisionBars = memo(({ decision }: { decision: DecisionInfo }) => {
  const options = Object.entries(decision.probabilities).sort((a, b) => b[1] - a[1]);
  const unsure = decision.choice === UNSURE;

  const bars = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: '12px', fontWeight: 700, color: unsure ? '#b45309' : '#6d28d9' }}>
        ◆ {decision.question}: {unsure ? `UNSURE (best guess ${decision.bestGuess})` : decision.choice}
      </div>
      {options.map(([option, probability]) => {
        const chosen = option === decision.choice;
        const bestGuess = option === decision.bestGuess;
        return (
          <div
            key={option}
            data-testid="decision-option"
            data-option={option}
            data-chosen={String(chosen)}
            data-best-guess={String(bestGuess)}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <span
              style={{
                width: '120px',
                fontSize: '11px',
                fontFamily: 'monospace',
                fontWeight: chosen ? 700 : 500,
                color: chosen ? '#6d28d9' : '#78716c',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {chosen ? '✔ ' : ''}
              {option}
            </span>
            <span style={{ position: 'relative', flex: 1, height: '10px', borderRadius: '5px', background: '#e7e5e4' }}>
              <span
                style={{
                  display: 'block',
                  height: '100%',
                  width: `${Math.max(probability * 100, 1)}%`,
                  borderRadius: '5px',
                  background: chosen ? DECISION_COLOR : bestGuess ? '#f59e0b' : '#a8a29e',
                }}
              />
              {decision.threshold !== null && (
                <span
                  title={`threshold ${decision.threshold.toFixed(2)}`}
                  style={{
                    position: 'absolute',
                    top: '-2px',
                    bottom: '-2px',
                    left: `${decision.threshold * 100}%`,
                    width: '2px',
                    background: '#44403c',
                    opacity: 0.6,
                  }}
                />
              )}
            </span>
            <span style={{ width: '36px', textAlign: 'right', fontSize: '11px', fontWeight: 600, color: '#57534e' }}>
              {Math.round(probability * 100)}%
            </span>
          </div>
        );
      })}
      <div style={{ fontSize: '10px', color: '#a8a29e', fontFamily: 'monospace' }}>
        {decision.model}
        {decision.latencyMs !== null ? ` · ${Math.round(decision.latencyMs)} ms` : ''}
        {decision.threshold !== null ? ` · threshold ${decision.threshold.toFixed(2)}` : ''}
      </div>
    </div>
  );

  if (!decision.subjectThumb) {
    return <div style={{ marginBottom: '10px' }}>{bars}</div>;
  }
  // The decided image next to its probabilities
  return (
    <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start', marginBottom: '10px' }}>
      <img
        src={decision.subjectThumb}
        alt="decided image"
        style={{
          width: '88px',
          height: '88px',
          objectFit: 'cover',
          borderRadius: '8px',
          border: `3px solid ${unsure ? '#f59e0b' : DECISION_COLOR}`,
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          flexShrink: 0,
        }}
      />
      {bars}
    </div>
  );
});
DecisionBars.displayName = 'DecisionBars';

/** Thumbnails of the image fields of an artifact. */
export const ImageStrip = memo(({ images }: { images: ImageSummary[] }) => (
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '10px' }}>
    {images.map((image) => (
      <figure key={image.path} style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <img
          src={image.thumb}
          alt={image.path}
          style={{
            maxWidth: '160px',
            maxHeight: '160px',
            borderRadius: '8px',
            border: '1px solid #e7e5e4',
            boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
          }}
        />
        <figcaption style={{ fontSize: '10px', color: '#a8a29e', fontFamily: 'monospace' }}>
          {image.path} · {image.mime} · {Math.max(1, Math.round(image.bytes / 1024))} KB
        </figcaption>
      </figure>
    ))}
  </div>
));
ImageStrip.displayName = 'ImageStrip';
