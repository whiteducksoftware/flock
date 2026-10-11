import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { getWebSocketClient } from '../../../services/websocket';
import styles from './Unfolded.module.css';

/** A `streaming_output` event, live or from the agent's streaming history. */
export interface StreamEvent {
  agent_name: string;
  run_id: string;
  output_type: 'llm_token' | 'log' | 'stdout' | 'stderr';
  content: string;
  sequence: number;
  is_final: boolean;
}

const same = (a: StreamEvent, b: StreamEvent) =>
  a.run_id === b.run_id && a.sequence === b.sequence && a.output_type === b.output_type && a.content === b.content;

/** Tokens run on as text; logs, stdout and stderr get lines of their own. */
export function streamText(events: StreamEvent[]): string {
  let text = '';
  for (const event of events) {
    if (event.output_type === 'llm_token') {
      text += event.content;
    } else {
      if (text && !text.endsWith('\n')) text += '\n';
      text += `${event.content}\n`;
    }
  }
  return text;
}

/**
 * The agent's output as it streams: the server's history, then live
 * `streaming_output` events. Each opening starts from the history, so
 * switching tabs never repeats output. Follows the end while scrolled there.
 */
const LiveTab: React.FC<{ agent: string; running: boolean }> = ({ agent, running }) => {
  const [events, setEvents] = useState<StreamEvent[] | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement | null>(null);
  const following = useRef(true);

  useEffect(() => {
    let current = true;
    // Live events that come before the history: kept unless the history has them
    let early: StreamEvent[] | null = [];
    const onEvent = (event: StreamEvent) => {
      if (event.agent_name !== agent) return;
      if (early) early.push(event);
      else setEvents((previous) => [...(previous ?? []), event]);
    };
    const client = getWebSocketClient();
    client.on('streaming_output', onEvent);

    fetch(`/api/streaming-history/${encodeURIComponent(agent)}`)
      .then((response) => {
        if (!response.ok) throw new Error(`The output so far could not be read (${response.status})`);
        return response.json();
      })
      .catch((reason: unknown) => {
        // Live events still come; the tab says what is missing
        if (current) setHistoryError(reason instanceof Error ? reason.message : String(reason));
        return { events: [] };
      })
      .then((data: { events?: StreamEvent[] }) => {
        if (!current) return;
        const history = data.events ?? [];
        const pending = early ?? [];
        early = null;
        setEvents([...history, ...pending.filter((event) => !history.some((known) => same(known, event)))]);
      });

    return () => {
      current = false;
      client.off('streaming_output', onEvent);
    };
  }, [agent]);

  const text = useMemo(() => streamText(events ?? []), [events]);

  // Follow the end, unless the reader scrolled up (scrollIntoView would move the board)
  useLayoutEffect(() => {
    const element = scroller.current?.closest<HTMLElement>('[data-scroll]');
    if (element && following.current) element.scrollTop = element.scrollHeight;
  }, [text]);

  useEffect(() => {
    const element = scroller.current?.closest<HTMLElement>('[data-scroll]');
    if (!element) return;
    const onScroll = () => {
      following.current = element.scrollHeight - element.scrollTop - element.clientHeight < 24;
    };
    element.addEventListener('scroll', onScroll);
    return () => element.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div ref={scroller} data-testid="live">
      {historyError && <div className={`${styles.faint} ${styles.failed}`}>{historyError}</div>}
      {events === null ? (
        <div className={styles.empty}>Loading output…</div>
      ) : events.length === 0 ? (
        !historyError && <div className={styles.empty}>No output yet</div>
      ) : (
        <pre className={`mono ${styles.live}`}>
          {text}
          {running && <span className={styles.caret}>▍</span>}
        </pre>
      )}
    </div>
  );
};

export default LiveTab;
