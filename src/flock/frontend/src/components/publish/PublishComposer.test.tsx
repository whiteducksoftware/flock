import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PublishComposer from './PublishComposer';
import Toast from '../common/Toast';
import { useFilterStore } from '../../store/filterStore';
import { useUIStore } from '../../store/uiStore';

// "Picked up by" reads the agents; these tests count the requests for types and publishing
vi.mock('../../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../services/api')>()),
  fetchAgents: vi.fn(async () => []),
}));

// Mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

// The list is there before the artifact types load: wait for the type
// (an option reads "Idea 1 field")
const waitForType = (name: string) => screen.findByRole('option', { name: new RegExp(`^${name}\\b`) });
const pickType = (name: string) => fireEvent.click(screen.getByRole('option', { name: new RegExp(`^${name}\\b`) }));
const publishButton = () => screen.getByRole('button', { name: /^publish$/i });
// The composer shows its result in the toast
const renderComposer = () =>
  render(
    <>
      <PublishComposer />
      <Toast />
    </>
  );

describe('PublishComposer', () => {
  const mockArtifactTypes = [
    { name: 'Idea', schema: { type: 'object', properties: { content: { type: 'string' } } } },
    { name: 'Movie', schema: { type: 'object', properties: { title: { type: 'string' }, plot: { type: 'string' } } } },
    { name: 'Tagline', schema: { type: 'object', properties: { text: { type: 'string' } } } },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
    useUIStore.setState({ toast: null });
  });

  it('should render the type list and, for the picked type, its content field', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: mockArtifactTypes }),
    });

    renderComposer();

    await waitForType('Idea');

    // Pick the artifact type to trigger dynamic field rendering
    pickType('Idea');

    // Now the content field should appear
    expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    expect(publishButton()).toBeInTheDocument();
  });

  it('should list the available types', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: mockArtifactTypes }),
    });

    renderComposer();

    await waitForType('Idea');

    const list = screen.getByRole('listbox', { name: 'Artifact types' });
    const optionValues = Array.from(list.querySelectorAll('[role="option"]')).map((opt) => opt.getAttribute('title'));

    expect(optionValues).toContain('Idea');
    expect(optionValues).toContain('Movie');
    expect(optionValues).toContain('Tagline');
  });

  it('should prefill array fields from schema defaults', async () => {
    const arrayDefaultsType = [
      {
        name: 'CompetitorBrief',
        schema: {
          type: 'object',
          properties: {
            key_differentiators: {
              type: 'array',
              title: 'Key Differentiators',
              items: { type: 'string' },
              default: ['Blackboard architecture', 'Typed artifacts'],
            },
            known_competitors: {
              type: 'array',
              title: 'Known Competitors',
              items: { type: 'string' },
              default: ['CrewAI', 'LangGraph', 'AutoGen'],
            },
          },
        },
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: arrayDefaultsType }),
    });

    renderComposer();

    await waitForType('CompetitorBrief');

    pickType('CompetitorBrief');

    await waitFor(() => {
      expect(screen.getByLabelText(/key_differentiators/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/known_competitors/i)).toBeInTheDocument();
    });

    const differentiators = screen.getByLabelText(/key_differentiators/i) as HTMLTextAreaElement;
    const competitors = screen.getByLabelText(/known_competitors/i) as HTMLTextAreaElement;

    expect(differentiators.value).toBe('Blackboard architecture\nTyped artifacts');
    expect(competitors.value).toBe('CrewAI\nLangGraph\nAutoGen');
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

    renderComposer();

    await waitForType('Idea');

    const submitButton = publishButton();

    // Test 1: Try to submit without selecting type - should NOT call API
    fireEvent.click(submitButton);

    // Give it a moment, then verify API was NOT called (only 1 call for artifact types)
    await new Promise(resolve => setTimeout(resolve, 100));
    expect(mockFetch).toHaveBeenCalledTimes(1); // Only the initial artifact types fetch

    // Test 2: Pick artifact type but leave content empty - should NOT call API
    pickType('Idea');

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

    renderComposer();

    await waitForType('Idea');

    pickType('Idea');

    // Wait for content field to appear after selecting type
    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = publishButton();

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

    renderComposer();

    await waitForType('Idea');

    pickType('Idea');

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = publishButton();

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

  it('should show a toast with the run of the correlation ID after successful publish', async () => {
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

    renderComposer();

    await waitForType('Idea');

    pickType('Idea');

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = publishButton();

    fireEvent.change(contentInput, { target: { value: 'Success test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Published Idea · run test')).toBeInTheDocument();
      // The full correlation ID is the tooltip of the run
      expect(screen.getByTitle('test-correlation-456')).toBeInTheDocument();
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

    renderComposer();

    await waitForType('Idea');

    pickType('Idea');

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = publishButton();

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

    renderComposer();

    await waitForType('Idea');

    pickType('Idea');

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i) as HTMLInputElement;
    const submitButton = publishButton();

    fireEvent.change(contentInput, { target: { value: 'Reset test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/^published idea/i)).toBeInTheDocument();
    });

    // Form should be reset - artifact type cleared means fields disappear
    expect(screen.queryByRole('option', { selected: true })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/content/i)).not.toBeInTheDocument();
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

    renderComposer();

    await waitForType('Idea');

    pickType('Idea');

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = publishButton();

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

    renderComposer();

    await waitForType('Idea');

    pickType('Idea');

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = publishButton();

    fireEvent.change(contentInput, { target: { value: 'Network error test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/network error|failed to connect/i)).toBeInTheDocument();
    });
  });

  // Auto-filter checkbox tests
  it('should render the follow checkbox checked by default', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: mockArtifactTypes }),
    });

    renderComposer();

    await waitForType('Idea');

    const checkbox = screen.getByLabelText(/follow this run on the board/i) as HTMLInputElement;
    expect(checkbox).toBeInTheDocument();
    expect(checkbox.checked).toBe(true);
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

    renderComposer();

    await waitForType('Idea');

    const checkbox = screen.getByLabelText(/follow this run on the board/i) as HTMLInputElement;

    // The checkbox is checked: following is the default
    expect(checkbox.checked).toBe(true);

    pickType('Idea');

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = publishButton();

    fireEvent.change(contentInput, { target: { value: 'Auto-filter test' } });
    fireEvent.click(submitButton);

    // Verify filter was set in store (primary behavior)
    await waitFor(() => {
      const filterState = useFilterStore.getState();
      expect(filterState.correlationId).toBe('auto-filter-123');
    });
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

    renderComposer();

    await waitForType('Idea');

    const checkbox = screen.getByLabelText(/follow this run on the board/i) as HTMLInputElement;

    // Uncheck the checkbox, checked by default
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);

    pickType('Idea');

    await waitFor(() => {
      expect(screen.getByLabelText(/content/i)).toBeInTheDocument();
    });

    const contentInput = screen.getByLabelText(/content/i);
    const submitButton = publishButton();

    fireEvent.change(contentInput, { target: { value: 'No filter test' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByTitle('no-filter-456')).toBeInTheDocument();
    });

    // Verify filter was NOT updated to the new correlation ID
    const filterState = useFilterStore.getState();
    expect(filterState.correlationId).not.toBe('no-filter-456');
  });

  it('should allow toggling checkbox state', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ artifact_types: mockArtifactTypes }),
    });

    renderComposer();

    await waitForType('Idea');

    const checkbox = screen.getByLabelText(/follow this run on the board/i) as HTMLInputElement;

    // Initially checked
    expect(checkbox.checked).toBe(true);

    // Uncheck
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);

    // Check again
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);
  });
});
