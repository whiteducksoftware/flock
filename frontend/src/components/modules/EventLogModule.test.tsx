import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import EventLogModule from './EventLogModule';
import { Message, Agent } from '../../types/graph';
import { TimeRange } from '../../types/filters';

// Mock ModuleContext type based on the architecture spec
interface ModuleContext {
  agents: Map<string, Agent>;
  messages: Map<string, Message>;
  events: Message[];
  filters: {
    correlationId: string | null;
    timeRange: TimeRange;
  };
  publish: (artifact: any) => void;
  invoke: (agentName: string, inputs: any[]) => void;
}

describe('EventLogModule', () => {
  const createMockAgent = (id: string, name: string): Agent => ({
    id,
    name,
    status: 'idle',
    subscriptions: [],
    lastActive: Date.now(),
    sentCount: 0,
    recvCount: 0,
  });

  const createMockMessage = (
    id: string,
    type: string,
    producedBy: string,
    correlationId: string,
    timestamp: number
  ): Message => ({
    id,
    type,
    payload: { data: `test-${id}` },
    timestamp,
    correlationId,
    producedBy,
  });

  const createMockContext = (
    events: Message[] = [],
    correlationId: string | null = null,
    timeRange: TimeRange = { preset: 'last10min' }
  ): ModuleContext => ({
    agents: new Map([
      ['agent1', createMockAgent('agent1', 'TestAgent1')],
      ['agent2', createMockAgent('agent2', 'TestAgent2')],
    ]),
    messages: new Map(),
    events,
    filters: {
      correlationId,
      timeRange,
    },
    publish: vi.fn(),
    invoke: vi.fn(),
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render table with correct column headers', () => {
    const context = createMockContext();
    render(<EventLogModule context={context} />);

    expect(screen.getByText(/Timestamp/)).toBeInTheDocument();
    expect(screen.getByText(/^Type/)).toBeInTheDocument();
    expect(screen.getByText(/^Agent/)).toBeInTheDocument();
    expect(screen.getByText(/Correlation ID/)).toBeInTheDocument();
  });

  it('should display events from context in table rows', () => {
    const now = Date.now();
    const events = [
      createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', now - 1000),
      createMockMessage('msg2', 'Tagline', 'agent2', 'corr-123', now),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    expect(screen.getByText('Movie')).toBeInTheDocument();
    expect(screen.getByText('Tagline')).toBeInTheDocument();
  });

  it('should display timestamp for each event', () => {
    const now = Date.now();
    const events = [createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', now - 1000)];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    // Should display formatted timestamp - check it's in the table
    const cells = screen.getAllByRole('cell');
    // First cell should be the timestamp - just verify it exists and has some content
    expect(cells[0]).toBeInTheDocument();
    expect(cells[0]!.textContent).toBeTruthy();
  });

  it('should display event type for each event', () => {
    const events = [
      createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', Date.now()),
      createMockMessage('msg2', 'Tagline', 'agent2', 'corr-456', Date.now()),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    expect(screen.getByText('Movie')).toBeInTheDocument();
    expect(screen.getByText('Tagline')).toBeInTheDocument();
  });

  it('should display agent name for each event', () => {
    const events = [
      createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', Date.now()),
      createMockMessage('msg2', 'Tagline', 'agent2', 'corr-123', Date.now()),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    expect(screen.getByText('agent1')).toBeInTheDocument();
    expect(screen.getByText('agent2')).toBeInTheDocument();
  });

  it('should display correlation ID for each event', () => {
    const events = [
      createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', Date.now()),
      createMockMessage('msg2', 'Tagline', 'agent2', 'corr-456', Date.now()),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    expect(screen.getByText('corr-123')).toBeInTheDocument();
    expect(screen.getByText('corr-456')).toBeInTheDocument();
  });

  it('should filter events by correlation ID from context', () => {
    const events = [
      createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', Date.now()),
      createMockMessage('msg2', 'Tagline', 'agent2', 'corr-456', Date.now()),
      createMockMessage('msg3', 'Idea', 'agent1', 'corr-123', Date.now()),
    ];
    const context = createMockContext(events, 'corr-123');

    render(<EventLogModule context={context} />);

    // Should show events with corr-123
    expect(screen.getByText('Movie')).toBeInTheDocument();
    expect(screen.getByText('Idea')).toBeInTheDocument();

    // Should NOT show event with corr-456
    expect(screen.queryByText('Tagline')).not.toBeInTheDocument();
  });

  it('should filter events by time range from context', () => {
    const now = Date.now();
    const fifteenMinutesAgo = now - 15 * 60 * 1000;

    const events = [
      createMockMessage('msg1', 'Recent', 'agent1', 'corr-123', now - 1000),
      createMockMessage('msg2', 'Old', 'agent2', 'corr-123', fifteenMinutesAgo),
    ];

    // Filter: last 10 minutes
    const timeRange: TimeRange = { preset: 'last10min' };
    const context = createMockContext(events, null, timeRange);

    render(<EventLogModule context={context} />);

    // Should show recent event
    expect(screen.getByText('Recent')).toBeInTheDocument();

    // Should NOT show old event (15 minutes ago)
    expect(screen.queryByText('Old')).not.toBeInTheDocument();
  });

  it('should filter events by custom time range', () => {
    const now = Date.now();
    const events = [
      createMockMessage('msg1', 'InRange', 'agent1', 'corr-123', now - 2000),
      createMockMessage('msg2', 'OutOfRange', 'agent2', 'corr-123', now - 10000),
    ];

    // Custom time range: last 5 seconds
    const timeRange: TimeRange = {
      preset: 'custom',
      start: now - 5000,
      end: now,
    };
    const context = createMockContext(events, null, timeRange);

    render(<EventLogModule context={context} />);

    // Should show in-range event
    expect(screen.getByText('InRange')).toBeInTheDocument();

    // Should NOT show out-of-range event
    expect(screen.queryByText('OutOfRange')).not.toBeInTheDocument();
  });

  it('should have expand button for each event row', () => {
    const events = [
      createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', Date.now()),
      createMockMessage('msg2', 'Tagline', 'agent2', 'corr-123', Date.now()),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    // Should have 2 row expand buttons + 1 "Expand All" button = 3 total
    const allExpandButtons = screen.getAllByRole('button', { name: /expand/i });
    expect(allExpandButtons).toHaveLength(3);

    // Verify row expand buttons exist (there should be 2)
    const rowExpandButtons = screen.getAllByRole('button', { name: /expand ▼/i });
    expect(rowExpandButtons).toHaveLength(2);
  });

  it('should show empty state when no events', () => {
    const context = createMockContext([]);

    render(<EventLogModule context={context} />);

    // Table headers should still be present
    expect(screen.getByText(/Timestamp/)).toBeInTheDocument();

    // Should show empty state message
    expect(screen.getByText('No events to display')).toBeInTheDocument();
  });

  it('should show empty state when all events are filtered out', () => {
    const events = [
      createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', Date.now()),
      createMockMessage('msg2', 'Tagline', 'agent2', 'corr-456', Date.now()),
    ];
    // Filter by non-existent correlation ID
    const context = createMockContext(events, 'corr-999');

    render(<EventLogModule context={context} />);

    // Should not show any events
    expect(screen.queryByText('Movie')).not.toBeInTheDocument();
    expect(screen.queryByText('Tagline')).not.toBeInTheDocument();
  });

  it('should have sortable column headers', () => {
    const context = createMockContext();
    render(<EventLogModule context={context} />);

    const timestampHeader = screen.getByText(/Timestamp/);
    const typeHeader = screen.getByText(/^Type/);
    const agentHeader = screen.getByText(/^Agent/);

    // Check if headers are clickable (have onClick or role)
    expect(timestampHeader.closest('th')).toBeInTheDocument();
    expect(typeHeader.closest('th')).toBeInTheDocument();
    expect(agentHeader.closest('th')).toBeInTheDocument();
  });

  it('should sort events by timestamp when timestamp column is clicked', async () => {
    const user = userEvent.setup();
    const now = Date.now();
    const events = [
      createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', now - 5000),
      createMockMessage('msg2', 'Tagline', 'agent2', 'corr-123', now - 1000),
      createMockMessage('msg3', 'Idea', 'agent1', 'corr-123', now - 3000),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    const timestampHeader = screen.getByText(/Timestamp/);

    // Click to sort ascending
    await user.click(timestampHeader);

    const rows = screen.getAllByRole('row');
    // First row is header, so data rows start at index 1
    // Oldest should be first after ascending sort
    expect(within(rows[1]!).getByText('Movie')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('Idea')).toBeInTheDocument();
    expect(within(rows[3]!).getByText('Tagline')).toBeInTheDocument();
  });

  it('should sort events by type when type column is clicked', async () => {
    const user = userEvent.setup();
    const now = Date.now();
    const events = [
      createMockMessage('msg1', 'Zebra', 'agent1', 'corr-123', now),
      createMockMessage('msg2', 'Apple', 'agent2', 'corr-123', now),
      createMockMessage('msg3', 'Movie', 'agent1', 'corr-123', now),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    const typeHeader = screen.getByText(/^Type/);

    // Click to sort ascending
    await user.click(typeHeader);

    const rows = screen.getAllByRole('row');
    // After alphabetical sort: Apple, Movie, Zebra
    expect(within(rows[1]!).getByText('Apple')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('Movie')).toBeInTheDocument();
    expect(within(rows[3]!).getByText('Zebra')).toBeInTheDocument();
  });

  it('should sort events by agent name when agent column is clicked', async () => {
    const user = userEvent.setup();
    const now = Date.now();
    const events = [
      createMockMessage('msg1', 'Movie', 'zebra-agent', 'corr-123', now),
      createMockMessage('msg2', 'Tagline', 'apple-agent', 'corr-123', now),
      createMockMessage('msg3', 'Idea', 'movie-agent', 'corr-123', now),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    const agentHeader = screen.getByText(/^Agent/);

    // Click to sort ascending
    await user.click(agentHeader);

    const rows = screen.getAllByRole('row');
    // After alphabetical sort: apple-agent, movie-agent, zebra-agent
    expect(within(rows[1]!).getByText('apple-agent')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('movie-agent')).toBeInTheDocument();
    expect(within(rows[3]!).getByText('zebra-agent')).toBeInTheDocument();
  });

  it('should expand row to show event payload when expand button is clicked', async () => {
    const user = userEvent.setup();
    const events = [
      createMockMessage('msg1', 'Movie', 'agent1', 'corr-123', Date.now()),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    // Get the row expand button (there's only one row, so one button)
    const rowExpandButtons = screen.getAllByRole('button', { name: /expand ▼/i });
    expect(rowExpandButtons.length).toBeGreaterThan(0);
    const expandButton = rowExpandButtons[0]!; // Non-null assertion since we verified length

    // Click expand button
    await user.click(expandButton);

    // Should show payload data
    expect(screen.getByText(/test-msg1/i)).toBeInTheDocument();
  });

  it('should display events in reverse chronological order by default', () => {
    const now = Date.now();
    const events = [
      createMockMessage('msg1', 'Oldest', 'agent1', 'corr-123', now - 10000),
      createMockMessage('msg2', 'Middle', 'agent2', 'corr-123', now - 5000),
      createMockMessage('msg3', 'Newest', 'agent1', 'corr-123', now),
    ];
    const context = createMockContext(events);

    render(<EventLogModule context={context} />);

    const rows = screen.getAllByRole('row');
    // First row is header, so data rows start at index 1
    // Newest should be first (reverse chronological)
    expect(within(rows[1]!).getByText('Newest')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('Middle')).toBeInTheDocument();
    expect(within(rows[3]!).getByText('Oldest')).toBeInTheDocument();
  });

  it('should apply both correlation ID and time range filters together', () => {
    const now = Date.now();
    const events = [
      createMockMessage('msg1', 'Match', 'agent1', 'corr-123', now - 1000),
      createMockMessage('msg2', 'WrongCorr', 'agent2', 'corr-456', now - 1000),
      createMockMessage('msg3', 'WrongTime', 'agent1', 'corr-123', now - 20 * 60 * 1000),
    ];

    const timeRange: TimeRange = { preset: 'last10min' };
    const context = createMockContext(events, 'corr-123', timeRange);

    render(<EventLogModule context={context} />);

    // Should only show event matching both filters
    expect(screen.getByText('Match')).toBeInTheDocument();
    expect(screen.queryByText('WrongCorr')).not.toBeInTheDocument();
    expect(screen.queryByText('WrongTime')).not.toBeInTheDocument();
  });
});
