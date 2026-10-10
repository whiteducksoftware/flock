import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PublishControl from './PublishControl';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const imageDef = {
  type: 'object',
  properties: { url: { type: 'string' } },
  required: ['url'],
  title: 'Image',
  'x-flock-image': true,
};

const photoTypes = [
  {
    name: 'Photo',
    schema: {
      $defs: { Image: imageDef },
      type: 'object',
      properties: {
        caption: { type: 'string', title: 'Caption' },
        picture: { $ref: '#/$defs/Image' },
      },
      required: ['caption', 'picture'],
    },
  },
  {
    name: 'Album',
    schema: {
      $defs: { Image: imageDef },
      type: 'object',
      properties: {
        title: { type: 'string', title: 'Title' },
        pages: { type: 'array', items: { $ref: '#/$defs/Image' }, default: [], title: 'Pages' },
      },
      required: ['title'],
    },
  },
  {
    name: 'Gallery',
    schema: {
      $defs: { Image: imageDef },
      type: 'object',
      properties: {
        title: { type: 'string', title: 'Title' },
        pages: {
          anyOf: [{ type: 'array', items: { $ref: '#/$defs/Image' } }, { type: 'null' }],
          default: null,
          title: 'Pages',
        },
      },
      required: ['title'],
    },
  },
];

const png = (name: string) =>
  new File([new Uint8Array([137, 80, 78, 71, 13, 10])], name, { type: 'image/png' });

async function openForm(typeName: string) {
  mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ artifact_types: photoTypes }) });
  render(<PublishControl />);
  await waitFor(() => expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument());
  await waitFor(() => {
    const select = screen.getByLabelText(/artifact type/i) as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toContain(typeName);
  });
  fireEvent.change(screen.getByLabelText(/artifact type/i), { target: { value: typeName } });
}

function publishedContent() {
  const call = mockFetch.mock.calls.find(([url]) => url === '/api/control/publish');
  return JSON.parse(call![1].body).content;
}

describe('PublishControl image fields', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  it('shows an image picker instead of a text box for an Image field', async () => {
    await openForm('Photo');

    const picker = screen.getByLabelText(/picture/i) as HTMLInputElement;
    expect(picker.type).toBe('file');
    expect(picker.accept).toContain('image/png');
    expect(picker.multiple).toBe(false);
  });

  it('publishes the chosen picture as an Image data URL', async () => {
    await openForm('Photo');
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ correlation_id: 'c-1' }) });

    fireEvent.change(screen.getByLabelText(/caption/i), { target: { value: 'a red square' } });
    fireEvent.change(screen.getByLabelText(/picture/i), { target: { files: [png('red.png')] } });
    await waitFor(() => expect(screen.getByAltText(/red\.png/i)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /publish artifact/i }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    const content = publishedContent();
    expect(content.caption).toBe('a red square');
    expect(content.picture.url.startsWith('data:image/png;base64,')).toBe(true);
  });

  it('requires a picture for a required Image field', async () => {
    await openForm('Photo');

    fireEvent.change(screen.getByLabelText(/caption/i), { target: { value: 'no picture' } });
    fireEvent.click(screen.getByRole('button', { name: /publish artifact/i }));

    await waitFor(() => expect(screen.getByText(/picture is required/i)).toBeInTheDocument());
    expect(mockFetch).toHaveBeenCalledTimes(1); // only the artifact types
  });

  it('publishes several pictures for a list of images and can remove one', async () => {
    await openForm('Album');
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ correlation_id: 'c-2' }) });

    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'colors' } });
    const picker = screen.getByLabelText(/pages/i) as HTMLInputElement;
    expect(picker.multiple).toBe(true);
    fireEvent.change(picker, { target: { files: [png('a.png'), png('b.png'), png('c.png')] } });
    await waitFor(() => expect(screen.getByAltText(/c\.png/i)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /remove b\.png/i }));
    fireEvent.click(screen.getByRole('button', { name: /publish artifact/i }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    const content = publishedContent();
    expect(content.pages).toHaveLength(2);
    expect(content.pages.every((p: { url: string }) => p.url.startsWith('data:image/'))).toBe(true);
  });

  it('leaves an untouched optional list of images to its default', async () => {
    await openForm('Gallery');
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ correlation_id: 'c-3' }) });

    expect((screen.getByLabelText(/pages/i) as HTMLInputElement).multiple).toBe(true);
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'empty' } });
    fireEvent.click(screen.getByRole('button', { name: /publish artifact/i }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    expect(publishedContent()).toEqual({ title: 'empty' });
  });
});
