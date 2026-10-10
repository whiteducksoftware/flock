import { describe, it, expect } from 'vitest';
import { imageFieldKind, fileToImageUrl } from './imageFields';

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
