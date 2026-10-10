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

export type QuestionKind = 'choice' | 'yesno' | 'scale';

export interface DeciderQuestion {
  name: string;
  kind: QuestionKind;
  instructions?: string;
  options: string[]; // scale: ordered levels, lowest first
  counts: Record<string, number>;
  refused?: number;
  meanScore?: number; // scale: mean probability-weighted level
  samples?: Record<string, DecisionSample[]>;
}

export interface DeciderInfo {
  model: string;
  threshold: number | null;
  questions: DeciderQuestion[];
}

export interface ImageSummary {
  path: string;
  mime: string;
  bytes: number;
  thumb: string;
}

export interface DecisionInfo {
  question: string;
  kind?: QuestionKind;
  choice: string;
  bestGuess: string | null;
  probabilities: Record<string, number>;
  levels?: string[]; // scale: ordered levels, lowest first
  score?: number | null; // scale: probability-weighted level
  refused?: boolean;
  confidence: number | null;
  threshold: number | null;
  model: string;
  latencyMs: number | null;
  subjectThumb?: string;
}

// Hover zoom for thumbnails (inline styles cannot express :hover)
const THUMB_CSS = `
  .decision-thumb { transition: transform 0.15s ease, box-shadow 0.15s ease; transform-origin: center; }
  .decision-thumb:hover { transform: scale(3.2); z-index: 1000; position: relative; opacity: 1 !important; box-shadow: 0 0 0 1px rgba(255,255,255,0.6), 0 8px 24px rgba(0,0,0,0.55); }
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

const KIND_GLYPH: Record<QuestionKind, string> = { choice: '◆', yesno: '✓✗', scale: '▂▄▆' };
const NO_COLOR = 'rgba(148, 163, 184, 0.55)';
const pct = (value: number) => `${Math.round(value * 1000) / 10}%`;

export const DecisionBadge = memo(({ questions, compact }: { questions: string[]; compact: boolean }) => (
  <span
    aria-label="Decision agent"
    title={`Decision agent: ${questions.join(', ')}`}
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
    ◆ {questions[0]}{questions.length > 1 ? ` +${questions.length - 1}` : ''}
  </span>
));
DecisionBadge.displayName = 'DecisionBadge';

/** Thumbnail lanes of the options that have decided images. */
const SampleLanes = memo(({ question }: { question: DeciderQuestion }) => {
  const rows = [...question.options, UNSURE].filter((option) => question.samples?.[option]?.length);
  return (
    <>
      {rows.map((option) => (
        <div key={option} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '48px', fontSize: '10px', fontFamily: 'var(--font-family-mono)', color: 'var(--color-text-tertiary)' }}>
            {option}
          </span>
          <ThumbLane option={option} samples={question.samples?.[option] ?? []} total={question.counts[option] ?? 0} />
        </div>
      ))}
    </>
  );
});
SampleLanes.displayName = 'SampleLanes';

/** Choice: one row per option with how often it was chosen (and its image lane). */
const ChoiceCounts = memo(({ question }: { question: DeciderQuestion }) => {
  const rows = [...question.options];
  if (UNSURE in question.counts) rows.push(UNSURE);
  const max = Math.max(1, ...rows.map((option) => question.counts[option] ?? 0));
  return (
    <>
      {rows.map((option) => {
        const count = question.counts[option] ?? 0;
        const unsure = option === UNSURE;
        const color = unsure ? 'var(--color-warning)' : DECISION_COLOR;
        const samples = question.samples?.[option] ?? [];
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
    </>
  );
});
ChoiceCounts.displayName = 'ChoiceCounts';

/** Yes/no: one bar split into yes, no and UNSURE shares. */
const YesNoCounts = memo(({ question }: { question: DeciderQuestion }) => {
  const parts: [string, string][] = [
    ['yes', DECISION_COLOR],
    ['no', NO_COLOR],
  ];
  if (UNSURE in question.counts) parts.push([UNSURE, 'var(--color-warning)']);
  const total = parts.reduce((sum, [option]) => sum + (question.counts[option] ?? 0), 0);
  return (
    <>
      <div style={{ display: 'flex', height: '8px', borderRadius: '4px', overflow: 'hidden', background: 'rgba(148, 163, 184, 0.15)' }}>
        {parts.map(([option, color]) => (
          <span
            key={option}
            data-testid="yesno-segment"
            data-option={option}
            title={`${option}: ${question.counts[option] ?? 0}`}
            style={{
              width: `${total ? ((question.counts[option] ?? 0) / total) * 100 : 0}%`,
              background: color,
              transition: 'width 0.3s ease',
            }}
          />
        ))}
      </div>
      <div style={{ display: 'flex', gap: '8px', fontSize: '10px', fontWeight: 700, fontFamily: 'var(--font-family-mono)' }}>
        {parts.map(([option, color]) => (
          <span key={option} style={{ color: option === 'no' ? 'var(--color-text-secondary)' : color }}>
            {option} {question.counts[option] ?? 0}
          </span>
        ))}
      </div>
      {question.samples && <SampleLanes question={question} />}
    </>
  );
});
YesNoCounts.displayName = 'YesNoCounts';

/** Scale: a histogram of the levels in order, with the mean weighted score. */
const ScaleCounts = memo(({ question }: { question: DeciderQuestion }) => {
  const levels = question.options;
  const max = Math.max(1, ...levels.map((level) => question.counts[level] ?? 0));
  const unsure = question.counts[UNSURE] ?? 0;
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'flex-end', height: '46px' }}>
        {levels.map((level, index) => {
          const count = question.counts[level] ?? 0;
          return (
            <div
              key={level}
              data-testid="scale-level"
              data-option={level}
              data-count={String(count)}
              title={`${level}: ${count}`}
              style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px', padding: '0 2px' }}
            >
              <span style={{ fontSize: '9px', fontWeight: 700, color: DECISION_TEXT }}>{count}</span>
              <span
                style={{
                  width: '100%',
                  height: `${Math.max((count / max) * 32, 2)}px`,
                  borderRadius: '3px 3px 0 0',
                  background: DECISION_COLOR,
                  opacity: 0.35 + (0.65 * (index + 1)) / levels.length,
                  transition: 'height 0.3s ease',
                }}
              />
            </div>
          );
        })}
      </div>
      <div style={{ position: 'relative', height: '1px', background: 'rgba(148, 163, 184, 0.35)' }}>
        {question.meanScore !== undefined && (
          <span
            data-testid="scale-mean"
            title={`mean score ${question.meanScore.toFixed(2)}`}
            style={{
              position: 'absolute',
              top: '-1px',
              left: `${((question.meanScore + 0.5) / levels.length) * 100}%`,
              transform: 'translateX(-50%)',
              width: 0,
              height: 0,
              borderLeft: '6px solid transparent',
              borderRight: '6px solid transparent',
              borderBottom: `8px solid ${DECISION_TEXT}`,
            }}
          />
        )}
      </div>
      <div style={{ display: 'flex', marginTop: '6px' }}>
        {levels.map((level) => (
          <span
            key={level}
            style={{
              flex: 1,
              textAlign: 'center',
              fontSize: '9px',
              fontFamily: 'var(--font-family-mono)',
              color: 'var(--color-text-tertiary)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {level}
          </span>
        ))}
      </div>
      {unsure > 0 && (
        <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-warning)', fontFamily: 'var(--font-family-mono)' }}>
          UNSURE {unsure}
        </span>
      )}
      {question.samples && <SampleLanes question={question} />}
    </>
  );
});
ScaleCounts.displayName = 'ScaleCounts';

/** Questions of a decision agent with how often each answer was given. */
export const DeciderOptions = memo(({ decider }: { decider: DeciderInfo }) => {
  const titled = decider.questions.length > 1;
  const hasSamples = decider.questions.some((question) => question.samples);
  return (
    <div
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
      {hasSamples && <style>{THUMB_CSS}</style>}
      {decider.questions.map((question, index) => (
        <div
          key={question.name}
          title={question.instructions}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            ...(index > 0 ? { borderTop: `1px dashed ${DECISION_BORDER}`, paddingTop: '6px', marginTop: '2px' } : {}),
          }}
        >
          {titled && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 700, color: DECISION_TEXT }}>
              <span aria-hidden style={{ fontSize: '10px', letterSpacing: '-1px', opacity: 0.85 }}>{KIND_GLYPH[question.kind] ?? '◆'}</span>
              <span>{question.name}</span>
            </div>
          )}
          {question.kind === 'yesno' ? (
            <YesNoCounts question={question} />
          ) : question.kind === 'scale' ? (
            <ScaleCounts question={question} />
          ) : (
            <ChoiceCounts question={question} />
          )}
          {question.refused ? (
            <span style={{ fontSize: '10px', color: 'var(--color-warning-light)', fontFamily: 'var(--font-family-mono)' }}>
              {question.refused} refused
            </span>
          ) : null}
        </div>
      ))}
      <div style={{ fontSize: '10px', color: 'var(--color-text-tertiary)', fontFamily: 'var(--font-family-mono)' }}>
        {decider.model}
        {decider.threshold !== null ? ` · threshold ${decider.threshold.toFixed(2)}` : ''}
      </div>
    </div>
  );
});
DeciderOptions.displayName = 'DeciderOptions';

const STONE = '#a8a29e';
const AMBER = '#f59e0b';
const VIOLET_TEXT = '#6d28d9';

/** Choice: probability per option, most probable first, with the threshold marker. */
const ChoiceBars = memo(({ decision }: { decision: DecisionInfo }) => {
  const options = Object.entries(decision.probabilities).sort((a, b) => b[1] - a[1]);
  return (
    <>
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
                color: chosen ? VIOLET_TEXT : '#78716c',
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
                  background: chosen ? DECISION_COLOR : bestGuess ? AMBER : STONE,
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
    </>
  );
});
ChoiceBars.displayName = 'ChoiceBars';

/** Yes/no: one bar, yes from the left and no from the right. Between the two
 * threshold markers neither answer is firm: the UNSURE zone. */
const YesNoBar = memo(({ decision }: { decision: DecisionInfo }) => {
  const yes = decision.probabilities.yes ?? 0;
  const color = (option: string) =>
    option === decision.choice ? DECISION_COLOR : option === decision.bestGuess ? AMBER : '#d6d3d1';
  const threshold = decision.threshold;
  const zone = threshold !== null && threshold > 0.5;
  return (
    <>
      <div
        data-testid="decision-yesno"
        data-yes={String(yes)}
        style={{ position: 'relative', display: 'flex', height: '14px', borderRadius: '7px', overflow: 'hidden', background: '#e7e5e4' }}
      >
        <span style={{ width: `${yes * 100}%`, background: color('yes') }} />
        <span style={{ flex: 1, background: color('no') }} />
        {zone && (
          <span
            data-testid="decision-unsure-zone"
            title={`UNSURE between ${(1 - threshold).toFixed(2)} and ${threshold.toFixed(2)}`}
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: pct(1 - threshold),
              width: pct(2 * threshold - 1),
              borderLeft: '2px solid rgba(68, 64, 60, 0.55)',
              borderRight: '2px solid rgba(68, 64, 60, 0.55)',
              background: 'repeating-linear-gradient(135deg, rgba(245, 158, 11, 0.22) 0 4px, transparent 4px 8px)',
            }}
          />
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontFamily: 'monospace', fontWeight: 600 }}>
        <span style={{ color: decision.choice === 'yes' ? VIOLET_TEXT : '#78716c' }}>{`yes ${Math.round(yes * 100)}%`}</span>
        <span style={{ color: decision.choice === 'no' ? VIOLET_TEXT : '#78716c' }}>{`no ${Math.round((1 - yes) * 100)}%`}</span>
      </div>
    </>
  );
});
YesNoBar.displayName = 'YesNoBar';

const SCALE_HEIGHT = 60;
const CARD_BG = '#fefce8'; // MessageNode background

/** Scale: probability per level in level order, the threshold as a line and
 * the probability-weighted score on the axis below. */
const ScaleBars = memo(({ decision }: { decision: DecisionInfo }) => {
  const levels = decision.levels ?? Object.keys(decision.probabilities);
  const score = decision.score ?? null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      <div style={{ position: 'relative', display: 'flex', alignItems: 'flex-end' }}>
        {levels.map((level, index) => {
          const probability = decision.probabilities[level] ?? 0;
          const chosen = level === decision.choice;
          const bestGuess = level === decision.bestGuess;
          return (
            <div
              key={level}
              data-testid="decision-option"
              data-option={level}
              data-chosen={String(chosen)}
              data-best-guess={String(bestGuess)}
              style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px', padding: '0 3px' }}
            >
              <span
                style={{
                  position: 'relative',
                  zIndex: 1,
                  padding: '0 3px',
                  borderRadius: '3px',
                  background: CARD_BG,
                  fontSize: '10px',
                  fontWeight: 600,
                  color: chosen ? VIOLET_TEXT : '#57534e',
                }}
              >
                {Math.round(probability * 100)}%
              </span>
              <span
                style={{
                  width: '100%',
                  height: `${Math.max(probability * SCALE_HEIGHT, 2)}px`,
                  borderRadius: '4px 4px 0 0',
                  background: chosen ? DECISION_COLOR : bestGuess ? AMBER : STONE,
                  opacity: chosen || bestGuess ? 1 : 0.45 + (0.4 * (index + 1)) / levels.length,
                }}
              />
            </div>
          );
        })}
        {decision.threshold !== null && (
          <span
            title={`threshold ${decision.threshold.toFixed(2)}`}
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: `${decision.threshold * SCALE_HEIGHT}px`,
              borderTop: '1px dashed rgba(68, 64, 60, 0.6)',
            }}
          />
        )}
      </div>
      <div style={{ position: 'relative', height: '2px', background: '#d6d3d1', borderRadius: '1px' }}>
        {score !== null && (
          <span
            data-testid="decision-score"
            title={`score ${score.toFixed(2)}`}
            style={{
              position: 'absolute',
              top: '-4px',
              left: `${((score + 0.5) / levels.length) * 100}%`,
              transform: 'translateX(-50%)',
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: DECISION_COLOR,
              border: '2px solid white',
              boxShadow: '0 0 0 1px rgba(109, 40, 217, 0.5)',
            }}
          />
        )}
      </div>
      <div style={{ display: 'flex', marginTop: '4px' }}>
        {levels.map((level) => (
          <span
            key={level}
            style={{
              flex: 1,
              textAlign: 'center',
              fontSize: '10px',
              fontFamily: 'monospace',
              fontWeight: level === decision.choice ? 700 : 500,
              color: level === decision.choice ? VIOLET_TEXT : '#78716c',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {level}
          </span>
        ))}
      </div>
    </div>
  );
});
ScaleBars.displayName = 'ScaleBars';

/** One decision: its answer drawn by question kind, with model and threshold. */
export const DecisionBars = memo(({ decision }: { decision: DecisionInfo }) => {
  const kind = decision.kind ?? 'choice';
  const unsure = decision.choice === UNSURE;
  const answer = decision.refused
    ? 'refused'
    : unsure
      ? `UNSURE (best guess ${decision.bestGuess})`
      : decision.choice;
  const score = kind === 'scale' && !decision.refused && decision.score != null ? ` · score ${decision.score.toFixed(2)}` : '';
  const amber = unsure || decision.refused;

  const bars = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: '12px', fontWeight: 700, color: amber ? '#b45309' : VIOLET_TEXT }}>
        {`◆ ${decision.question}: ${answer}${score}`}
      </div>
      {decision.refused ? (
        <div style={{ fontSize: '11px', color: '#78716c' }}>The model declined to answer; the decision routes to UNSURE.</div>
      ) : kind === 'yesno' ? (
        <YesNoBar decision={decision} />
      ) : kind === 'scale' ? (
        <ScaleBars decision={decision} />
      ) : (
        <ChoiceBars decision={decision} />
      )}
      <div style={{ fontSize: '10px', color: STONE, fontFamily: 'monospace' }}>
        {decision.model}
        {decision.latencyMs !== null ? ` · ${Math.round(decision.latencyMs)} ms` : ''}
        {decision.threshold !== null ? ` · threshold ${decision.threshold.toFixed(2)}` : ''}
      </div>
    </div>
  );

  if (!decision.subjectThumb) {
    return <div style={{ marginBottom: '10px' }}>{bars}</div>;
  }
  // The decided image next to its answer
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
          border: `3px solid ${amber ? AMBER : DECISION_COLOR}`,
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
