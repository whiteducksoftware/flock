import { describe, expect, it } from 'vitest';
import { fieldType, formLosses, formToPayload, initialFormData, isRequiredField, payloadToForm } from './form';

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

describe('formLosses', () => {
  it('finds nothing to lose in the JSON the form itself made', () => {
    const form = { ...initialFormData(schema), subject: 'x', count: '2', picture: { name: 'p', url: 'data:a' } };

    expect(formLosses(formToPayload(form, schema), schema)).toEqual([]);
  });

  it('names the fields the form would change or drop', () => {
    expect(
      formLosses(
        {
          subject: 'x',
          count: 1,
          urgent: false,
          sizes: [],
          level: 'a',
          picture: { url: 'data:a' },
          note: null, // None would become an empty text
          tags: ['a\nb', ''], // one item per line splits and drops them
          pages: [], // an empty list would give way to the default
          extra: 1, // not a field of the type
        },
        schema,
      ),
    ).toEqual(['tags', 'note', 'pages', 'extra']);
  });

  it('names fields whose values the form cannot show: lists of objects, objects', () => {
    const nested = {
      type: 'object',
      properties: {
        name: { type: 'string' },
        items: { type: 'array', items: { type: 'object' } },
        meta: { type: 'object' },
        grid: { type: 'array', items: { type: 'string' } },
      },
    };

    expect(
      formLosses({ name: 'x', items: [{ name: 'one' }], meta: { a: 1 }, grid: [['a']] }, nested)
    ).toEqual(['items', 'meta', 'grid']);
  });

  it('names fields the form would add that the JSON leaves out', () => {
    expect(formLosses({ subject: 'x', count: 1, picture: { url: 'data:a' } }, schema)).toEqual([
      'urgent',
      'tags',
      'sizes',
      'note',
      'level',
    ]);
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
