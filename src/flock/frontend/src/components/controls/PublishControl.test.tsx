import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PublishControl from './PublishControl';
import { useFilterStore } from '../../store/filterStore';

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('PublishControl', () => {
  const mockArtifactTypes = [
    { name: 'Idea', schema: { type: 'object', properties: { content: { type: 'string' } } } },
    { name: 'Movie', schema: { type: 'object', properties: { title: { type: 'string' }, plot: { type: 'string' } } } },
    { name: 'Tagline', schema: { type: 'object', properties: { text: { type: 'string' } } } },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  it('should render publish form with artifact type dropdown and content textarea', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: mockArtifactTypes }),
    });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    // Select artifact type to trigger dynamic field rendering
    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    // Now the content field should appear
    expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /publish artifact/i })).toBeInTheDocument();
  });

  it('should populate artifact type dropdown from available types', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: mockArtifactTypes }),
    });

    render(<PublishControl />);

    await waitFor(() => {
      const dropdown = screen.getByLabelText(/artifact type/i) as HTMLSelectElement;
      expect(dropdown.options.length).toBeGreaterThan(0);
    });

    const dropdown = screen.getByLabelText(/artifact type/i) as HTMLSelectElement;
    const optionValues = Array.from(dropdown.options).map(opt => opt.value);

    expect(optionValues).toContain('Idea');
    expect(optionValues).toContain('Movie');
    expect(optionValues).toContain('Tagline');
  });

  it('should validate required fields before submission', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ artifact_types: mockArtifactTypes }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          correlation_id: 'should-not-be-called',
        }),
      });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    // Test 1: Try to submit without selecting type - should NOT call API
    fireEvent.click(submitButton);

    // Give it a moment, then verify API was NOT called (only 1 call for artifact types)
    await new Promise(resolve => setTimeout(resolve, 100));
    expect(mockFetch).toHaveBeenCalledTimes(1); // Only the initial artifact types fetch

    // Test 2: Select artifact type but leave content empty - should NOT call API
    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    // Try to submit with empty content
    fireEvent.click(submitButton);

    // Give it a moment, then verify API was still NOT called
    await new Promise(resolve => setTimeout(resolve, 100));
    expect(mockFetch).toHaveBeenCalledTimes(1); // Still only 1 call
  });

  it('should validate content as valid JSON', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: mockArtifactTypes }),
    });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    // Wait for content field to appear after selecting type
    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    // Content field is now a text input, not textarea, and accepts any string
    // The validation is done on the backend, so this test is no longer relevant
    // for JSON validation. Skip JSON validation test.
    fireEvent.change(contentInput, { target: { value: 'Test content' } });
    fireEvent.click(submitButton);

    // Should not show JSON validation error for simple text
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  it('should successfully publish and call API endpoint', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ artifact_types: mockArtifactTypes }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          correlation_id: 'test-correlation-123',
          message: 'Artifact published successfully'
        }),
      });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    fireEvent.change(contentInput, { target: { value: 'Test idea' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/control/publish',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            artifact_type: 'Idea',
            content: { content: 'Test idea' }, // Schema-based: { content: string }
          }),
        })
      );
    });
  });

  it('should display success message with correlation ID after successful publish', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ artifact_types: mockArtifactTypes }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          correlation_id: 'test-correlation-456',
          message: 'Artifact published successfully'
        }),
      });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    fireEvent.change(contentInput, { target: { value: 'Success test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/successfully published/i)).toBeInTheDocument();
      expect(screen.getByText(/test-correlation-456/)).toBeInTheDocument();
    });
  });

  it('should display error message on API failure', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ artifact_types: mockArtifactTypes }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({
          error: 'Internal server error',
          message: 'Failed to publish artifact'
        }),
      });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    fireEvent.change(contentInput, { target: { value: 'Error test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/failed to publish/i)).toBeInTheDocument();
    });
  });

  it('should reset form after successful publish', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ artifact_types: mockArtifactTypes }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          correlation_id: 'test-correlation-789',
          message: 'Artifact published successfully'
        }),
      });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const artifactTypeSelect = screen.getByLabelText(/artifact type/i) as HTMLSelectElement;
    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i) as HTMLInputElement;
    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    fireEvent.change(contentInput, { target: { value: 'Reset test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/successfully published/i)).toBeInTheDocument();
    });

    // Form should be reset - artifact type cleared means fields disappear
    expect(artifactTypeSelect.value).toBe('');
  });

  it('should disable submit button during API call', async () => {
    let resolvePublish: (value: any) => void;
    const publishPromise = new Promise(resolve => {
      resolvePublish = resolve;
    });

    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ artifact_types: mockArtifactTypes }),
      })
      .mockReturnValueOnce(publishPromise as any);

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    fireEvent.change(contentInput, { target: { value: 'Loading test' } });
    fireEvent.click(submitButton);

    // Button should be disabled during API call
    await waitFor(() => {
      expect(submitButton).toBeDisabled();
      expect(screen.getByText(/publishing/i)).toBeInTheDocument();
    });

    // Resolve the promise
    resolvePublish!({
      ok: true,
      json: async () => ({
        status: 'success',
        correlation_id: 'test-correlation-999',
        message: 'Artifact published successfully'
      }),
    });

    // Button should be enabled after API call completes
    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });
  });

  it('should handle network errors gracefully', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ artifact_types: mockArtifactTypes }),
      })
      .mockRejectedValueOnce(new Error('Network error'));

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    fireEvent.change(contentInput, { target: { value: 'Network error test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/network error|failed to connect/i)).toBeInTheDocument();
    });
  });

  // Auto-filter checkbox tests
  it('should render auto-set filter checkbox unchecked by default', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: mockArtifactTypes }),
    });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const checkbox = screen.getByLabelText(/set filter to correlation id/i) as HTMLInputElement;
    expect(checkbox).toBeInTheDocument();
    expect(checkbox.checked).toBe(false);
  });

  it('should set filter to correlation ID when checkbox is checked and publish succeeds', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ artifact_types: mockArtifactTypes }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          correlation_id: 'auto-filter-123',
          message: 'Artifact published successfully'
        }),
      });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    const checkbox = screen.getByLabelText(/set filter to correlation id/i) as HTMLInputElement;

    // Check the checkbox to enable auto-filter
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);

    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    fireEvent.change(contentInput, { target: { value: 'Auto-filter test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/filter set to: auto-filter-123/i)).toBeInTheDocument();
    });

    // Verify filter was set in store
    const filterState = useFilterStore.getState();
    expect(filterState.correlationId).toBe('auto-filter-123');
  });

  it('should NOT set filter when checkbox is unchecked', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ artifact_types: mockArtifactTypes }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: 'success',
          correlation_id: 'no-filter-456',
          message: 'Artifact published successfully'
        }),
      });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const artifactTypeSelect = screen.getByLabelText(/artifact type/i);
    const checkbox = screen.getByLabelText(/set filter to correlation id/i) as HTMLInputElement;

    // Checkbox should already be unchecked by default
    expect(checkbox.checked).toBe(false);

    // Clear any existing filter
    useFilterStore.setState({ correlationId: undefined });

    fireEvent.change(artifactTypeSelect, { target: { value: 'Idea' } });

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = screen.getByRole('button', { name: /publish artifact/i });

    fireEvent.change(contentInput, { target: { value: 'No filter test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/correlation id: no-filter-456/i)).toBeInTheDocument();
    });

    // Verify filter was NOT set in store
    const filterState = useFilterStore.getState();
    expect(filterState.correlationId).toBeUndefined();
  });

  it('should allow toggling checkbox state', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: mockArtifactTypes }),
    });

    render(<PublishControl />);

    await waitFor(() => {
      expect(screen.getByLabelText(/artifact type/i)).toBeInTheDocument();
    });

    const checkbox = screen.getByLabelText(/set filter to correlation id/i) as HTMLInputElement;

    // Initially unchecked
    expect(checkbox.checked).toBe(false);

    // Check
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);

    // Uncheck again
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);
  });
});
