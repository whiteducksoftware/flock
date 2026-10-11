import { describe, expect, it } from 'vitest';
import type { Edge, Node } from '@xyflow/react';
import { lineageOf } from './lineage';

const agent = (id: string, outputTypes: string[] = [], typeLabels?: Record<string, string>): Node => ({
  id,
  type: 'agent',
  position: { x: 0, y: 0 },
  data: { name: id, outputTypes, typeLabels },
});
const flow = (source: string, target: string, messageType: string, decisionChoice?: string): Edge => ({
  id: `${source}-${target}-${messageType}-${decisionChoice ?? ''}`,
  source,
  target,
  type: 'message_flow',
  data: { messageType, messageCount: 1, decisionChoice, decisionUnsure: decisionChoice === 'UNSURE' },
});

// The triage flock of the design
const nodes = [
  agent('external', ['app.SupportTicket']),
  agent('triage', ['Decision[app.Route]']),
  agent('billing_team', ['app.TeamReply'], { 'Decision[app.Route]': '◆ Route.billing' }),
  agent('supervisor', ['app.TeamReply'], { 'Decision[app.Route]': '◆ Route.UNSURE' }),
  agent('crm_sync', ['app.CrmRecord']),
];
const edges = [
  flow('external', 'triage', 'app.SupportTicket'),
  flow('triage', 'billing_team', 'Decision[app.Route]', 'billing'),
  flow('triage', 'supervisor', 'Decision[app.Route]', 'UNSURE'),
  flow('billing_team', 'crm_sync', 'app.TeamReply'),
  flow('supervisor', 'crm_sync', 'app.TeamReply'),
];

describe('lineageOf', () => {
  it('leads a handle back to the subject it receives, and on to the consumers of the output', () => {
    expect(lineageOf('billing_team', nodes, edges)).toEqual({
      upstream: [
        { node: 'external', label: 'SupportTicket', decision: false },
        { node: 'triage', label: 'Route.billing', decision: true },
      ],
      outputs: [{ type: 'app.TeamReply', label: 'TeamReply', decision: false, consumers: [{ node: 'crm_sync', label: null }] }],
    });
  });

  it('lists a decider\'s routes as the consumers of its decision', () => {
    expect(lineageOf('triage', nodes, edges)).toEqual({
      upstream: [{ node: 'external', label: 'SupportTicket', decision: false }],
      outputs: [
        {
          type: 'Decision[app.Route]',
          label: 'Route',
          decision: true,
          consumers: [
            { node: 'billing_team', label: 'billing' },
            { node: 'supervisor', label: 'UNSURE' },
          ],
        },
      ],
    });
  });

  it('knows outputs no one consumes yet, and a source with nothing upstream', () => {
    expect(lineageOf('crm_sync', nodes, edges).outputs).toEqual([
      { type: 'app.CrmRecord', label: 'CrmRecord', decision: false, consumers: [] },
    ]);
    expect(lineageOf('external', nodes, edges).upstream).toEqual([]);
  });

  it('keeps a decision label the server already qualified (yes/no, scale, checklist)', () => {
    const escalation = [
      agent('triage', ['Decision[app.Escalate]']),
      agent('pager', ['app.Page'], { 'Decision[app.Escalate]': '◆ Escalate.yes' }),
    ];
    const lineage = lineageOf('pager', escalation, [flow('triage', 'pager', 'Decision[app.Escalate]', 'Escalate.yes')]);

    expect(lineage.upstream).toEqual([{ node: 'triage', label: 'Escalate.yes', decision: true }]);
  });

  it('qualifies an option that has dots of its own (Choice.from_options ids)', () => {
    const controls = [agent('mapper', ['Decision[app.Control]']), agent('auditor', ['app.Finding'], { 'Decision[app.Control]': '◆ Control.ORP.1.A1' })];
    const lineage = lineageOf('auditor', controls, [flow('mapper', 'auditor', 'Decision[app.Control]', 'ORP.1.A1')]);

    expect(lineage.upstream).toEqual([{ node: 'mapper', label: 'Control.ORP.1.A1', decision: true }]);
  });

  it('shows a consumer of the decision itself the decider, not the subject', () => {
    // Decision.of(Route): its edges carry the option too, but no handle label
    const audit = [...nodes, agent('audit', ['app.Entry'])];
    const lineage = lineageOf('audit', audit, [
      ...edges,
      flow('triage', 'audit', 'Decision[app.Route]', 'billing'),
      flow('triage', 'audit', 'Decision[app.Route]', 'UNSURE'),
    ]);

    expect(lineage.upstream).toEqual([{ node: 'triage', label: 'Route', decision: true }]);
  });

  it('shows what a source sent, consumed or not', () => {
    const source = { ...agent('external'), data: { name: 'external', outputTypes: [], sentByType: { 'app.SupportTicket': 3, 'app.Note': 1 } } };
    const lineage = lineageOf('external', [source], [flow('external', 'triage', 'app.SupportTicket')]);

    expect(lineage.outputs.map((output) => [output.label, output.consumers.map((consumer) => consumer.node)])).toEqual([
      ['SupportTicket', ['triage']],
      ['Note', []],
    ]);
  });

  it('names each upstream producer once per type', () => {
    expect(lineageOf('crm_sync', nodes, edges).upstream).toEqual([
      { node: 'billing_team', label: 'TeamReply', decision: false },
      { node: 'supervisor', label: 'TeamReply', decision: false },
    ]);
  });
});
