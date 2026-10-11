import { describe, expect, it } from 'vitest';
import {
  batchWait,
  formatAgo,
  formatClock,
  formatSpan,
  joinWait,
  portRows,
  scheduleText,
  tagOf,
  type PortRow,
} from './cardModel';

describe('scheduleText', () => {
  it('says how often or when an agent runs', () => {
    expect(scheduleText({ type: 'interval', interval: 'PT30S' })).toBe('every 30s');
    expect(scheduleText({ type: 'interval', interval: 'PT5M' })).toBe('every 5m');
    expect(scheduleText({ type: 'interval', interval: 'P1D' })).toBe('every 1d');
    expect(scheduleText({ type: 'time', time: '17:00:00' })).toBe('daily 17:00');
    expect(scheduleText({ type: 'datetime', datetime: '2026-10-12T09:00:00Z' })).toBe('once');
    expect(scheduleText({ type: 'cron', cron: '0 9 * * 1-5' })).toBe('0 9 * * 1-5');
  });
});

describe('time formats', () => {
  it('counts down and back in the units that matter', () => {
    expect(formatSpan(16 * 3600 + 34 * 60 + 5)).toBe('16 h 34 m');
    expect(formatSpan(190)).toBe('3 m 10 s');
    expect(formatSpan(45)).toBe('45 s');
    expect(formatAgo(23 * 3600 + 100)).toBe('23 h ago');
    expect(formatAgo(130)).toBe('2 m ago');
    expect(formatAgo(4)).toBe('4 s ago');
    expect(formatClock(24)).toBe('0:24');
    expect(formatClock(65)).toBe('1:05');
    expect(formatClock(3725)).toBe('1:02:05');
    expect(formatClock(-3)).toBe('0:00');
  });
});

describe('tagOf', () => {
  it('names a decider by its question, then the schedule, then the engine', () => {
    const questions = [{ name: 'Route' }, { name: 'Urgent' }];
    expect(tagOf({ decision: { questions }, engineTag: 'LLM' })).toEqual({ kind: 'decision', text: '◆ Route', more: 1 });
    expect(tagOf({ scheduleSpec: { type: 'cron', cron: '0 9 * * 1-5' }, engineTag: 'LLM' })).toEqual({
      kind: 'schedule',
      text: '0 9 * * 1-5',
    });
    expect(tagOf({ engineTag: 'LLM' })).toEqual({ kind: 'engine', text: 'LLM' });
    expect(tagOf({ isOpenClawAgent: true })).toEqual({ kind: 'engine', text: 'OpenClaw' });
    // Event-driven agents with an untagged engine get no badge
    expect(tagOf({})).toBeNull();
  });
});

describe('portRows', () => {
  it('labels inputs IN, AND and JOIN by subscription, outputs OUT', () => {
    const rows = portRows({
      // pager: Route.tech AND Urgent.yes; a join of TeamReply and CustomerScore
      subscriptionGroups: [['Decision[app.Route]', 'Decision[app.Urgent]'], ['app.TeamReply', 'app.CustomerScore']],
      typeLabels: { 'Decision[app.Route]': '◆ Route.tech', 'Decision[app.Urgent]': '◆ Urgent.yes' },
      logicOperations: [{ subscription_index: 1, subscription_types: [], join: { required_types: [] } }],
      receivedByType: { 'Decision[app.Route]': 1, 'app.TeamReply': 2 },
      outputTypes: ['app.Page'],
      sentByType: { 'app.Page': 1 },
    });

    expect(rows.map((row: PortRow) => [row.dir, row.label, row.count])).toEqual([
      ['in', 'Route.tech', 1],
      ['and', 'Urgent.yes', 0],
      ['in', 'TeamReply', 2],
      ['join', 'CustomerScore', 0],
      ['out', 'Page', 1],
    ]);
  });

  it('shows choice handles as decisions and hides a decider\'s Decision output', () => {
    const rows = portRows({
      subscriptions: ['Decision[app.Route]'],
      typeLabels: { 'Decision[app.Route]': '◆ Route.billing' },
      receivedByType: { 'Decision[app.Route]': 3 },
      outputTypes: ['Decision[app.Route]', 'app.Reply'],
      decision: { questions: [{ name: 'Route' }] },
    });

    expect(rows).toEqual([
      { dir: 'in', type: 'Decision[app.Route]', label: 'Route.billing', decision: true, count: 3, times: 1 },
      { dir: 'out', type: 'app.Reply', label: 'Reply', decision: false, count: 0, times: 1 },
    ]);
  });

  it('labels decision handles about the same subject AND, though they correlate like a join', () => {
    // pager: .consumes(Route.tech, Urgent.yes) joins on the ticket under the hood
    const rows = portRows({
      subscriptionGroups: [['Decision[app.Route]', 'Decision[app.Urgent]']],
      typeLabels: { 'Decision[app.Route]': '◆ Route.tech', 'Decision[app.Urgent]': '◆ Urgent.yes' },
      logicOperations: [{ subscription_index: 0, subscription_types: [], join: { required_types: [] } }],
    });

    expect(rows.map((row: PortRow) => [row.dir, row.label])).toEqual([
      ['in', 'Route.tech'],
      ['and', 'Urgent.yes'],
    ]);
  });

  it('counts a type a subscription needs several times once, with how many', () => {
    const rows = portRows({ subscriptionGroups: [['app.Note', 'app.Note', 'app.Note']], receivedByType: {} });

    expect(rows).toEqual([{ dir: 'in', type: 'app.Note', label: 'Note', decision: false, count: 0, times: 3 }]);
  });

  it('falls back to one row per subscribed type without groups, plus types received anyway', () => {
    const rows = portRows({ subscriptions: ['app.A', 'app.B'], receivedByType: { 'app.C': 4 } });

    expect(rows.map((row: PortRow) => [row.dir, row.label, row.count])).toEqual([
      ['in', 'A', 0],
      ['in', 'B', 0],
      ['in', 'C', 4],
    ]);
  });
});

describe('waits', () => {
  // Seconds since the snapshot arrived; the server counted down to then
  const age = 6;

  const joinOf = (index: number, groups: { key: string; elapsed: number; expiresIn: number | null }[]) => ({
    subscription_index: index,
    subscription_types: [],
    join: { window_type: 'time', window_value: 60, window_unit: 'seconds' },
    waiting_state: {
      is_waiting: true,
      correlation_groups: groups.map((group) => ({
        correlation_key: `('${group.key}',)`,
        elapsed_seconds: group.elapsed,
        expires_in_seconds: group.expiresIn,
        collected_types: { 'app.TeamReply': 1 },
        required_types: { 'app.TeamReply': 1, 'app.CustomerScore': 1 },
        is_complete: false,
        is_expired: false,
      })),
    },
  });

  it('reads the open join: its key, how much is there and when it expires', () => {
    const wait = joinWait(
      [
        joinOf(0, [
          { key: 'T-0002', elapsed: 20, expiresIn: 40 },
          { key: 'T-0001', elapsed: 30, expiresIn: 30 },
        ]),
      ],
      age,
    );

    expect(wait).toEqual({ key: 'T-0001', collected: 1, required: 2, secondsLeft: 24, more: 1 });
  });

  it('takes the oldest open join of all the agent\'s joins', () => {
    const wait = joinWait(
      [joinOf(0, [{ key: 'T-0003', elapsed: 5, expiresIn: 55 }]), joinOf(1, [{ key: 'T-0001', elapsed: 40, expiresIn: 20 }])],
      age,
    );

    expect(wait).toMatchObject({ key: 'T-0001', secondsLeft: 14, more: 1 });
  });

  it('has no countdown for a join window counted in artifacts', () => {
    expect(joinWait([joinOf(0, [{ key: 'T-0001', elapsed: 40, expiresIn: null }])], age)?.secondsLeft).toBeNull();
  });

  it('reads the batch: items so far, the target and the timeout', () => {
    const wait = batchWait(
      [
        {
          subscription_index: 0,
          subscription_types: [],
          batch: { strategy: 'hybrid', size: 5, timeout_seconds: 60 },
          waiting_state: {
            is_waiting: true,
            batch_state: { items_collected: 3, items_target: 5, timeout_seconds: 60, timeout_remaining_seconds: 30 },
          },
        },
      ],
      age,
    );

    expect(wait).toEqual({ collected: 3, target: 5, secondsLeft: 24 });
  });

  it('has nothing to show when nothing waits', () => {
    expect(joinWait([], age)).toBeNull();
    expect(batchWait([{ subscription_index: 0, subscription_types: [], waiting_state: { is_waiting: false } }], age)).toBeNull();
  });
});
