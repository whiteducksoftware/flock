import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ImageThumbnails from './ImageThumbnails';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const images = [
  { path: 'picture', mime: 'image/jpeg', bytes: 42 * 1024, thumb: 'data:image/jpeg;base64,VEhVTUI=' },
  { path: 'pages[1]', mime: 'image/png', bytes: 2048, thumb: 'data:image/png;base64,UEFHRQ==' },
];

describe('ImageThumbnails', () => {
  beforeEach(() => {
    mockFetch.mockReset();
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
});
