import { describe, expect, it } from 'vitest';
import type { Agent } from '../../services/api';
import { orList, pickedUpBy } from './pickedUpBy';

const agent = (name: string, subscriptions: string[], output_types: string[]): Agent => ({
  name,
  description: '',
  status: 'ready',
  subscriptions,
  output_types,
});

// The ticket triage of the mockups
const agents = [
  agent('triage', ['app.SupportTicket'], ['Decision[app.Route]']),
  agent('urgency', ['app.SupportTicket'], ['Decision[app.Urgent]']),
  agent('billing_team', ['Decision[app.Route]'], ['app.TeamReply']),
  agent('supervisor', ['Decision[app.Route]'], ['app.TeamReply']),
  agent('pager', ['Decision[app.Route]', 'Decision[app.Urgent]'], ['app.Page']),
  agent('crm_sync', ['app.TeamReply'], ['app.CrmRecord']),
];

describe('pickedUpBy', () => {
  it('finds the subscribers and the agents that run after them on a decision', () => {
    const { direct, onward, viaDecisions } = pickedUpBy('app.SupportTicket', agents);

    expect(direct.map((a) => a.name)).toEqual(['triage', 'urgency']);
    // pager subscribes to both decisions and is named once
    expect(onward.map((a) => a.name)).toEqual(['billing_team', 'supervisor', 'pager']);
    expect(viaDecisions).toBe(true);
  });

  it('tells when no decision leads on', () => {
    const { direct, onward, viaDecisions } = pickedUpBy('app.TeamReply', [
      ...agents,
      agent('archive', ['app.CrmRecord'], []),
    ]);

    expect(direct.map((a) => a.name)).toEqual(['crm_sync']);
    expect(onward.map((a) => a.name)).toEqual(['archive']);
    expect(viaDecisions).toBe(false);
  });

  it('finds nobody for a type without subscribers', () => {
    expect(pickedUpBy('app.Page', agents)).toEqual({ direct: [], onward: [], viaDecisions: false });
  });
});

describe('orList', () => {
  it('joins names with commas and a last "or"', () => {
    expect(orList(['a'])).toBe('a');
    expect(orList(['a', 'b'])).toBe('a or b');
    expect(orList(['a', 'b', 'c'])).toBe('a, b or c');
  });
});
