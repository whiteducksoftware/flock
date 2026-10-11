import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
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

/** An event's identity: the same run, place, kind and content. */
const keyOf = (event: StreamEvent) => JSON.stringify([event.run_id, event.sequence, event.output_type, event.content]);

/** The tab shows at most this much of the latest output. */
export const MAX_LIVE_CHARS = 100_000;

/** Tokens run on as text; logs, stdout and stderr get lines of their own. */
const join = (text: string, event: StreamEvent): string => {
  if (event.output_type === 'llm_token') return text + event.content;
  return `${text && !text.endsWith('\n') ? `${text}\n` : text}${event.content}\n`;
};

const latestOf = (text: string): string => (text.length > MAX_LIVE_CHARS ? `…${text.slice(-MAX_LIVE_CHARS)}` : text);

/** The text of a history, its latest part. */
export function streamText(events: StreamEvent[]): string {
  let text = '';
  for (const event of events) text = join(text, event);
  return latestOf(text);
}

/** The text with one more event, without rebuilding it from all events. */
export const appendStream = (text: string, event: StreamEvent): string => latestOf(join(text, event));

/**
 * The agent's output as it streams: the server's history, then live
 * `streaming_output` events. Each opening starts from the history, so
 * switching tabs never repeats output. Follows the end while scrolled there.
 */
const LiveTab: React.FC<{ agent: string; running: boolean }> = ({ agent, running }) => {
  // The text so far; events are appended, never kept (a history can hold 100,000s)
  const [text, setText] = useState<string | null>(null);
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
      else setText((previous) => appendStream(previous ?? '', event));
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
        // One lookup per live event, however long the history (it can hold 100,000s)
        const known = new Set(history.map(keyOf));
        setText(streamText([...history, ...pending.filter((event) => !known.has(keyOf(event)))]));
      });

    return () => {
      current = false;
      client.off('streaming_output', onEvent);
    };
  }, [agent]);


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
      {text === null ? (
        <div className={styles.empty}>Loading output…</div>
      ) : text === '' ? (
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
