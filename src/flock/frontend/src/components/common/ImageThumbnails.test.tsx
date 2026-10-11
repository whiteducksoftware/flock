import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ImageThumbnails from './ImageThumbnails';

const mockFetch = vi.fn();

const images = [
  { path: 'picture', keys: ['picture'], mime: 'image/jpeg', bytes: 42 * 1024, thumb: 'data:image/jpeg;base64,VEhVTUI=' },
  { path: 'pages[1]', keys: ['pages', 1], mime: 'image/png', bytes: 2048, thumb: 'data:image/png;base64,UEFHRQ==' },
  { path: 'views.front.view', keys: ['views', 'front.view'], mime: 'image/png', bytes: 1024, thumb: 'data:image/png;base64,VklFVw==' },
];

describe('ImageThumbnails', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows each thumbnail with its field, type and size', () => {
    render(<ImageThumbnails artifactId="a-1" images={images} />);

    expect(screen.getByAltText('picture')).toHaveAttribute('src', images[0]!.thumb);
    expect(screen.getByText(/picture · image\/jpeg · 42 KB/)).toBeInTheDocument();
    expect(screen.getByText(/pages\[1\] · image\/png · 2 KB/)).toBeInTheDocument();
  });

  it('loads the full image on demand', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        payload: { pages: [{ url: 'data:image/png;base64,MA==' }, { url: 'data:image/png;base64,RlVMTA==' }] },
      }),
    });
    render(<ImageThumbnails artifactId="a-1" images={images} />);

    fireEvent.click(screen.getByRole('button', { name: /open pages\[1\]/i }));

    await waitFor(() =>
      expect(screen.getByAltText('pages[1] (full size)')).toHaveAttribute('src', 'data:image/png;base64,RlVMTA==')
    );
    expect(mockFetch).toHaveBeenCalledWith('/api/v1/artifacts/a-1', expect.anything());
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(screen.queryByAltText('pages[1] (full size)')).not.toBeInTheDocument();
  });

  it('says so when the full image cannot be loaded', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: 'artifact not found' }) });
    render(<ImageThumbnails artifactId="a-1" images={images} />);

    fireEvent.click(screen.getByRole('button', { name: /open picture/i }));

    await waitFor(() => expect(screen.getByText(/could not load the full image/i)).toBeInTheDocument());
  });

  it('finds images under keys that contain dots', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ payload: { views: { 'front.view': { url: 'data:image/png;base64,RlJPTlQ=' } } } }),
    });
    render(<ImageThumbnails artifactId="a-1" images={images} />);

    fireEvent.click(screen.getByRole('button', { name: /open views\.front\.view/i }));

    await waitFor(() =>
      expect(screen.getByAltText('views.front.view (full size)')).toHaveAttribute(
        'src',
        'data:image/png;base64,RlJPTlQ='
      )
    );
  });

  it('behaves as a modal dialog: focus, Tab, Escape and focus return', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ payload: { picture: { url: 'data:image/jpeg;base64,RlVMTA==' } } }),
    });
    render(<ImageThumbnails artifactId="a-1" images={images} />);
    const opener = screen.getByRole('button', { name: /open picture/i });
    opener.focus();

    fireEvent.click(opener);

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    const close = screen.getByRole('button', { name: /close/i });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: 'Tab' });
    expect(close).toHaveFocus();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});
