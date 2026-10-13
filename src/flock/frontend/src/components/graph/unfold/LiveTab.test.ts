import { describe, expect, it } from 'vitest';
import { appendStream, MAX_LIVE_CHARS, streamText, type StreamEvent } from './LiveTab';

const event = (output_type: StreamEvent['output_type'], content: string): StreamEvent => ({
  agent_name: 'billing_team',
  run_id: 'r1',
  output_type,
  content,
  sequence: 0,
  is_final: false,
});

describe('the Live tab\'s text', () => {
  it('runs tokens on and gives logs lines of their own, one event at a time', () => {
    let text = '';
    for (const next of [event('llm_token', 'We '), event('llm_token', 'refunded'), event('log', 'tokens: 28'), event('llm_token', 'Done')]) {
      text = appendStream(text, next);
    }

    expect(text).toBe('We refunded\ntokens: 28\nDone');
    expect(streamText([event('llm_token', 'We '), event('log', 'tokens: 28')])).toBe('We \ntokens: 28\n');
  });

  it('keeps the latest output when there is too much of it', () => {
    const long = 'x'.repeat(MAX_LIVE_CHARS);

    const text = appendStream(long, event('llm_token', 'END'));

    expect(text.length).toBeLessThanOrEqual(MAX_LIVE_CHARS + 2);
    expect(text.startsWith('…')).toBe(true);
    expect(text.endsWith('END')).toBe(true);
  });
});
