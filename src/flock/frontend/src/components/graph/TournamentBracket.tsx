import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { DECISION_COLOR, DECISION_TEXT, type TournamentRound } from './DecisionDisplay';

/**
 * Maximized view of a tournament decision: one column per round plus the
 * final, group boxes with their top candidates, lines from every survivor to
 * its place in the next round, and the champion's path highlighted.
 */

const AMBER = '#f59e0b';
const PANEL_BG = '#14141c';
const BOX_BG = '#1d1d29';
const LINE = 'rgba(148, 163, 184, 0.35)';

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

  const lineColor = (option: string) =>
    option === hovered ? AMBER : option === champion ? DECISION_COLOR : LINE;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Tournament bracket: ${question}`}
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2000,
        background: 'rgba(6, 6, 10, 0.78)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px',
      }}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          background: PANEL_BG,
          border: `1px solid rgba(139, 92, 246, 0.35)`,
          borderRadius: '14px',
          boxShadow: '0 24px 64px rgba(0, 0, 0, 0.6)',
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          color: '#e7e5e4',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '14px 20px', borderBottom: '1px solid rgba(148,163,184,0.15)' }}>
          <span style={{ fontSize: '16px', fontWeight: 700, color: DECISION_TEXT }}>🏆 {question}</span>
          <span style={{ fontSize: '12px', color: '#a8a29e', fontFamily: 'monospace' }}>
            {champion ? `winner: ${champion}` : 'no winner'} · hover an option to trace it
          </span>
          <button
            ref={closeRef}
            type="button"
            aria-label="Close bracket"
            onClick={onClose}
            style={{
              marginLeft: 'auto',
              background: 'transparent',
              border: '1px solid rgba(148,163,184,0.3)',
              color: '#e7e5e4',
              borderRadius: '8px',
              padding: '4px 10px',
              cursor: 'pointer',
            }}
          >
            ✕ Close
          </button>
        </div>
        <div ref={containerRef} style={{ position: 'relative', flex: 1, overflow: 'auto', padding: '20px' }}>
          <svg
            aria-hidden
            width={size.width}
            height={size.height}
            style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
          >
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
          <div style={{ position: 'relative', display: 'flex', gap: '72px', alignItems: 'flex-start' }}>
            {columns.map((column, columnIndex) => (
              <div
                key={column.title}
                data-testid="bracket-column"
                data-title={column.title}
                style={{ display: 'flex', flexDirection: 'column', gap: '10px', width: '230px', flexShrink: 0 }}
              >
                <div style={{ position: 'sticky', top: 0 }}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: DECISION_TEXT }}>{column.title}</div>
                  <div style={{ fontSize: '11px', color: '#a8a29e', fontFamily: 'monospace' }}>{column.subtitle}</div>
                </div>
                {column.groups.map((group) => (
                  <div
                    key={group.key}
                    ref={anchor(group.key)}
                    data-testid="bracket-group"
                    style={{
                      background: BOX_BG,
                      border: `1px solid ${group.refused ? 'rgba(245, 158, 11, 0.5)' : 'rgba(148,163,184,0.18)'}`,
                      borderRadius: '10px',
                      padding: '8px 10px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ fontSize: '10px', color: '#78716c', fontFamily: 'monospace' }}>
                      {group.label} · {group.size} options
                    </div>
                    {group.refused && (
                      <div style={{ fontSize: '11px', color: AMBER }}>refused: no option fits</div>
                    )}
                    {group.top.map(([option, p]) => {
                      const isFinal = columnIndex === columns.length - 1;
                      const survivor = isFinal ? option === champion : group.survivors.has(option);
                      const winner = option === champion;
                      const highlight = option === hovered ? AMBER : winner ? DECISION_COLOR : null;
                      return (
                        <div
                          key={option}
                          ref={anchor(`${columnIndex}:${option}`)}
                          data-testid="bracket-option"
                          data-option={option}
                          data-column={String(columnIndex)}
                          data-survivor={String(survivor)}
                          data-winner={String(winner)}
                          onMouseEnter={() => setHovered(option)}
                          onMouseLeave={() => setHovered(null)}
                          title={`${option} · p ${p.toFixed(3)}`}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '2px 6px',
                            borderRadius: '6px',
                            border: `1px solid ${highlight ?? 'transparent'}`,
                            boxShadow: highlight ? `0 0 10px ${highlight}55` : 'none',
                            opacity: survivor || option === hovered ? 1 : 0.45,
                            cursor: 'default',
                          }}
                        >
                          <span
                            style={{
                              width: '86px',
                              fontSize: '11px',
                              fontFamily: 'monospace',
                              fontWeight: survivor ? 700 : 500,
                              color: winner ? DECISION_TEXT : '#e7e5e4',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {winner ? '★ ' : ''}
                            {option}
                          </span>
                          <span style={{ flex: 1, height: '6px', borderRadius: '3px', background: 'rgba(148,163,184,0.15)' }}>
                            <span
                              style={{
                                display: 'block',
                                height: '100%',
                                width: `${Math.max(p * 100, 1)}%`,
                                borderRadius: '3px',
                                background: survivor ? DECISION_COLOR : '#78716c',
                              }}
                            />
                          </span>
                          <span style={{ width: '34px', textAlign: 'right', fontSize: '10px', color: '#a8a29e' }}>
                            {Math.round(p * 100)}%
                          </span>
                        </div>
                      );
                    })}
                    {group.size > group.top.length && !group.refused && (
                      <div style={{ fontSize: '10px', color: '#78716c', fontFamily: 'monospace' }}>
                        +{group.size - group.top.length} more
                      </div>
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
