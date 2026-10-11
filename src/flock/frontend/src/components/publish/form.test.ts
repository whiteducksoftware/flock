import { describe, expect, it } from 'vitest';
import { fieldType, formToPayload, initialFormData, isRequiredField, payloadToForm } from './form';

const imageDef = { type: 'object', properties: { url: { type: 'string' } }, 'x-flock-image': true };

const schema = {
  $defs: { Image: imageDef },
  type: 'object',
  properties: {
    subject: { type: 'string' },
    count: { type: 'integer' },
    urgent: { type: 'boolean' },
    tags: { type: 'array', items: { type: 'string' }, default: ['new'] },
    sizes: { type: 'array', items: { type: 'number' } },
    note: { anyOf: [{ type: 'string' }, { type: 'null' }], default: null },
    level: { enum: ['a', 'b'], type: 'string', default: 'a' },
    picture: { $ref: '#/$defs/Image' },
    pages: { type: 'array', items: { $ref: '#/$defs/Image' }, default: [] },
  },
  required: ['subject', 'picture'],
};

describe('initialFormData', () => {
  it('starts every field empty or at its default', () => {
    expect(initialFormData(schema)).toEqual({
      subject: '',
      count: '',
      urgent: false,
      tags: 'new',
      sizes: '',
      note: '', // a None default shows as an empty text
      level: 'a',
      picture: null,
      pages: [],
    });
  });
});

describe('formToPayload', () => {
  it('converts each value to its schema type', () => {
    const payload = formToPayload(
      {
        subject: 'Double charge',
        count: '3',
        urgent: true,
        tags: ' billing \n\nrefund',
        sizes: '1.5\nx\n2',
        note: 'call back',
        level: 'b',
        picture: { name: 'a.png', url: 'data:a' },
        pages: [],
      },
      schema
    );

    expect(payload).toEqual({
      subject: 'Double charge',
      count: 3,
      urgent: true,
      tags: ['billing', 'refund'],
      sizes: [1.5, 2],
      note: 'call back',
      level: 'b',
      picture: { url: 'data:a' },
      // no pictures chosen: the default applies
    });
  });

  it('leaves out values of fields the type does not have', () => {
    expect(formToPayload({ subject: 'x', stale: 'y' }, { properties: { subject: { type: 'string' } } })).toEqual({
      subject: 'x',
    });
  });
});

describe('payloadToForm', () => {
  it('gives the form values of a payload, pictures as picked images with their url', () => {
    const values = payloadToForm(
      {
        subject: 'Double charge',
        count: 3,
        tags: ['billing', 'refund'],
        picture: { url: 'data:a' },
        pages: [{ url: 'data:b' }, { url: 'data:c' }],
      },
      schema
    );

    expect(values).toEqual({
      subject: 'Double charge',
      count: 3,
      urgent: false,
      tags: 'billing\nrefund',
      sizes: '',
      note: '', // a None default shows as an empty text
      level: 'a',
      picture: { name: 'picture', url: 'data:a' },
      pages: [
        { name: 'pages 1', url: 'data:b' },
        { name: 'pages 2', url: 'data:c' },
      ],
    });
  });

  it('round-trips with formToPayload', () => {
    const payload = {
      subject: 'x',
      count: 1,
      urgent: true,
      tags: ['a', 'b'],
      sizes: [1, 2],
      note: 'n',
      level: 'b',
      picture: { url: 'data:a' },
      pages: [{ url: 'data:b' }],
    };

    expect(formToPayload(payloadToForm(payload, schema), schema)).toEqual(payload);
  });
});

describe('fieldType', () => {
  it('names the type as Python does', () => {
    const type = (key: string) => fieldType(schema.properties[key as keyof typeof schema.properties], schema);
    expect(['subject', 'count', 'urgent', 'tags', 'sizes', 'note', 'level', 'picture', 'pages'].map(type)).toEqual([
      'str',
      'int',
      'bool',
      'list[str]',
      'list[float]',
      'str | None',
      'enum',
      'Image',
      'list[Image]',
    ]);
  });
});

describe('isRequiredField', () => {
  it('follows the checks before publishing', () => {
    const required = (key: string) =>
      isRequiredField(key, schema.properties[key as keyof typeof schema.properties], schema);
    expect(required('subject')).toBe(true); // listed
    expect(required('count')).toBe(true); // a scalar without a default
    expect(required('tags')).toBe(false); // a list
    expect(required('note')).toBe(false); // a default
    expect(required('picture')).toBe(true);
    expect(required('pages')).toBe(false); // no minItems
  });
});
