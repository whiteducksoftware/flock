import React, { useEffect, useState } from 'react';
import { duration, shortId } from './format';
import { RunTrace, runTraces, Span, TRACED_RUNS } from './traces';
import styles from './Unfolded.module.css';

const NS_PER_MS = 1_000_000;

/**
 * The spans of the agent's latest runs: pick a run, see where its time went.
 * The trace viewer has all traces (the timeline dock replaces it, #564).
 */
const TracesTab: React.FC<{ agent: string; onOpenTrace: (correlationId: string) => void }> = ({ agent, onOpenTrace }) => {
  const [traces, setTraces] = useState<RunTrace[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    // The agent's latest runs only; the trace database can be large
    fetch(`/api/traces/agents/${encodeURIComponent(agent)}?runs=${TRACED_RUNS}`)
      .then((response) => {
        if (!response.ok) throw new Error(`The traces could not be read (${response.status})`);
        return response.json();
      })
      .then((spans: Span[]) => {
        if (current) setTraces(runTraces(Array.isArray(spans) ? spans : [], agent));
      })
      .catch((reason: unknown) => {
        if (current) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      current = false;
    };
  }, [agent]);

  if (error) return <div className={`${styles.empty} ${styles.failed}`}>{error}</div>;
  if (traces === null) return <div className={styles.empty}>Loading traces…</div>;
  if (traces.length === 0) {
    return (
      <div className={styles.empty}>
        No traces of this agent. Tracing writes them with <span className="mono">FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true</span>.
      </div>
    );
  }

  const trace = traces.find((candidate) => candidate.runId === picked) ?? traces[0]!;
  const total = Math.max(1, trace.end - trace.start);

  return (
    <div className={styles.section} data-testid="traces">
      <div className={styles.runs} role="group" aria-label="Runs">
        {traces.map((candidate) => (
          <button
            key={candidate.runId}
            type="button"
            className="seg mono"
            aria-pressed={candidate === trace}
            onClick={() => setPicked(candidate.runId)}
          >
            {shortId(candidate.runId)}
            {candidate.failed && <span className={styles.failed}> ✕</span>}
          </button>
        ))}
      </div>
      <span className={styles.label}>
        Run {shortId(trace.runId)} · {duration(total / NS_PER_MS)}
      </span>
      <div className={styles.waterfall}>
        {trace.spans.map(({ span, depth }) => {
          const left = ((span.start_time - trace.start) / total) * 100;
          const width = ((span.end_time - span.start_time) / total) * 100;
          return (
            <React.Fragment key={span.context.span_id}>
              <span className={`mono ${styles.spanName}`} style={{ paddingLeft: depth * 14 }} title={span.name}>
                {span.name}
              </span>
              <div className={styles.lane}>
                <div
                  className={styles.bar}
                  data-root={depth === 0 || undefined}
                  data-status={span.status?.status_code === 'ERROR' ? 'error' : undefined}
                  style={{ left: `${Math.max(0, left)}%`, width: `${Math.min(100, width)}%` }}
                />
              </div>
              <span className={`mono num ${styles.quiet}`} style={{ textAlign: 'right' }}>
                {duration((span.end_time - span.start_time) / NS_PER_MS)}
              </span>
            </React.Fragment>
          );
        })}
      </div>
      {trace.correlationId && (
        <button type="button" className={styles.link} onClick={() => onOpenTrace(trace.correlationId!)}>
          Open in the trace viewer →
        </button>
      )}
    </div>
  );
};

export default TracesTab;
