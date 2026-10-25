import { memo, useState, type ReactNode } from 'react';
import { reviewDecision } from '../../services/api';
import { useGraphStore } from '../../store/graphStore';
import { Icon } from '../icons/Icon';
import { TournamentBracket } from './TournamentBracket';
import styles from './DecisionDisplay.module.css';

/**
 * Decision models: displays for decision agents (Agent View) and decision
 * artifacts (Blackboard View). Backend fields: GraphAssembler node data
 * `decision` (see flock.decisions.graph). The encodings are the decision kit
 * of docs/internal/design-system/README.md: blue is a decided answer, the
 * hatch is unsure, dashed outlines are best guesses and refusals, coral is
 * failed.
 */

const UNSURE = 'UNSURE';

export interface DecisionSample {
  thumb: string;
  p: number;
}

export type QuestionKind = 'choice' | 'yesno' | 'scale' | 'checklist';

export interface DeciderQuestion {
  name: string;
  kind: QuestionKind;
  instructions?: string;
  options: string[]; // scale: ordered levels, lowest first
  counts: Record<string, number>;
  refused?: number;
  meanScore?: number; // scale: mean probability-weighted level
  itemStats?: number[][]; // checklist: [yes, no, unsure] per item, in item order
  descriptions?: Record<string, string>; // checklist: item -> requirement
  samples?: Record<string, DecisionSample[]>;
}

/** An unsure decision of a decider that no person reviewed yet (the graph snapshot carries them, #610). */
export interface ReviewItem {
  id: string;
  question: string;
  correlationId: string | null;
  bestGuess: string | null;
  probabilities: Record<string, number>;
  /** The options a person can choose */
  options: string[] | null;
  /** A field that names the decided artifact, else its first text */
  subjectTitle: string | null;
}

export interface DeciderInfo {
  model: string;
  threshold: number | null;
  questions: DeciderQuestion[];
  tournament?: { groupSize: number; keep: number };
  escalate?: string[]; // models asked after `model`, in order, when it is not sure
  ensemble?: string[]; // models that all answer every question (instead of `model`)
  vote?: string; // how the ensemble decides: majority, unanimous or mean
  shadow?: { model: string; compared: number; agree: number }; // shadow model and its agreement
  itemThresholds?: Record<string, number>; // checklist items with their own threshold
  needsReview?: ReviewItem[]; // its unsure decisions no one reviewed, newest first (at most 20)
  needsReviewCount?: number; // how many there are
}

export interface ShadowAnswer {
  model: string;
  choice?: string;
  best_guess?: string | null;
  probabilities?: Record<string, number>;
  confidence?: number | null;
  refused?: boolean;
  results?: Record<string, string>; // checklist
  latency_ms?: number;
  error?: string; // the shadow failed; the decision did not
}

export interface EscalationAttempt {
  model: string;
  choice?: string | null;
  probabilities?: Record<string, number>;
  confidence?: number | null;
  refused?: boolean;
  results?: Record<string, string>; // checklist: the escalated items and their results
}

export interface TournamentGroupResult {
  size: number;
  refused: boolean;
  top: [string, number][]; // survivors first, then the strongest eliminated options
}

export interface TournamentRound {
  candidates: number;
  groups: number;
  group_size?: number;
  refused_groups?: number; // groups where no option fits (the model refused)
  survivors: string[];
  group_results?: TournamentGroupResult[];
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
  items?: string[]; // checklist: items in order
  results?: Record<string, string>; // checklist: yes | no | UNSURE per item
  refusedItems?: string[];
  rounds?: TournamentRound[]; // tournament: rounds before the final question
  candidates?: string[]; // options= restricted the question to these options
  tier?: number; // escalation tier that answered (0: the decider's model)
  attempts?: EscalationAttempt[]; // lower tiers that were not sure, oldest first
  votes?: EscalationAttempt[]; // ensemble: every model's answer, in model order
  shadow?: ShadowAnswer; // shadow mode: what the shadow model decided (never routed)
  sections?: { field: string; spans: number[][]; answeredBy: Record<string, number> }; // long documents
  review?: { choice: string; by: string | null }; // the latest review of this decision
  reviewOf?: string; // this decision is a person's review of that decision
  itemThresholds?: Record<string, number>; // checklist items with their own threshold
  options?: string[]; // the question's options, for a review (also of a refusal)
  explanation?: { explanation: string; missing?: string | null; model: string; by?: string | null }; // latest LLM explanation
  confidence: number | null;
  threshold: number | null;
  model: string;
  latencyMs: number | null;
  subjectThumb?: string;
}

const cx = (...names: (string | false | null | undefined)[]) => names.filter(Boolean).join(' ');
const pct = (value: number) => `${Math.round(value * 1000) / 10}%`;
const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

const KIND_LABEL: Record<QuestionKind, string> = { choice: 'Choice', yesno: 'Yes / No', scale: 'Scale', checklist: 'Checklist' };

type MarkKind = 'sure' | 'unsure' | 'refused' | 'failed';

/** How an answer reads without its color: a check, the hatch, a dashed box or a cross. */
const Mark = ({ kind }: { kind: MarkKind }) =>
  kind === 'sure' ? (
    <Icon name="check" size={14} className={styles.check} />
  ) : kind === 'failed' ? (
    <Icon name="close" size={14} className={styles.cross} />
  ) : (
    <span aria-hidden className={cx(styles.swatch, kind === 'unsure' ? `hatch ${styles.dashed}` : styles.refusedMark)} />
  );

/** The arrow between chips: a round, a tier. */
const Arrow = () => (
  <svg className={styles.arrow} width="14" height="10" viewBox="0 0 14 10" aria-hidden>
    <path d="M0 5h10M7 1l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/** `◆ Question` and the kind on the right. */
const Head = ({ question, kind }: { question: string; kind: string }) => (
  <div className={styles.head}>
    <span className={cx('mono', styles.questionName)}>
      <span className={styles.diamond}>◆</span> {question}
    </span>
    <span className={styles.kind}>{kind}</span>
  </div>
);

/** A titled part of a decision card: escalation, vote, shadow, explanation, review. */
const Section = ({ label, meta, children }: { label: string; meta?: string; children: ReactNode }) => (
  <div className={styles.section}>
    <div className={styles.head}>
      <span className={styles.label}>{label}</span>
      {meta ? <span className={styles.meta}>{meta}</span> : null}
    </div>
    {children}
  </div>
);

/** The latest images that landed in one option, newest first; the UNSURE lane is hatched. */
const ThumbLane = memo(
  ({ option, samples, total }: { option: string; samples: DecisionSample[]; total: number }) => {
    const hidden = total - samples.length;
    return (
      <div className={cx(styles.lane, option === UNSURE && `hatch ${styles.laneUnsure}`)}>
        {samples.map((sample, index) => {
          const label = `${option} · p ${sample.p.toFixed(2)}`;
          return <img key={index} className={cx(styles.thumb, 'nodrag')} src={sample.thumb} alt={label} title={label} />;
        })}
        {hidden > 0 && <span className={styles.lanePill}>+{hidden}</span>}
      </div>
    );
  }
);
ThumbLane.displayName = 'ThumbLane';

/** Thumbnail lanes of the options that have decided images. */
const SampleLanes = memo(({ question }: { question: DeciderQuestion }) => {
  const rows = [...question.options, UNSURE].filter((option) => question.samples?.[option]?.length);
  return (
    <div className={styles.lanes}>
      {rows.map((option) => (
        <div key={option} className={styles.laneRow}>
          <span className={styles.laneName} title={option}>
            {option}
          </span>
          <ThumbLane option={option} samples={question.samples?.[option] ?? []} total={question.counts[option] ?? 0} />
        </div>
      ))}
    </div>
  );
});
SampleLanes.displayName = 'SampleLanes';

const MAX_OPTION_ROWS = 8;

/** Choice: one row per option with how often it was chosen (and its image lane).
 * Choices with many options show the most frequent ones. */
const ChoiceCounts = memo(({ question }: { question: DeciderQuestion }) => {
  let rows = [...question.options];
  let hidden = 0;
  if (rows.length > MAX_OPTION_ROWS) {
    rows = rows
      .filter((option) => (question.counts[option] ?? 0) > 0)
      .sort((a, b) => (question.counts[b] ?? 0) - (question.counts[a] ?? 0))
      .slice(0, MAX_OPTION_ROWS);
    hidden = question.options.length - rows.length;
  }
  if (UNSURE in question.counts) rows.push(UNSURE);
  const total = Math.max(1, Object.values(question.counts).reduce((sum, count) => sum + count, 0));
  return (
    <>
      <div className={styles.bars}>
        {rows.map((option) => {
          const count = question.counts[option] ?? 0;
          const unsure = option === UNSURE;
          const samples = question.samples?.[option] ?? [];
          return (
            <div key={option} className={styles.row}>
              <span className={cx(styles.name, unsure && styles.quiet)} title={option}>
                {option}
              </span>
              <span className={styles.track}>
                <span
                  className={cx(styles.fill, unsure ? `hatch ${styles.fillGuess}` : styles.fillSure)}
                  style={{ width: `${(count / total) * 100}%` }}
                />
              </span>
              <span className={styles.value}>{count}</span>
              {samples.length > 0 && (
                <div className={styles.wide}>
                  <ThumbLane option={option} samples={samples} total={count} />
                </div>
              )}
            </div>
          );
        })}
      </div>
      {hidden > 0 && <span className={styles.more}>+{hidden} more options</span>}
    </>
  );
});
ChoiceCounts.displayName = 'ChoiceCounts';

/** Yes/no: one bar, yes from the left, the UNSURE share hatched, no from the right. */
const YesNoCounts = memo(({ question }: { question: DeciderQuestion }) => {
  const parts: [string, string | undefined][] = [['yes', styles.shareSure]];
  if (UNSURE in question.counts) parts.push([UNSURE, 'hatch']);
  parts.push(['no', styles.shareNo]);
  const total = parts.reduce((sum, [option]) => sum + (question.counts[option] ?? 0), 0);
  return (
    <>
      <div className={styles.split}>
        {parts.map(([option, className]) => (
          <span
            key={option}
            data-testid="yesno-segment"
            data-option={option}
            title={`${option}: ${question.counts[option] ?? 0}`}
            className={className}
            style={{ width: `${total ? ((question.counts[option] ?? 0) / total) * 100 : 0}%` }}
          />
        ))}
      </div>
      <div className={styles.ends}>
        {parts.map(([option]) => (
          <span key={option}>
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
  const columns = { gridTemplateColumns: `repeat(${levels.length}, minmax(0, 1fr))` };
  return (
    <>
      <div className={cx(styles.levels, styles.levelsCompact)} style={columns}>
        {levels.map((level) => {
          const count = question.counts[level] ?? 0;
          return (
            <div
              key={level}
              data-testid="scale-level"
              data-option={level}
              data-count={String(count)}
              title={`${level}: ${count}`}
              className={styles.level}
            >
              <span className={styles.levelValue}>{count}</span>
              <span className={cx(styles.levelBar, styles.levelBarSure)} style={{ height: `${Math.max((count / max) * 32, 2)}px` }} />
            </div>
          );
        })}
      </div>
      <div className={styles.markerRow}>
        {question.meanScore !== undefined && (
          <span
            data-testid="scale-mean"
            title={`mean score ${question.meanScore.toFixed(2)}`}
            className={styles.marker}
            style={{ left: `${((question.meanScore + 0.5) / levels.length) * 100}%` }}
          />
        )}
      </div>
      <div className={styles.levelNames} style={columns}>
        {levels.map((level) => (
          <span key={level} title={level}>
            {level}
          </span>
        ))}
      </div>
      {(unsure > 0 || question.meanScore !== undefined) && (
        <div className={styles.counts}>
          {unsure > 0 && (
            <span>
              <span aria-hidden className={cx(styles.swatchSmall, 'hatch', styles.dashed)} />
              UNSURE {unsure}
            </span>
          )}
          {question.meanScore !== undefined && <span className={styles.faint}>mean score {question.meanScore.toFixed(2)}</span>}
        </div>
      )}
      {question.samples && <SampleLanes question={question} />}
    </>
  );
});
ScaleCounts.displayName = 'ScaleCounts';

/** Checklist: outcomes, a strip with every item's answers across artifacts,
 * and the items answered "no" most often. */
const ChecklistCounts = memo(({ question }: { question: DeciderQuestion }) => {
  const outcomes: [string, string | undefined, string | undefined][] = [
    ['passed', styles.shareSure, styles.sureInk],
    ['failed', styles.shareFailed, styles.errorInk],
    [UNSURE, 'hatch', undefined],
  ];
  const total = outcomes.reduce((sum, [option]) => sum + (question.counts[option] ?? 0), 0);
  const stats = question.itemStats ?? [];
  const gaps = question.options
    .map((item, index) => ({ item, no: stats[index]?.[1] ?? 0 }))
    .filter((gap) => gap.no > 0)
    .sort((a, b) => b.no - a.no)
    .slice(0, 3);
  return (
    <>
      <div className={styles.split}>
        {outcomes.map(([option, className]) => (
          <span
            key={option}
            data-testid="checklist-outcome"
            data-option={option}
            title={`${option}: ${question.counts[option] ?? 0}`}
            className={className}
            style={{ width: `${total ? ((question.counts[option] ?? 0) / total) * 100 : 0}%` }}
          />
        ))}
      </div>
      <div className={styles.ends}>
        {outcomes.map(([option, , ink]) => (
          <span key={option} className={ink}>
            {option} {question.counts[option] ?? 0}
          </span>
        ))}
      </div>
      <div className={styles.strip} title="Answers per item across all decisions: yes (blue), unsure (hatched), no (empty)">
        {question.options.map((item, index) => {
          const [yes = 0, no = 0, unsure = 0] = stats[index] ?? [];
          const n = Math.max(1, yes + no + unsure);
          const description = question.descriptions?.[item];
          return (
            <span
              key={item}
              data-testid="checklist-item-stat"
              title={`${item}: ${yes} yes · ${no} no · ${unsure} unsure${description ? ` — ${description}` : ''}`}
              className={styles.stripItem}
            >
              <span className={styles.shareSure} style={{ height: `${(yes / n) * 100}%` }} />
              <span className="hatch" style={{ height: `${(unsure / n) * 100}%` }} />
            </span>
          );
        })}
      </div>
      {gaps.length > 0 && (
        <div className={styles.chips}>
          <span className={styles.more}>most often no</span>
          {gaps.map((gap) => (
            <span
              key={gap.item}
              data-testid="checklist-gap"
              data-item={gap.item}
              title={question.descriptions?.[gap.item]}
              className={cx('mono', styles.chip)}
            >
              {gap.item} {gap.no}
            </span>
          ))}
        </div>
      )}
      {question.samples && <SampleLanes question={{ ...question, options: ['passed', 'failed'] }} />}
    </>
  );
});
ChecklistCounts.displayName = 'ChecklistCounts';

/** At most this many questions sit one below the other on a decider's card; more go into columns. */
export const QUESTIONS_PER_COLUMN = 3;

/**
 * Splits a decider's questions into columns of at most QUESTIONS_PER_COLUMN, in question order and as
 * even as possible: 4 → 2 + 2, 5 → 3 + 2, 6 → 3 + 3, 7 → 3 + 2 + 2. Up to three questions stay one column.
 */
export function questionColumns<T>(questions: T[]): T[][] {
  return splitEven(questions, Math.ceil(questions.length / QUESTIONS_PER_COLUMN));
}

/** `count` columns of the items in order, the first ones one longer where they do not divide evenly. */
function splitEven<T>(items: T[], count: number): T[][] {
  count = Math.max(1, count);
  const base = Math.floor(items.length / count);
  const extra = items.length % count;
  const columns: T[][] = [];
  let start = 0;
  for (let index = 0; index < count; index += 1) {
    const size = base + (index < extra ? 1 : 0);
    columns.push(items.slice(start, start + size));
    start += size;
  }
  return columns;
}

/** Up to this many questions a decider's card shows every option; more become one compact row each. */
export const MAX_DETAILED_QUESTIONS = 6;
/** Compact rows per column; more questions go into a second column. */
export const COMPACT_ROWS_PER_COLUMN = 12;

/**
 * How a decider's card lays out its questions: one to three as a list, four to six in columns of at most
 * three, seven or more as compact rows (in columns of at most twelve).
 */
export function deciderLayout<T>(questions: T[]): { compact: boolean; columns: T[][] } {
  if (questions.length > MAX_DETAILED_QUESTIONS) {
    return { compact: true, columns: splitEven(questions, Math.ceil(questions.length / COMPACT_ROWS_PER_COLUMN)) };
  }
  return { compact: false, columns: questionColumns(questions) };
}

/** Strength of a decided answer's segment by its rank, the most frequent first. */
const RANK_SHADE = [1, 0.78, 0.6, 0.47, 0.37, 0.3];

/**
 * One question in one row (deciders with many questions): a stacked bar of the answers by frequency,
 * the unsure share hatched at the end, then the most frequent answer and its count. The tooltip has
 * the whole distribution.
 */
function CompactQuestion({ question }: { question: DeciderQuestion }) {
  const unsure = question.counts[UNSURE] ?? 0;
  const answers: [string, number, string | undefined][] =
    question.kind === 'checklist'
      ? [
          ['passed', question.counts.passed ?? 0, styles.shareSure],
          ['failed', question.counts.failed ?? 0, styles.shareFailed],
        ]
      : question.kind === 'yesno'
        ? [
            ['yes', question.counts.yes ?? 0, styles.shareSure],
            ['no', question.counts.no ?? 0, styles.shareNo],
          ]
        : question.options.map((option): [string, number, string | undefined] => [option, question.counts[option] ?? 0, styles.shareSure]);
  const decided = answers.filter(([, count]) => count > 0).sort((a, b) => b[1] - a[1]);
  const total = decided.reduce((sum, [, count]) => sum + count, 0) + unsure;
  const top = decided[0];
  const distribution = [...decided.map(([option, count]) => `${option} ${count}`), ...(unsure ? [`${UNSURE} ${unsure}`] : [])];
  const ranked = question.kind === 'choice' || question.kind === 'scale';
  return (
    <div
      className={styles.compactRow}
      data-testid="compact-question"
      title={[question.instructions, distribution.join(' · ') || 'no decisions yet'].filter(Boolean).join('\n')}
    >
      <span className={cx('mono', styles.questionName)}>
        <span className={styles.diamond}>◆</span> {question.name}
      </span>
      <span className={cx(styles.split, styles.compactBar)}>
        {decided.map(([option, count, className], index) => (
          <span
            key={option}
            data-option={option}
            className={className}
            style={{
              width: `${(count / total) * 100}%`,
              opacity: ranked ? RANK_SHADE[Math.min(index, RANK_SHADE.length - 1)] : undefined,
            }}
          />
        ))}
        {unsure > 0 && <span data-option={UNSURE} className="hatch" style={{ width: `${(unsure / total) * 100}%` }} />}
      </span>
      <span className={cx('mono', styles.compactTop, !top && unsure > 0 && styles.quiet)}>
        {top ? `${top[0]} ${top[1]}` : unsure > 0 ? `${UNSURE} ${unsure}` : '—'}
      </span>
    </div>
  );
}

function DeciderQuestionCounts({ question, titled }: { question: DeciderQuestion; titled: boolean }) {
  return (
    <div className={styles.question} title={question.instructions}>
      {titled && <Head question={question.name} kind={KIND_LABEL[question.kind] ?? KIND_LABEL.choice} />}
      {question.kind === 'checklist' ? (
        <ChecklistCounts question={question} />
      ) : question.kind === 'yesno' ? (
        <YesNoCounts question={question} />
      ) : question.kind === 'scale' ? (
        <ScaleCounts question={question} />
      ) : (
        <ChoiceCounts question={question} />
      )}
      {question.refused ? (
        <span className={styles.counts}>
          <span>
            <span aria-hidden className={cx(styles.swatchSmall, styles.refusedMark)} />
            {question.refused} refused
          </span>
        </span>
      ) : null}
    </div>
  );
}

/**
 * Questions of a decision agent with how often each answer was given. `columns` applies the card's layout
 * (deciderLayout: columns from four questions, compact rows from seven); without it every question shows
 * all its options in one column (unfolded).
 */
export const DeciderOptions = memo(({ decider, columns = false }: { decider: DeciderInfo; columns?: boolean }) => {
  const titled = decider.questions.length > 1;
  const shadow = decider.shadow;
  const layout = columns ? deciderLayout(decider.questions) : { compact: false, columns: [decider.questions] };
  return (
    <div className={styles.decider}>
      {layout.compact ? (
        <div className={styles.questionColumns} data-testid="decider-compact">
          {layout.columns.map((column, index) => (
            <div key={index} className={cx(styles.questionColumn, styles.compactColumn)}>
              {column.map((question) => (
                <CompactQuestion key={question.name} question={question} />
              ))}
            </div>
          ))}
        </div>
      ) : layout.columns.length > 1 ? (
        <div className={styles.questionColumns} data-testid="decider-columns">
          {layout.columns.map((column, index) => (
            <div key={index} className={styles.questionColumn}>
              {column.map((question) => (
                <DeciderQuestionCounts key={question.name} question={question} titled={titled} />
              ))}
            </div>
          ))}
        </div>
      ) : (
        decider.questions.map((question) => (
          <DeciderQuestionCounts key={question.name} question={question} titled={titled} />
        ))
      )}
      <div className={styles.deciderFoot}>
        <div className={styles.foot}>
          {decider.ensemble
            ? `${decider.vote} of ${decider.ensemble.join(' + ')}`
            : [decider.model, ...(decider.escalate ?? [])].join(' › ')}
          {decider.threshold !== null ? ` · threshold ${decider.threshold.toFixed(2)}` : ''}
          {decider.tournament
            ? ` · tournament: groups of ${decider.tournament.groupSize}, keep ${decider.tournament.keep}`
            : ''}
        </div>
        {decider.itemThresholds ? <ItemThresholds thresholds={decider.itemThresholds} /> : null}
        {shadow ? (
          <div
            data-testid="decider-shadow"
            className={styles.shadowRow}
            title="Decisions where the shadow model chose the same as the decider"
          >
            <span className={cx(styles.chip, styles.chipDashed)}>
              {`shadow ${shadow.model} · agrees ${shadow.agree}/${shadow.compared}`}
            </span>
            <span className={styles.track}>
              <span
                className={cx(styles.fill, styles.fillQuiet)}
                style={{ width: `${shadow.compared ? (shadow.agree / shadow.compared) * 100 : 0}%` }}
              />
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
});
DeciderOptions.displayName = 'DeciderOptions';

/** Choice: probability per option, most probable first, with the threshold tick.
 * Large choices show their most probable options. */
const ChoiceBars = memo(({ decision }: { decision: DecisionInfo }) => {
  const sorted = Object.entries(decision.probabilities).sort((a, b) => b[1] - a[1]);
  const options = sorted.slice(0, MAX_OPTION_ROWS);
  const rest = sorted.slice(MAX_OPTION_ROWS);
  const restMax = rest.length > 0 ? (rest[0]?.[1] ?? 0) : 0;
  const unsure = decision.choice === UNSURE;
  return (
    <>
      <div className={styles.bars}>
        {options.map(([option, probability]) => {
          const chosen = option === decision.choice;
          const bestGuess = option === decision.bestGuess;
          const guess = unsure && bestGuess;
          return (
            <div
              key={option}
              data-testid="decision-option"
              data-option={option}
              data-chosen={String(chosen)}
              data-best-guess={String(bestGuess)}
              className={styles.row}
            >
              <span className={cx(styles.name, chosen ? styles.sureInk : !guess && styles.quiet)} title={option}>
                {option}
              </span>
              <span className={styles.track}>
                <span
                  className={cx(styles.fill, chosen && styles.fillSure, guess && `hatch ${styles.fillGuess}`)}
                  style={{ width: `${Math.max(probability * 100, 1)}%` }}
                />
                {decision.threshold !== null && (
                  <span
                    aria-hidden
                    title={`threshold ${decision.threshold.toFixed(2)}`}
                    className={styles.tick}
                    style={{ left: `${decision.threshold * 100}%` }}
                  />
                )}
              </span>
              <span className={cx(styles.value, (chosen || guess) && styles.strong)}>{probability.toFixed(2)}</span>
            </div>
          );
        })}
      </div>
      {rest.length > 0 && (
        <span className={styles.more}>
          {`+${rest.length} more options, each ${restMax < 0.01 ? 'below 1%' : `at most ${Math.round(restMax * 100)}%`}`}
        </span>
      )}
    </>
  );
});
ChoiceBars.displayName = 'ChoiceBars';

/** Yes/no: one bar, yes from the left and no from the right. Between 1 − t
 * and t neither answer is firm: the hatched UNSURE zone. The marker is at p. */
const YesNoBar = memo(({ decision }: { decision: DecisionInfo }) => {
  const yes = decision.probabilities.yes ?? 0;
  const threshold = decision.threshold;
  const zone = threshold !== null && threshold > 0.5;
  return (
    <div className={styles.yesno}>
      <div data-testid="decision-yesno" data-yes={String(yes)} className={styles.yesnoBar}>
        {/* The chosen side blue; an unsure answer only tints yes */}
        <span
          className={decision.choice === 'yes' ? styles.sideSure : decision.choice === UNSURE ? styles.sideLeaning : styles.side}
          style={{ width: `${yes * 100}%` }}
        />
        <span className={cx(styles.noSide, decision.choice === 'no' ? styles.sideSure : styles.side)} />
        {zone && (
          <span
            data-testid="decision-unsure-zone"
            title={`UNSURE between ${(1 - threshold).toFixed(2)} and ${threshold.toFixed(2)}`}
            className={cx('hatch', styles.zone)}
            style={{ left: pct(1 - threshold), width: pct(2 * threshold - 1) }}
          />
        )}
      </div>
      <div className={styles.markerRow}>
        <span aria-hidden className={styles.marker} style={{ left: pct(yes) }} />
      </div>
      <div className={styles.ends}>
        <span className={cx(decision.choice === 'yes' && styles.sureInk)}>{`yes ${yes.toFixed(2)}`}</span>
        {zone && <span className={styles.faint}>{`unsure zone ${(1 - threshold).toFixed(2)} – ${threshold.toFixed(2)}`}</span>}
        <span className={cx(decision.choice === 'no' && styles.sureInk)}>{`no ${(1 - yes).toFixed(2)}`}</span>
      </div>
    </div>
  );
});
YesNoBar.displayName = 'YesNoBar';

/** Height of a scale bar at probability 1. */
const SCALE_HEIGHT = 46;

/** Scale: probability per level in level order, the threshold as a dashed line
 * and the probability-weighted score as a marker below. */
const ScaleBars = memo(({ decision }: { decision: DecisionInfo }) => {
  const levels = decision.levels ?? Object.keys(decision.probabilities);
  const score = decision.score ?? null;
  const unsure = decision.choice === UNSURE;
  const columns = { gridTemplateColumns: `repeat(${levels.length}, minmax(0, 1fr))` };
  return (
    <div>
      <div className={styles.levels} style={columns}>
        {levels.map((level) => {
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
              className={styles.level}
            >
              <span className={styles.levelValue}>{probability.toFixed(2)}</span>
              <span
                className={cx(styles.levelBar, chosen && styles.levelBarSure, unsure && bestGuess && `hatch ${styles.levelBarGuess}`)}
                style={{ height: `${Math.max(probability * SCALE_HEIGHT, 2)}px` }}
              />
            </div>
          );
        })}
        {decision.threshold !== null && (
          <span
            aria-hidden
            title={`threshold ${decision.threshold.toFixed(2)}`}
            className={styles.thresholdLine}
            style={{ bottom: `${decision.threshold * SCALE_HEIGHT}px` }}
          />
        )}
      </div>
      <div className={styles.markerRow}>
        {score !== null && (
          <span
            data-testid="decision-score"
            title={`score ${score.toFixed(2)}`}
            className={styles.marker}
            style={{ left: `${((score + 0.5) / levels.length) * 100}%` }}
          />
        )}
      </div>
      <div className={styles.levelNames} style={columns}>
        {levels.map((level) => (
          <span key={level} title={level} className={cx(level === decision.choice && styles.sureInk)}>
            {level}
          </span>
        ))}
      </div>
    </div>
  );
});
ScaleBars.displayName = 'ScaleBars';

function attemptLabel(attempt: EscalationAttempt): string {
  if (attempt.results) return `${Object.keys(attempt.results).length} unsure`;
  if (attempt.refused || !attempt.choice) return 'refused';
  // A provider may report only a confidence for its choice
  const p = attempt.probabilities?.[attempt.choice] ?? attempt.confidence;
  return p == null ? attempt.choice : `${attempt.choice} ${p.toFixed(2)}`;
}

function voteLabel(vote: EscalationAttempt): string {
  if (!vote.results) return attemptLabel(vote);
  const values = Object.values(vote.results);
  const count = (result: string) => values.filter((value) => value === result).length;
  const unsure = count(UNSURE);
  return `${count('yes')} yes · ${count('no')} no${unsure ? ` · ${unsure} unsure` : ''}`;
}

type VoteState = 'agrees' | 'differs' | 'unsure';

const VOTE_STYLE: Record<VoteState, { className: string | undefined; title: string }> = {
  agrees: { className: styles.chipSure, title: 'Firm vote for the decision' },
  differs: { className: '', title: 'Firm vote that did not carry' },
  unsure: { className: `hatch ${styles.chipUnsure}`, title: 'No vote: below the threshold or refused' },
};

function checklistVoteState(vote: Record<string, string>, results: Record<string, string>): VoteState {
  const firm = Object.entries(vote).filter(([, result]) => result !== UNSURE);
  if (firm.length === 0) return 'unsure'; // no firm item answer is no vote
  // A firm item answer that differs from the decision's result did not carry
  return firm.some(([item, result]) => results[item] !== result) ? 'differs' : 'agrees';
}

function voteState(vote: EscalationAttempt, choice: string, threshold: number | null): VoteState {
  if (vote.refused || !vote.choice) return 'unsure';
  const p = vote.probabilities?.[vote.choice] ?? vote.confidence;
  if (threshold !== null && (p == null || p < threshold)) return 'unsure';
  return vote.choice === choice ? 'agrees' : 'differs';
}

/** Ensemble: every model's vote (blue agrees, hatched unsure, outlined differs) and the result. */
const EnsembleVotes = memo(
  ({
    votes,
    choice,
    threshold,
    results,
  }: {
    votes: EscalationAttempt[];
    choice: string;
    threshold: number | null;
    results?: Record<string, string>;
  }) => {
    // Checklist votes hold one result per item, compared item by item
    const states = votes.map((vote) =>
      vote.results ? checklistVoteState(vote.results, results ?? {}) : voteState(vote, choice, threshold)
    );
    const agree = states.filter((state) => state === 'agrees').length;
    return (
      <Section label="Vote" meta={plural(votes.length, 'model')}>
        <div className={styles.chips}>
          {votes.map((vote, index) => {
            const state = states[index] ?? 'unsure';
            return (
              <span
                key={index}
                data-testid="decision-vote"
                data-vote={state}
                title={VOTE_STYLE[state].title}
                className={cx(styles.chip, VOTE_STYLE[state].className)}
              >
                {`${vote.model} · ${voteLabel(vote)}`}
              </span>
            );
          })}
        </div>
        <div className={styles.result}>
          <span className={styles.quiet}>result</span>
          <span className={cx('mono', choice === UNSURE ? styles.quiet : styles.sureInk)}>
            {choice === UNSURE ? 'unsure' : `◆ ${choice}`}
          </span>
          <span className={styles.faint}>{`${agree} of ${votes.length} agree`}</span>
        </div>
      </Section>
    );
  }
);
EnsembleVotes.displayName = 'EnsembleVotes';

function shadowLabel(shadow: ShadowAnswer): string {
  if (shadow.error) return 'error';
  if (shadow.refused) return 'refused';
  if (shadow.results) return shadow.choice ?? UNSURE;
  const pick = shadow.choice === UNSURE ? shadow.best_guess : shadow.choice;
  const p = pick ? (shadow.probabilities?.[pick] ?? shadow.confidence) : null;
  const value = pick && p != null ? `${pick} ${p.toFixed(2)}` : (pick ?? '');
  return shadow.choice === UNSURE ? `UNSURE (${value})` : value;
}

/** Shadow mode: a dashed chip with what the shadow model decided, and whether it would have routed the same. */
const ShadowRow = memo(({ shadow, choice }: { shadow: ShadowAnswer; choice: string }) => {
  const agrees = !shadow.error && shadow.choice === choice;
  return (
    <Section label="Shadow" meta="not routed">
      <div className={styles.chips}>
        <span
          data-testid="decision-shadow"
          data-agrees={String(agrees)}
          title={shadow.error ?? (agrees ? 'The shadow model chose the same' : 'The shadow model would have routed differently')}
          className={cx(styles.chip, styles.chipDashed)}
        >
          {`shadow ${shadow.model} · ${shadowLabel(shadow)}`}
        </span>
        {shadow.error ? (
          <span className={cx(styles.flag, styles.errorInk)}>
            <Mark kind="failed" />
            failed
          </span>
        ) : agrees ? (
          <span className={cx(styles.flag, styles.sureInk)}>
            <Mark kind="sure" />
            agrees
          </span>
        ) : (
          <span className={cx(styles.flag, styles.quiet)}>would route differently</span>
        )}
      </div>
    </Section>
  );
});
ShadowRow.displayName = 'ShadowRow';

export interface ExplanationInfo {
  explanation: string;
  missing?: string | null;
  model: string;
  questions: string[];
}

/** "Would settle it: …" */
const Settle = ({ missing }: { missing: string }) => (
  <div className={styles.settle}>
    <span>Would settle it:</span> <span>{missing}</span>
  </div>
);

/** An Explanation artifact: the LLM's text instead of JSON. */
export const ExplanationCard = memo(({ explanation }: { explanation: ExplanationInfo }) => (
  <div data-testid="explanation-card" className={styles.decision}>
    <div className={styles.head}>
      <span>
        Explains <span className="mono">{explanation.questions.join(', ') || 'a decision'}</span>
      </span>
      <span className={styles.kind}>Explanation</span>
    </div>
    <p className={styles.explainText}>{explanation.explanation}</p>
    {explanation.missing ? <Settle missing={explanation.missing} /> : null}
    <span className={styles.foot}>{explanation.model}</span>
  </div>
));
ExplanationCard.displayName = 'ExplanationCard';

/** The latest explanation of a decision, shown on the decision's card. */
const ExplanationNote = memo(({ explanation }: { explanation: NonNullable<DecisionInfo['explanation']> }) => {
  const [open, setOpen] = useState(false);
  return (
    <Section label="Explanation" meta={explanation.model}>
      <div data-testid="decision-explanation" className={styles.explanation}>
        <p className={cx(styles.explainText, !open && styles.clamp)}>
          <span className={styles.faint}>{`${explanation.by ?? explanation.model}:`}</span> {explanation.explanation}
        </p>
        {open && explanation.missing ? <Settle missing={explanation.missing} /> : null}
        <button
          type="button"
          className={cx('nodrag nopan', styles.toggle)}
          aria-expanded={open}
          aria-label={open ? 'Show less of the explanation' : 'Show the whole explanation'}
          onClick={(event) => {
            event.stopPropagation();
            setOpen(!open);
          }}
        >
          {open ? 'less' : 'more'}
        </button>
      </div>
    </Section>
  );
});
ExplanationNote.displayName = 'ExplanationNote';

/** Escalation: chips per tier, hatched for the tiers that were unsure, blue for the tier that answered. */
const EscalationTrail = memo(({ decision, attempts, tier }: { decision: DecisionInfo; attempts: EscalationAttempt[]; tier: number }) => {
  const answered = !decision.refused && decision.choice !== UNSURE;
  const p = decision.probabilities[decision.choice] ?? decision.confidence;
  const answer = decision.refused
    ? 'refused'
    : !answered
      ? 'unsure'
      : decision.kind === 'checklist' || p == null
        ? decision.choice
        : `${decision.choice} ${p.toFixed(2)}`;
  return (
    <Section label="Escalation" meta={`tier ${tier}`}>
      <div className={styles.chips}>
        {attempts.map((attempt, index) => (
          <span key={index} className={styles.step}>
            {index > 0 && <Arrow />}
            <span
              data-testid="escalation-attempt"
              title={
                attempt.results
                  ? `Tier ${index}: not sure about ${Object.keys(attempt.results).join(', ')}; asked one tier up`
                  : `Tier ${index}: ${attempt.refused ? 'refused' : 'below the threshold'}; asked one tier up`
              }
              className={cx(styles.chip, 'hatch', styles.chipUnsure)}
            >
              {`${attempt.model} · ${attemptLabel(attempt)}`}
            </span>
          </span>
        ))}
        <span className={styles.step}>
          <Arrow />
          <span
            data-testid="escalation-final"
            className={cx(styles.chip, answered ? styles.chipSure : `hatch ${styles.chipUnsure}`)}
          >
            {`${decision.model} · ${answer}`}
          </span>
        </span>
      </div>
      <p className={styles.note}>
        {`${answered ? 'Answered' : 'Not sure'} at tier ${tier} after ${plural(attempts.length, 'attempt')}.`}
      </p>
    </Section>
  );
});
EscalationTrail.displayName = 'EscalationTrail';

/** Tournament: the rounds that narrowed the options down to the final question. */
const TournamentRounds = memo(
  ({ decision, rounds, onOpen }: { decision: DecisionInfo; rounds: TournamentRound[]; onOpen?: () => void }) => {
    const unsure = decision.choice === UNSURE;
    const winner = unsure ? decision.bestGuess : decision.choice;
    const p = winner ? decision.probabilities[winner] : undefined;
    return (
      <>
        <div className={styles.chips}>
          <span className={styles.chip}>{`${rounds[0]?.candidates ?? 0} options`}</span>
          {rounds.map((round, index) => (
            <span key={index} className={styles.step}>
              <Arrow />
              <span
                data-testid="tournament-round"
                title={`Round ${index + 1}: ${round.candidates} options in ${round.groups} groups; the ${round.survivors.length} survivors are the most probable options of each group${
                  round.refused_groups ? `; ${round.refused_groups} group(s) refused, no option fit` : ''
                }`}
                className={styles.chip}
              >
                {`${round.groups} groups → ${round.survivors.length}`}
              </span>
            </span>
          ))}
          {winner && (
            <span className={styles.step}>
              <Arrow />
              <span
                title={unsure ? 'The best guess of the final question' : 'The answer of the final question'}
                className={cx(styles.chip, unsure ? `hatch ${styles.chipUnsure}` : styles.chipSure)}
              >
                {p === undefined ? winner : `${winner} · ${p.toFixed(2)}`}
              </span>
            </span>
          )}
        </div>
        {onOpen && (
          <button
            type="button"
            className={cx('btn sm nodrag nopan', styles.start)}
            aria-label="Open tournament bracket"
            title="Show the whole bracket"
            onClick={(event) => {
              event.stopPropagation();
              onOpen();
            }}
          >
            Open bracket
          </button>
        )}
      </>
    );
  }
);
TournamentRounds.displayName = 'TournamentRounds';

/** Checklist: one cell per item, in item order, and a legend with counts. */
const ChecklistGrid = memo(({ decision }: { decision: DecisionInfo }) => {
  const results = decision.results ?? {};
  const items = decision.items ?? Object.keys(results);
  const refused = new Set(decision.refusedItems ?? []);
  const count = (result: string) => items.filter((item) => !refused.has(item) && (results[item] ?? UNSURE) === result).length;
  return (
    <>
      <div role="group" aria-label={`${decision.question} items`} className={styles.cells}>
        {items.map((item) => {
          const result = results[item] ?? UNSURE;
          const p = decision.probabilities[item];
          const section = decision.sections?.answeredBy[item];
          const own = decision.itemThresholds?.[item];
          const where = `${own !== undefined ? ` · threshold ${own.toFixed(2)}` : ''}${
            section !== undefined ? ` · section ${section + 1}` : ''
          }`;
          const title = refused.has(item)
            ? `${item} · refused${where}`
            : `${item} · ${result}${p !== undefined ? ` · p ${p.toFixed(2)}` : ''}${where}`;
          return (
            <span
              key={item}
              data-testid="checklist-cell"
              data-result={result}
              role="img"
              aria-label={title}
              title={title}
              className={cx(
                styles.cell,
                refused.has(item)
                  ? styles.refusedMark
                  : result === 'yes'
                    ? styles.cellYes
                    : result === 'no'
                      ? styles.cellNo
                      : 'hatch'
              )}
            />
          );
        })}
      </div>
      <div className={styles.legend}>
        <span>
          <span aria-hidden className={cx(styles.swatchSmall, styles.cellYes)} />
          yes {count('yes')}
        </span>
        <span>
          <span aria-hidden className={cx(styles.swatchSmall, styles.cellNo, styles.legendNo)} />
          no {count('no')}
        </span>
        <span>
          <span aria-hidden className={cx(styles.swatchSmall, 'hatch')} />
          unsure {count(UNSURE)}
        </span>
        {refused.size > 0 && (
          <span>
            <span aria-hidden className={cx(styles.swatchSmall, styles.refusedMark)} />
            refused {refused.size}
          </span>
        )}
      </div>
    </>
  );
});
ChecklistGrid.displayName = 'ChecklistGrid';

/** The answer under the header: a check and the option, the hatch and UNSURE
 * with the best guess, a dashed box for a refusal, a cross for a failed checklist. */
function Answer({ decision }: { decision: DecisionInfo }) {
  const kind = decision.kind ?? 'choice';
  const unsure = decision.choice === UNSURE;
  let mark: MarkKind = 'sure';
  let ink: string | undefined = styles.sureInk;
  const details: string[] = [];
  if (decision.refused) {
    mark = 'refused';
    ink = undefined;
  } else if (unsure) {
    mark = 'unsure';
    ink = undefined;
  }
  if (kind === 'checklist') {
    const results = decision.results ?? {};
    const items = decision.items ?? Object.keys(results);
    const no = items.filter((item) => results[item] === 'no');
    if (decision.choice === 'failed') {
      mark = 'failed';
      ink = styles.errorInk;
      if (no.length > 0) details.push(`${plural(no.length, 'required item')} ${no.length === 1 ? 'is' : 'are'} no: ${no.join(', ')}`);
    } else if (unsure) {
      const refused = new Set(decision.refusedItems ?? []);
      const open = items.filter((item) => (results[item] ?? UNSURE) === UNSURE && !refused.has(item)).length;
      details.push([open > 0 && `${plural(open, 'item')} not sure`, refused.size > 0 && `${refused.size} refused`].filter(Boolean).join(' · '));
    }
  } else if (!decision.refused && unsure && decision.bestGuess) {
    const p = decision.probabilities[decision.bestGuess];
    details.push(
      kind === 'yesno'
        ? `leaning ${decision.bestGuess}`
        : `best guess ${decision.bestGuess}${p !== undefined ? ` ${p.toFixed(2)}` : ''}`
    );
  }
  if (kind === 'scale' && !decision.refused && decision.score != null) details.push(`score ${decision.score.toFixed(2)}`);
  const detail = details.filter(Boolean).join(' · ');
  return (
    <div data-testid="decision-answer" className={styles.answer}>
      <Mark kind={mark} />
      <span className={cx(styles.answerText, ink)}>{decision.refused ? 'refused' : decision.choice}</span>
      {/* A space keeps answer and detail apart in the text content */}
      {detail && ' '}
      {detail && (
        <span className={styles.answerDetail} title={detail}>
          {detail}
        </span>
      )}
    </div>
  );
}

/** Long documents: how many sections were decided, and which one answered. */
function SectionsNote({ decision, sections }: { decision: DecisionInfo; sections: NonNullable<DecisionInfo['sections']> }) {
  const from = sections.answeredBy[decision.question];
  return (
    <span>
      {` · ${sections.spans.length} sections of ${sections.field}`}
      {from !== undefined ? ` · from section ${from + 1}` : ''}
    </span>
  );
}

const MAX_REVIEW_OPTIONS = 6;

/** Review: a person confirms or overrides an unsure decision; the best guess is preselected. */
type Reviewable = Pick<DecisionInfo, 'probabilities' | 'options' | 'bestGuess'>;

export const ReviewControl = memo(({ decision, artifactId }: { decision: Reviewable; artifactId: string }) => {
  const [reviewed, setReviewed] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (reviewed) {
    return <ReviewNote choice={reviewed} by={null} />;
  }
  // The most probable options first, the best guess leading (a refusal has no
  // probabilities),
  const ranked = Object.entries(decision.probabilities)
    .sort((a, b) => b[1] - a[1])
    .map(([option]) => option);
  // then the options a sparse answer left out
  const rest = (decision.options ?? []).filter((option) => !ranked.includes(option));
  const options = [...ranked, ...rest].slice(0, MAX_REVIEW_OPTIONS);
  const review = (option: string) => {
    setBusy(true);
    setError(null);
    reviewDecision(artifactId, option)
      .then((response) => {
        setReviewed(response.choice);
        // The review is a new decision; no event announces it
        useGraphStore.getState().scheduleRefresh();
      })
      .catch((caught: Error) => setError(caught.message))
      .finally(() => setBusy(false));
  };
  return (
    <div className={styles.reviewRow}>
      <span className={cx(styles.note, styles.faint)}>Review as</span>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          className={cx('btn sm nodrag nopan', option === decision.bestGuess && styles.pick)}
          aria-label={`Review as ${option}`}
          disabled={busy}
          onClick={(event) => {
            event.stopPropagation();
            review(option);
          }}
        >
          {option}
        </button>
      ))}
      {error ? (
        <span className={cx(styles.flag, styles.errorInk)}>
          <Mark kind="failed" />
          {error}
        </span>
      ) : null}
    </div>
  );
});
ReviewControl.displayName = 'ReviewControl';

/** "after review: ◆ option by reviewer" */
function ReviewNote({ choice, by }: { choice: string; by: string | null }) {
  return (
    <div data-testid="decision-review" className={styles.reviewNote}>
      <Icon name="person" size={14} className={styles.sureInk} />
      after review: <span className={cx('mono', styles.sureInk)}>{`◆ ${choice}`}</span>
      {by ? (
        <>
          {' by '}
          <span className="mono">{by}</span>
        </>
      ) : null}
    </div>
  );
}

/** Calibrated checklist items: a count that opens the thresholds (keyboard too). */
function ItemThresholds({ thresholds }: { thresholds: Record<string, number> }) {
  const count = Object.keys(thresholds).length;
  return (
    <details className={cx('nodrag nopan', styles.foot)}>
      <summary>{`${count} item threshold${count === 1 ? '' : 's'}`}</summary>
      <div>
        {Object.entries(thresholds)
          .map(([item, threshold]) => `${item} ${threshold.toFixed(2)}`)
          .join(' · ')}
      </div>
    </details>
  );
}

/** One decision: header, answer, its drawing by question kind, model and
 * threshold, then escalation, votes, shadow, explanation and review. */
export const DecisionBars = memo(
  ({ decision, artifactId, header = true }: { decision: DecisionInfo; artifactId?: string; header?: boolean }) => {
  const [bracketOpen, setBracketOpen] = useState(false);
  const kind = decision.kind ?? 'choice';
  const rounds = decision.rounds ?? [];
  const hasBracket = rounds.some((round) => round.group_results && round.group_results.length > 0);
  const unsure = decision.choice === UNSURE;
  const showReview = !decision.review && unsure && kind !== 'checklist' && !decision.reviewOf && artifactId;

  const body = (
    <div className={styles.decision}>
      {/* A card that names the question in its own head leaves this one out */}
      {header && <Head question={decision.question} kind={KIND_LABEL[kind] ?? KIND_LABEL.choice} />}
      <Answer decision={decision} />
      {kind === 'checklist' ? (
        <ChecklistGrid decision={decision} />
      ) : decision.refused ? (
        <p className={styles.note}>The model declined to answer; the decision routes to UNSURE.</p>
      ) : kind === 'yesno' ? (
        <YesNoBar decision={decision} />
      ) : kind === 'scale' ? (
        <ScaleBars decision={decision} />
      ) : (
        <>
          {rounds.length > 0 && (
            <TournamentRounds decision={decision} rounds={rounds} onOpen={hasBracket ? () => setBracketOpen(true) : undefined} />
          )}
          {bracketOpen && (
            <TournamentBracket
              question={decision.question}
              rounds={rounds}
              final={decision.probabilities}
              champion={decision.choice === UNSURE ? decision.bestGuess : decision.choice}
              onClose={() => setBracketOpen(false)}
            />
          )}
          <ChoiceBars decision={decision} />
        </>
      )}
      <div className={styles.foot}>
        {decision.model}
        {decision.latencyMs !== null ? ` · ${Math.round(decision.latencyMs)} ms` : ''}
        {decision.threshold !== null ? ` · threshold ${decision.threshold.toFixed(2)}` : ''}
        {decision.candidates ? (
          <span title={decision.candidates.join(', ')}>{` · among ${decision.candidates.length} candidates`}</span>
        ) : null}
        {decision.sections ? <SectionsNote decision={decision} sections={decision.sections} /> : null}
        {decision.reviewOf ? <span title={decision.reviewOf}>{` · review of ${decision.reviewOf.slice(0, 8)}`}</span> : null}
      </div>
      {decision.attempts && decision.attempts.length > 0 && (
        <EscalationTrail decision={decision} attempts={decision.attempts} tier={decision.tier ?? decision.attempts.length} />
      )}
      {decision.votes && decision.votes.length > 0 && (
        <EnsembleVotes votes={decision.votes} choice={decision.choice} threshold={decision.threshold} results={decision.results} />
      )}
      {decision.shadow && <ShadowRow shadow={decision.shadow} choice={decision.choice} />}
      {decision.explanation && <ExplanationNote explanation={decision.explanation} />}
      {decision.review ? (
        <Section label="Review">
          <ReviewNote choice={decision.review.choice} by={decision.review.by} />
        </Section>
      ) : showReview ? (
        <Section label="Review">
          <ReviewControl decision={decision} artifactId={artifactId} />
        </Section>
      ) : null}
    </div>
  );

  if (!decision.subjectThumb) return body;
  // The decided image next to its answer: solid blue when decided, dashed when not
  return (
    <div className={styles.withSubject}>
      <img
        src={decision.subjectThumb}
        alt="decided image"
        className={cx(styles.subject, (unsure || decision.refused) && styles.subjectUnsure)}
      />
      {body}
    </div>
  );
});
DecisionBars.displayName = 'DecisionBars';

export interface CoverageInfo extends Pick<DecisionInfo, 'question' | 'choice' | 'results' | 'items' | 'probabilities' | 'refusedItems'> {
  kind: 'checklist';
  group: string;
  combine: string;
  documents: number;
}

export interface AggregatorInfo {
  question: string;
  by: string;
  combine: string;
  groups: Record<string, number>; // passed, failed, UNSURE: groups by their latest outcome
}

/** An aggregating agent: what it combines, by what, and its groups' outcomes. */
export const CoverageSummary = memo(({ aggregator }: { aggregator: AggregatorInfo }) => (
  <div data-testid="coverage-summary" className={styles.coverageSummary}>
    <div>{`◇ ${aggregator.question} by ${aggregator.by} (${aggregator.combine})`}</div>
    <div className="num">
      <span className={styles.sureInk}>{`${aggregator.groups.passed ?? 0} passed`}</span>
      {' · '}
      <span className={styles.errorInk}>{`${aggregator.groups.failed ?? 0} failed`}</span>
      {' · '}
      <span className={styles.quiet}>{`${aggregator.groups[UNSURE] ?? 0} unsure`}</span>
    </div>
  </div>
));
CoverageSummary.displayName = 'CoverageSummary';

/** A coverage: one group's combined checklist, drawn like a checklist decision. */
export const CoverageCard = memo(({ coverage }: { coverage: CoverageInfo }) => {
  const decision = { ...coverage, bestGuess: null } as unknown as DecisionInfo;
  return (
    <div data-testid="coverage-card" className={styles.decision}>
      <div className={styles.head}>
        <span>
          <span className="mono">{`◇ ${coverage.question}`}</span> coverage of <span className="mono">{coverage.group}</span>
        </span>
        <span className={styles.kind}>Coverage</span>
      </div>
      <Answer decision={decision} />
      <ChecklistGrid decision={decision} />
      <span className={styles.foot}>
        {`${coverage.combine} of ${coverage.documents} document${coverage.documents === 1 ? '' : 's'}`}
      </span>
    </div>
  );
});
CoverageCard.displayName = 'CoverageCard';
