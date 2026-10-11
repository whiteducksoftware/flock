import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import PublishControl from './PublishControl';
import { fileToImageUrl } from '../../utils/imageFields';

vi.mock('../../utils/imageFields', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../utils/imageFields')>()),
  fileToImageUrl: vi.fn(),
}));

const mockFetch = vi.fn();

const imageDef = { type: 'object', properties: { url: { type: 'string' } }, 'x-flock-image': true };
const types = [
  {
    name: 'Photo',
    schema: {
      $defs: { Image: imageDef },
      type: 'object',
      properties: { picture: { $ref: '#/$defs/Image' } },
      required: ['picture'],
    },
  },
  {
    name: 'Note',
    schema: { type: 'object', properties: { text: { type: 'string', title: 'Text' } }, required: ['text'] },
  },
];

function deferred() {
  let resolve!: (value: string) => void;
  const promise = new Promise<string>((r) => (resolve = r));
  return { promise, resolve };
}

const file = (name: string) => new File([new Uint8Array([1])], name, { type: 'image/png' });

async function openForm(typeName: string) {
  mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ artifact_types: types }) });
  render(<PublishControl />);
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

describe('PublishControl image conversions that finish late', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('drops a conversion that finishes after the artifact type changed', async () => {
    const pending = deferred();
    vi.mocked(fileToImageUrl).mockReturnValueOnce(pending.promise);
    await openForm('Photo');
    fireEvent.change(screen.getByLabelText(/picture/i), { target: { files: [file('old.png')] } });

    fireEvent.change(screen.getByLabelText(/artifact type/i), { target: { value: 'Note' } });
    await act(async () => pending.resolve('data:image/png;base64,T0xE'));
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ correlation_id: 'c' }) });
    fireEvent.change(screen.getByLabelText(/text/i), { target: { value: 'hello' } });
    fireEvent.click(screen.getByRole('button', { name: /publish artifact/i }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    expect(publishedContent()).toEqual({ text: 'hello' });
  });

  it('keeps the newest picture when two conversions finish out of order', async () => {
    const first = deferred();
    const second = deferred();
    vi.mocked(fileToImageUrl).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    await openForm('Photo');
    const picker = screen.getByLabelText(/picture/i);

    fireEvent.change(picker, { target: { files: [file('first.png')] } });
    fireEvent.change(picker, { target: { files: [file('second.png')] } });
    await act(async () => second.resolve('data:image/png;base64,U0VDT05E'));
    await act(async () => first.resolve('data:image/png;base64,RklSU1Q='));

    expect(screen.getByAltText('second.png')).toBeInTheDocument();
    expect(screen.queryByAltText('first.png')).not.toBeInTheDocument();
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ correlation_id: 'c' }) });
    fireEvent.click(screen.getByRole('button', { name: /publish artifact/i }));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    expect(publishedContent().picture.url).toBe('data:image/png;base64,U0VDT05E');
  });

  it('waits for a pending conversion before publishing', async () => {
    const pending = deferred();
    vi.mocked(fileToImageUrl).mockReturnValueOnce(pending.promise);
    await openForm('Photo');
    fireEvent.change(screen.getByLabelText(/picture/i), { target: { files: [file('slow.png')] } });

    const submit = screen.getByRole('button', { name: /processing pictures/i });
    expect(submit).toBeDisabled();
    fireEvent.click(submit);
    expect(mockFetch).toHaveBeenCalledTimes(1); // only the artifact types

    await act(async () => pending.resolve('data:image/png;base64,U0xPVw=='));
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ correlation_id: 'c' }) });
    fireEvent.click(screen.getByRole('button', { name: /publish artifact/i }));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    expect(publishedContent().picture.url).toBe('data:image/png;base64,U0xPVw==');
  });

  it('ignores the failure of a conversion that a newer picture replaced', async () => {
    let rejectFirst!: (error: Error) => void;
    const first = new Promise<string>((_, reject) => (rejectFirst = reject));
    vi.mocked(fileToImageUrl)
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce('data:image/png;base64,TkVX');
    await openForm('Photo');
    const picker = screen.getByLabelText(/picture/i);

    fireEvent.change(picker, { target: { files: [file('broken.png')] } });
    fireEvent.change(picker, { target: { files: [file('new.png')] } });
    await waitFor(() => expect(screen.getByAltText('new.png')).toBeInTheDocument());
    await act(async () => rejectFirst(new Error('unreadable')));

    expect(screen.queryByText(/could not read/i)).not.toBeInTheDocument();
  });

  it('does not stay disabled for a stalled conversion that a newer picture replaced', async () => {
    vi.mocked(fileToImageUrl)
      .mockReturnValueOnce(new Promise<string>(() => {})) // never settles
      .mockResolvedValueOnce('data:image/png;base64,TkVX');
    await openForm('Photo');
    const picker = screen.getByLabelText(/picture/i);

    fireEvent.change(picker, { target: { files: [file('stalled.png')] } });
    fireEvent.change(picker, { target: { files: [file('new.png')] } });

    await waitFor(() => expect(screen.getByAltText('new.png')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /publish artifact/i })).toBeEnabled();
  });

  it('does not stay disabled for a stalled conversion after the type changed', async () => {
    vi.mocked(fileToImageUrl).mockReturnValueOnce(new Promise<string>(() => {}));
    await openForm('Photo');
    fireEvent.change(screen.getByLabelText(/picture/i), { target: { files: [file('stalled.png')] } });

    fireEvent.change(screen.getByLabelText(/artifact type/i), { target: { value: 'Note' } });

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /publish artifact/i })).toBeEnabled()
    );
  });
});
