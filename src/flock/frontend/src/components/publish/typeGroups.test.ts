import { describe, expect, it } from 'vitest';
import { groupTypes } from './typeGroups';

describe('groupTypes', () => {
  const type = (name: string) => ({ name, schema: { type: 'object', properties: {} } });
  const types = [
    type('flock.models.system_artifacts.WorkflowError'),
    type('app.SupportTicket'),
    type('app.TeamReply'),
    type('flock.decisions.explain.Explanation'),
    type('Decision[app.Route]'),
  ];
  const names = (list: { name: string }[]) => list.map((t) => t.name);

  it('puts each type in its group, in the order of the server', () => {
    const groups = groupTypes(types);

    expect(names(groups.yours)).toEqual(['app.SupportTicket', 'app.TeamReply']);
    expect(names(groups.decisions)).toEqual(['Decision[app.Route]']);
    expect(names(groups.system)).toEqual([
      'flock.models.system_artifacts.WorkflowError',
      'flock.decisions.explain.Explanation',
    ]);
  });

  it('searches the short names, in any case', () => {
    const groups = groupTypes(types, ' ticket ');
    expect(names(groups.yours)).toEqual(['app.SupportTicket']);
    expect(groups.decisions).toEqual([]);
    // the module path is not part of the name
    expect(groupTypes(types, 'flock').system).toEqual([]);
  });
});
