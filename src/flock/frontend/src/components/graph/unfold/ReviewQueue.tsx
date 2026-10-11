/**
 * A decider's unsure decisions that wait for a person, with their best
 * guesses and review buttons (docs/internal/design-system/README.md,
 * Decision kit; mockups/Main.dc.html, the Overview tab of triage).
 */

import React from 'react';
import { type DeciderInfo, ReviewControl } from '../DecisionDisplay';
import { shortId } from './format';
import styles from './Unfolded.module.css';

/** `best guess shipping 0.52 · billing 0.38` */
const guesses = (probabilities: Record<string, number>): string => {
  const [best, next] = Object.entries(probabilities).sort((a, b) => b[1] - a[1]);
  if (!best) return 'refused';
  return `best guess ${best[0]} ${best[1].toFixed(2)}${next ? ` · ${next[0]} ${next[1].toFixed(2)}` : ''}`;
};

const ReviewQueue: React.FC<{ decider: DeciderInfo }> = ({ decider }) => {
  const items = decider.needsReview ?? [];
  const total = decider.needsReviewCount ?? items.length;
  if (total === 0) return null;
  const questions = decider.questions.map((question) => question.name);
  const route = questions.length === 1 ? `${questions[0]}.UNSURE` : 'their UNSURE handles';
  // Several questions about one artifact would read alike: each row names its question
  const several = questions.length > 1;

  return (
    <section className={styles.section} aria-label="Needs review">
      <span className={styles.label}>Needs review · {total}</span>
      <span className={styles.faint}>
        {decider.threshold !== null
          ? `Answers below the ${decider.threshold.toFixed(2)} threshold route to ${route} and wait here for a person.`
          : `Unsure answers route to ${route} and wait here for a person.`}
      </span>
      <ul className={styles.queue}>
        {items.map((item) => (
          <li key={item.id} className={styles.queueItem}>
            <div className={styles.queueHead}>
              <span className={styles.queueTitle}>
                {several && <span className="mono">◆ {item.question} · </span>}
                {item.subjectTitle ?? item.question}
              </span>
              <span className={`mono ${styles.faint}`} title={item.correlationId ?? ''}>
                {shortId(item.correlationId, 4)}
              </span>
            </div>
            <span className={`mono ${styles.faint}`}>{guesses(item.probabilities)}</span>
            <ReviewControl decision={{ ...item, options: item.options ?? undefined }} artifactId={item.id} />
          </li>
        ))}
      </ul>
      {total > items.length && <span className={styles.faint}>and {total - items.length} more</span>}
    </section>
  );
};

export default ReviewQueue;
