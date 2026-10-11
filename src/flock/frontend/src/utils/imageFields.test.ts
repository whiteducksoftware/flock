import { describe, it, expect } from 'vitest';
import { imageFieldKind, fileToImageUrl, outputType, valueAtKeys } from './imageFields';

const schema = {
  $defs: {
    Image: {
      type: 'object',
      properties: { url: { type: 'string' } },
      'x-flock-image': true,
    },
    Note: { type: 'object', properties: { url: { type: 'string' } } },
  },
  properties: {
    picture: { $ref: '#/$defs/Image' },
    cover: { anyOf: [{ $ref: '#/$defs/Image' }, { type: 'null' }], default: null },
    pages: { type: 'array', items: { $ref: '#/$defs/Image' }, default: [] },
    note: { $ref: '#/$defs/Note' },
    caption: { type: 'string' },
  },
};

describe('imageFieldKind', () => {
  it('recognises Image, optional Image and list[Image] fields', () => {
    expect(imageFieldKind(schema.properties.picture, schema)).toBe('one');
    expect(imageFieldKind(schema.properties.cover, schema)).toBe('one');
    expect(imageFieldKind(schema.properties.pages, schema)).toBe('many');
  });

  it('ignores other objects and plain fields', () => {
    expect(imageFieldKind(schema.properties.note, schema)).toBeNull();
    expect(imageFieldKind(schema.properties.caption, schema)).toBeNull();
  });
});

describe('fileToImageUrl', () => {
  it('reads a file as an image data URL', async () => {
    const file = new File([new Uint8Array([137, 80, 78, 71])], 'red.png', { type: 'image/png' });

    const url = await fileToImageUrl(file);

    expect(url.startsWith('data:image/png;base64,')).toBe(true);
  });
});

describe('outputType', () => {
  it('keeps formats that can be transparent as PNG', () => {
    expect(outputType('image/png')).toBe('image/png');
    expect(outputType('image/gif')).toBe('image/png');
    expect(outputType('image/webp')).toBe('image/png');
    expect(outputType('image/jpeg')).toBe('image/jpeg');
    expect(outputType('image/bmp')).toBe('image/jpeg');
  });
});

describe('valueAtKeys', () => {
  it('follows key segments, including keys with dots', () => {
    const payload = { picture: { url: 'a' }, album: { pages: [{ url: 'b' }, { url: 'c' }] }, views: { 'front.view': { url: 'd' } } };

    expect(valueAtKeys(payload, ['picture'])).toEqual({ url: 'a' });
    expect(valueAtKeys(payload, ['album', 'pages', 1])).toEqual({ url: 'c' });
    expect(valueAtKeys(payload, ['views', 'front.view'])).toEqual({ url: 'd' });
    expect(valueAtKeys(payload, ['album', 'missing', 3])).toBeUndefined();
  });
});
