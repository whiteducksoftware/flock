import { describe, expect, it } from 'vitest';
import { DELIVERED, DELIVERY_FAILED, receiptOf, receiptText } from './deliveries';

const delivered = { sink: 'billing-api', method: 'POST', target: 'myapp:/billing', status: 200, attempts: 1, latency_ms: 41.2, artifact_ids: ['a'] };
const failed = { sink: 'billing-api', method: 'POST', target: 'myapp:/billing', status: 503, attempts: 4, error: 'HTTP 503: down', artifact_ids: ['a'] };

describe('receipts', () => {
  it('reads a delivery receipt', () => {
    const receipt = receiptOf(DELIVERED, delivered)!;

    expect(receipt.ok).toBe(true);
    expect(receiptText(receipt)).toBe('POST myapp:/billing · 200 · 41 ms');
  });

  it('reads a failed delivery, with its status or else its error', () => {
    expect(receiptText(receiptOf(DELIVERY_FAILED, failed)!)).toBe('POST myapp:/billing · HTTP 503 · 4 attempts');
    const unsent = receiptOf(DELIVERY_FAILED, { ...failed, status: null, attempts: 0, error: 'Environment variable MYAPP_TOKEN is not set' })!;
    expect(unsent.ok).toBe(false);
    expect(receiptText(unsent)).toBe('POST myapp:/billing · Environment variable MYAPP_TOKEN is not set');
  });

  it('is no receipt for other types, also ones of the same name', () => {
    expect(receiptOf('app.Delivered', delivered)).toBeNull();
    expect(receiptOf('app.Reply', { text: 'hi' })).toBeNull();
  });
});
