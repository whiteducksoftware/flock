import { describe, expect, it } from 'vitest';
import { ROOT, schemaErrors } from './schemaErrors';

const imageDef = { type: 'object', properties: { url: { type: 'string' } }, required: ['url'], 'x-flock-image': true };

const schema = {
  $defs: { Image: imageDef, Priority: { enum: ['low', 'high'], type: 'string' } },
  type: 'object',
  properties: {
    subject: { type: 'string' },
    count: { type: 'integer' },
    score: { type: 'number' },
    urgent: { type: 'boolean' },
    tags: { type: 'array', items: { type: 'string' } },
    sizes: { type: 'array', items: { type: 'integer' } },
    meta: { type: 'object' },
    note: { anyOf: [{ type: 'string' }, { type: 'null' }], default: null },
    level: { enum: ['a', 'b'], type: 'string' },
    priority: { $ref: '#/$defs/Priority' },
    picture: { $ref: '#/$defs/Image' },
  },
  required: ['subject', 'count'],
};

const valid = {
  subject: 'Double charge',
  count: 2,
  score: 0.5,
  urgent: true,
  tags: ['billing'],
  sizes: [1, 2],
  meta: { source: 'mail' },
  note: null,
  level: 'a',
  priority: 'high',
  picture: { url: 'data:image/png;base64,AA==' },
};

describe('schemaErrors', () => {
  it('finds nothing wrong with a payload that fits', () => {
    expect(schemaErrors(valid, schema)).toEqual({});
    expect(schemaErrors({ subject: 'x', count: 1 }, schema)).toEqual({});
  });

  it('wants an object', () => {
    expect(schemaErrors([1, 2], schema)).toEqual({ [ROOT]: 'The payload must be a JSON object' });
    expect(schemaErrors('text', schema)).toEqual({ [ROOT]: 'The payload must be a JSON object' });
    expect(schemaErrors(null, schema)).toEqual({ [ROOT]: 'The payload must be a JSON object' });
  });

  it('wants the required fields', () => {
    expect(schemaErrors({ subject: 'x' }, schema)).toEqual({ count: 'count is required' });
  });

  it('checks each scalar type', () => {
    expect(
      schemaErrors({ ...valid, subject: 3, count: 1.5, score: '1', urgent: 'yes', meta: [1] }, schema)
    ).toEqual({
      subject: 'subject must be a string',
      count: 'count must be an integer',
      score: 'score must be a number',
      urgent: 'urgent must be true or false',
      meta: 'meta must be an object',
    });
  });

  it('checks a list and the type of its items', () => {
    expect(schemaErrors({ ...valid, tags: 'billing', sizes: [1, 'two'] }, schema)).toEqual({
      tags: 'tags must be a list of strings',
      sizes: 'sizes must be a list of integers',
    });
  });

  it('allows null only where an anyOf has a null', () => {
    expect(schemaErrors({ ...valid, note: null }, schema)).toEqual({});
    expect(schemaErrors({ ...valid, note: 5 }, schema)).toEqual({ note: 'note must be a string or null' });
    expect(schemaErrors({ ...valid, subject: null }, schema)).toEqual({ subject: 'subject must be a string' });
  });

  it('checks enum members, inline and behind a $ref', () => {
    expect(schemaErrors({ ...valid, level: 'c', priority: 'urgent' }, schema)).toEqual({
      level: 'level must be one of a, b',
      priority: 'priority must be one of low, high',
    });
  });

  it('wants an object for an image', () => {
    expect(schemaErrors({ ...valid, picture: 'cat.png' }, schema)).toEqual({ picture: 'picture must be an object' });
  });

  it('leaves fields it does not know to the server', () => {
    expect(schemaErrors({ ...valid, extra: 1 }, schema)).toEqual({});
  });
});
