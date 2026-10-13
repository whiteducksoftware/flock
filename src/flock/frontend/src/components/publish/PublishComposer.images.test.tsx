import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PublishComposer from './PublishComposer';

// "Picked up by" reads the agents; these tests count the requests for types and publishing
vi.mock('../../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/api')>()),
  fetchAgents: vi.fn(async () => []),
}));

const mockFetch = vi.fn();

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
  {
    name: 'Maybe',
    schema: {
      $defs: { Image: imageDef },
      type: 'object',
      properties: {
        note: { type: 'string', title: 'Note' },
        picture: { anyOf: [{ $ref: '#/$defs/Image' }, { type: 'null' }] },
      },
      required: ['note', 'picture'],
    },
  },
  {
    name: 'Strip',
    schema: {
      $defs: { Image: imageDef },
      type: 'object',
      properties: {
        title: { type: 'string', title: 'Title' },
        frames: { type: 'array', items: { $ref: '#/$defs/Image' }, title: 'Frames' },
      },
      required: ['title', 'frames'],
    },
  },
];

const png = (name: string) =>
  new File([new Uint8Array([137, 80, 78, 71, 13, 10])], name, { type: 'image/png' });

async function openForm(typeName: string) {
  mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ artifact_types: photoTypes }) });
  render(<PublishComposer />);
  await waitFor(() => expect(screen.getByRole('listbox', { name: 'Artifact types' })).toBeInTheDocument());
  fireEvent.click(await screen.findByRole('option', { name: new RegExp(`^${typeName}\\b`) }));
}

function publishedContent() {
  const call = mockFetch.mock.calls.find(([url]) => url === '/api/control/publish');
  return JSON.parse(call![1].body).content;
}

describe('PublishComposer image fields', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
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
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    const content = publishedContent();
    expect(content.caption).toBe('a red square');
    expect(content.picture.url.startsWith('data:image/png;base64,')).toBe(true);
  });

  it('requires a picture for a required Image field', async () => {
    await openForm('Photo');

    fireEvent.change(screen.getByLabelText(/caption/i), { target: { value: 'no picture' } });
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

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
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

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
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    expect(publishedContent()).toEqual({ title: 'empty' });
  });

  it('sends null for a required field that may be None', async () => {
    await openForm('Maybe');
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ correlation_id: 'c-4' }) });

    fireEvent.change(screen.getByLabelText(/note/i), { target: { value: 'no picture' } });
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    expect(publishedContent()).toEqual({ note: 'no picture', picture: null });
  });

  it('allows an empty required list of images unless the schema sets minItems', async () => {
    await openForm('Strip');
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ correlation_id: 'c-5' }) });

    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'blank' } });
    fireEvent.click(screen.getByRole('button', { name: /^publish$/i }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    expect(publishedContent()).toEqual({ title: 'blank', frames: [] });
  });
});
