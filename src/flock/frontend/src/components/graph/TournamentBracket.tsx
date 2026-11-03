import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { TournamentRound } from './DecisionDisplay';
import styles from './TournamentBracket.module.css';

/**
 * Maximized view of a tournament decision: one column per round plus the
 * final, group boxes with their top candidates, lines from every survivor to
 * its place in the next round, and the champion's path in blue.
 */

interface BracketGroup {
  key: string;
  label: string;
  size: number;
  refused: boolean;
  top: [string, number][];
  survivors: Set<string>;
}

interface BracketColumn {
  title: string;
  subtitle: string;
  groups: BracketGroup[];
}

interface Line {
  key: string;
  option: string;
  d: string;
}

export interface TournamentBracketProps {
  question: string;
  rounds: TournamentRound[];
  final: Record<string, number>;
  champion: string | null;
  onClose: () => void;
}

function chunk<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < items.length; i += Math.max(1, size)) chunks.push(items.slice(i, i + Math.max(1, size)));
  return chunks;
}

function buildColumns(rounds: TournamentRound[], final: Record<string, number>): BracketColumn[] {
  const columns: BracketColumn[] = rounds.map((round, index) => {
    const survivors = new Set(round.survivors);
    const results = round.group_results ?? [];
    return {
      title: `Round ${index + 1}`,
      subtitle: `${round.candidates} options · ${round.groups} groups → ${round.survivors.length}`,
      groups: results.map((result, groupIndex) => ({
        key: `${index}:group:${groupIndex}`,
        label: `Group ${groupIndex + 1}`,
        size: result.size,
        refused: result.refused,
        top: result.top,
        survivors,
      })),
    };
  });
  const finalists = Object.entries(final).sort((a, b) => b[1] - a[1]);
  columns.push({
    title: 'Final',
    subtitle: `${finalists.length} finalists`,
    groups: [
      {
        key: `${rounds.length}:group:0`,
        label: 'Final question',
        size: finalists.length,
        refused: false,
        top: finalists,
        survivors: new Set<string>(),
      },
    ],
  });
  return columns;
}

/** Index of the group in the next column that ``option`` moved into. */
function nextGroupIndex(rounds: TournamentRound[], column: number, option: string): number {
  const next = rounds[column + 1];
  if (!next) return 0; // the final column has a single group
  const position = rounds[column]?.survivors.indexOf(option) ?? -1;
  const size = next.group_size ?? next.candidates;
  return position < 0 ? 0 : chunk(rounds[column]?.survivors ?? [], size).findIndex((g) => g.includes(option));
}

export const TournamentBracket = ({ question, rounds, final, champion, onClose }: TournamentBracketProps) => {
  const columns = buildColumns(rounds, final);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const anchors = useRef(new Map<string, HTMLElement>());
  const [lines, setLines] = useState<Line[]>([]);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [hovered, setHovered] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  const anchor = useCallback(
    (key: string) => (element: HTMLElement | null) => {
      if (element) anchors.current.set(key, element);
      else anchors.current.delete(key);
    },
    []
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onClose();
      } else if (event.key === 'Tab') {
        // Modal: the close button is the only control, keep focus on it
        event.preventDefault();
        closeRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown, { capture: true });
    return () => window.removeEventListener('keydown', onKeyDown, { capture: true });
  }, [onClose]);

  // Take focus from the button that opened the bracket and give it back on close
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    return () => opener?.focus();
  }, []);

  // Lines from every survivor to its chip (or group) in the next column
  const measure = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const origin = container.getBoundingClientRect();
    const point = (element: HTMLElement, side: 'left' | 'right') => {
      const rect = element.getBoundingClientRect();
      return {
        x: (side === 'right' ? rect.right : rect.left) - origin.left + container.scrollLeft,
        y: rect.top + rect.height / 2 - origin.top + container.scrollTop,
      };
    };
    const next: Line[] = [];
    rounds.forEach((round, column) => {
      round.survivors.forEach((option) => {
        const from = anchors.current.get(`${column}:${option}`);
        const target =
          anchors.current.get(`${column + 1}:${option}`) ??
          anchors.current.get(`${column + 1}:group:${nextGroupIndex(rounds, column, option)}`);
        if (!from || !target) return;
        const a = point(from, 'right');
        const b = point(target, 'left');
        const bend = Math.max(24, (b.x - a.x) / 2);
        next.push({
          key: `${column}:${option}`,
          option,
          d: `M ${a.x} ${a.y} C ${a.x + bend} ${a.y}, ${b.x - bend} ${b.y}, ${b.x} ${b.y}`,
        });
      });
    });
    setLines(next);
    setSize({ width: container.scrollWidth, height: container.scrollHeight });
  }, [rounds]);

  useLayoutEffect(() => {
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [measure]);

  // The champion's path is blue; a hovered option is traced in the text color
  const lineColor = (option: string) =>
    option === hovered ? 'var(--text)' : option === champion ? 'var(--sure)' : 'var(--line-2)';

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Tournament bracket: ${question}`}
      onClick={onClose}
      className={styles.scrim}
    >
      <div onClick={(event) => event.stopPropagation()} className={styles.panel}>
        <div className={styles.header}>
          <span className={styles.label}>Tournament</span>
          <span className={styles.title}>
            <span className={styles.diamond}>◆</span> {question}
          </span>
          <span className={styles.subtitle}>
            {champion ? `winner: ${champion}` : 'no winner'} · hover an option to trace it
          </span>
          <button ref={closeRef} type="button" aria-label="Close bracket" onClick={onClose} className={`btn sm ${styles.close}`}>
            Close
          </button>
        </div>
        <div ref={containerRef} className={styles.stage}>
          <svg aria-hidden width={size.width} height={size.height} className={styles.lines}>
            {lines.map((line) => (
              <path
                key={line.key}
                data-option={line.option}
                d={line.d}
                fill="none"
                stroke={lineColor(line.option)}
                strokeWidth={line.option === champion || line.option === hovered ? 2.2 : 1}
              />
            ))}
          </svg>
          <div className={styles.columns}>
            {columns.map((column, columnIndex) => (
              <div key={column.title} data-testid="bracket-column" data-title={column.title} className={styles.column}>
                <div className={styles.columnHead}>
                  <div className={styles.columnTitle}>{column.title}</div>
                  <div className={styles.columnSub}>{column.subtitle}</div>
                </div>
                {column.groups.map((group) => (
                  <div
                    key={group.key}
                    ref={anchor(group.key)}
                    data-testid="bracket-group"
                    className={group.refused ? `${styles.group} ${styles.groupRefused}` : styles.group}
                  >
                    <div className={styles.groupLabel}>
                      {group.label} · {group.size} options
                    </div>
                    {group.refused && (
                      <div className={styles.refused}>
                        <span aria-hidden className={styles.refusedMark} />
                        refused: no option fits
                      </div>
                    )}
                    {group.top.map(([option, p]) => {
                      const isFinal = columnIndex === columns.length - 1;
                      const survivor = isFinal ? option === champion : group.survivors.has(option);
                      const winner = option === champion;
                      return (
                        <div
                          key={option}
                          ref={anchor(`${columnIndex}:${option}`)}
                          data-testid="bracket-option"
                          data-option={option}
                          data-column={String(columnIndex)}
                          data-survivor={String(survivor)}
                          data-winner={String(winner)}
                          data-hovered={option === hovered || undefined}
                          onMouseEnter={() => setHovered(option)}
                          onMouseLeave={() => setHovered(null)}
                          title={`${option} · p ${p.toFixed(3)}`}
                          className={styles.option}
                        >
                          <span className={styles.name}>
                            {winner ? '◆ ' : ''}
                            {option}
                          </span>
                          <span className={styles.track}>
                            <span className={styles.fill} style={{ width: `${Math.max(p * 100, 1)}%` }} />
                          </span>
                          <span className={styles.value}>{p.toFixed(2)}</span>
                        </div>
                      );
                    })}
                    {group.size > group.top.length && !group.refused && (
                      <div className={styles.groupMore}>+{group.size - group.top.length} more</div>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};
