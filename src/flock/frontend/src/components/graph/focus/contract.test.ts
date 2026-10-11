import { describe, expect, it } from 'vitest';
import type { Node } from '@xyflow/react';
import { contractOf, fieldsOf } from './contract';

const schemas = {
  'app.SupportTicket': {
    properties: {
      subject: { type: 'string', title: 'Subject' },
      message: { type: 'string', description: "The customer's issue or question" },
      priority: { anyOf: [{ type: 'integer' }, { type: 'null' }], default: null },
    },
    required: ['subject', 'message'],
  },
  'app.TeamReply': {
    properties: {
      team: { type: 'string' },
      reply: { type: 'string', description: 'Short, friendly answer to the customer' },
      tags: { type: 'array', items: { type: 'string' } },
      ticket: { $ref: '#/$defs/SupportTicket' },
    },
    required: ['team', 'reply'],
  },
};

const node = (id: string, data: Record<string, unknown>): Node => ({ id, type: 'agent', position: { x: 0, y: 0 }, data });

describe('fieldsOf', () => {
  it('names each field\'s type the way Python spells it', () => {
    expect(fieldsOf(schemas['app.TeamReply'])).toEqual([
      { name: 'team', type: 'str', description: null, required: true },
      { name: 'reply', type: 'str', description: 'Short, friendly answer to the customer', required: true },
      { name: 'tags', type: 'list[str]', description: null, required: false },
      { name: 'ticket', type: 'SupportTicket', description: null, required: false },
    ]);
    expect(fieldsOf(schemas['app.SupportTicket'])[2]).toEqual({ name: 'priority', type: 'int | None', description: null, required: false });
  });
});

describe('contractOf', () => {
  const nodes = [
    node('triage', { subscriptions: ['app.SupportTicket'], outputTypes: ['Decision[app.Route]'] }),
    node('billing_team', {
      subscriptions: ['Decision[app.Route]'],
      typeLabels: { 'Decision[app.Route]': '◆ Route.billing' },
      outputTypes: ['app.TeamReply'],
    }),
  ];

  it('shows what a handle delivers: the subject the decider read', () => {
    expect(contractOf('billing_team', nodes, schemas)).toEqual({
      consumes: [
        {
          type: 'Decision[app.Route]',
          label: 'Route.billing',
          decision: true,
          note: 'decision handle · receives the SupportTicket',
          fields: fieldsOf(schemas['app.SupportTicket']),
        },
      ],
      publishes: [{ type: 'app.TeamReply', label: 'TeamReply', decision: false, note: null, fields: fieldsOf(schemas['app.TeamReply']) }],
    });
  });

  it('finds the decider of a handle by the edge that brings it, when two decide the same question', () => {
    const two = [
      node('mail_triage', { subscriptions: ['app.Email'], outputTypes: ['Decision[app.Route]'] }),
      node('ticket_triage', { subscriptions: ['app.SupportTicket'], outputTypes: ['Decision[app.Route]'] }),
      node('billing_team', {
        subscriptions: ['Decision[app.Route]'],
        typeLabels: { 'Decision[app.Route]': '◆ Route.billing' },
      }),
    ];
    const edges = [
      { id: 'e', source: 'ticket_triage', target: 'billing_team', data: { messageType: 'Decision[app.Route]', decisionChoice: 'billing' } },
    ];

    expect(contractOf('billing_team', two, schemas, edges).consumes[0]).toMatchObject({
      note: 'decision handle · receives the SupportTicket',
      fields: fieldsOf(schemas['app.SupportTicket']),
    });
  });

  it('shows a decider\'s decisions without fields, and a type without a schema as such', () => {
    const contract = contractOf('triage', nodes, { 'app.SupportTicket': schemas['app.SupportTicket'] });

    expect(contract.consumes[0]).toMatchObject({ label: 'SupportTicket', note: null });
    expect(contract.publishes).toEqual([
      { type: 'Decision[app.Route]', label: 'Route', decision: true, note: 'decision · routes to its handles', fields: [] },
    ]);
    expect(contractOf('triage', nodes, {}).consumes[0]).toMatchObject({ note: 'no schema known', fields: [] });
  });
});
