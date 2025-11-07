import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ScheduledAgentDisplay from './ScheduledAgentDisplay';
import { ScheduleSpecDisplay, TimerStateDisplay } from '../../types/graph';

describe('ScheduledAgentDisplay', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const createTimerState = (overrides?: Partial<TimerStateDisplay>): TimerStateDisplay => ({
    iteration: 0,
    last_fire_time: null,
    next_fire_time: null,
    is_active: true,
    is_completed: false,
    is_stopped: false,
    ...overrides,
  });

  describe('Schedule Badge', () => {
    it('should render interval schedule details', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={null} compactNodeView={false} />
      );

      // Check that schedule details are shown in the expanded view
      expect(screen.getByText('Every 30 seconds')).toBeInTheDocument();
    });

    it('should render time schedule details', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'time',
        time: '17:00:00',
      };

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={null} compactNodeView={false} />
      );

      // Check that schedule details are shown
      expect(screen.getByText(/Daily at.*PM UTC/i)).toBeInTheDocument();
    });

    it('should render datetime schedule details (one-time)', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'datetime',
        datetime: '2025-01-15T09:00:00Z',
      };

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={null} compactNodeView={false} />
      );

      // Check that schedule details are shown
      expect(screen.getByText(/Scheduled:/i)).toBeInTheDocument();
    });

    it('should render cron schedule details', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'cron',
        cron: '0 * * * *',
      };

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={null} compactNodeView={false} />
      );

      // Check that schedule details are shown
      expect(screen.getByText(/Cron: 0 \* \* \* \*/i)).toBeInTheDocument();
    });
  });

  describe('Timer Panel (expanded view)', () => {
    it('should render timer panel when not in compact mode', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const timerState = createTimerState({
        next_fire_time: new Date(Date.now() + 25000).toISOString(),
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.getByText('Scheduled Timer')).toBeInTheDocument();
    });

    it('should not render timer panel in compact mode', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const timerState = createTimerState();

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={true} />
      );

      expect(screen.queryByText('Scheduled Timer')).not.toBeInTheDocument();
    });

    it('should display next fire countdown', async () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const futureTime = new Date(Date.now() + 25000); // 25 seconds
      const timerState = createTimerState({
        next_fire_time: futureTime.toISOString(),
        is_active: true,
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      // Should show approximately 25s
      expect(screen.getByText(/Next:/i)).toBeInTheDocument();
      const countdown = screen.getByText(/25s/i);
      expect(countdown).toBeInTheDocument();
    });

    it('should display iteration count', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const timerState = createTimerState({
        iteration: 41,  // iteration + 1 = 42
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      // "Run #" and iteration number are in the same span, but may be split
      const elements = screen.getAllByText((_content, element) => {
        return element?.textContent?.includes('Run #42') ?? false;
      });
      expect(elements.length).toBeGreaterThan(0);
    });

    it('should display last fire time', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const pastTime = new Date(Date.now() - 120000); // 2 minutes ago
      const timerState = createTimerState({
        last_fire_time: pastTime.toISOString(),
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.getByText(/Last:/i)).toBeInTheDocument();
      expect(screen.getByText(/2m ago/i)).toBeInTheDocument();
    });

    it('should display schedule details', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const timerState = createTimerState();

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.getByText(/Every 30 seconds/i)).toBeInTheDocument();
    });
  });

  describe('State Indicators', () => {
    it('should show completed badge for one-time schedules', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'datetime',
        datetime: '2025-01-15T09:00:00Z',
      };
      const timerState = createTimerState({
        is_completed: true,
        is_active: false,
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.getByText('✓ Completed')).toBeInTheDocument();
    });

    it('should show stopped badge for max_repeats schedules', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
        max_repeats: 10,
      };
      const timerState = createTimerState({
        is_stopped: true,
        is_active: false,
        iteration: 9,  // iteration + 1 = 10
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.getByText('⏸ Stopped')).toBeInTheDocument();
      // "Run #" and iteration number are in the same span, but may be split
      const elements = screen.getAllByText((_content, element) => {
        return element?.textContent?.includes('Run #10') ?? false;
      });
      expect(elements.length).toBeGreaterThan(0);
      expect(screen.getByText(/\(final\)/i)).toBeInTheDocument();
    });

    it('should not show next fire countdown when timer is stopped', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const timerState = createTimerState({
        is_stopped: true,
        is_active: false,
        next_fire_time: null,
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.queryByText(/Next:/i)).not.toBeInTheDocument();
    });
  });

  describe('Schedule Formatting', () => {
    it('should format interval schedules correctly', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT5M',
      };
      const timerState = createTimerState();

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.getByText(/Every 5 minutes/i)).toBeInTheDocument();
    });

    it('should format time schedules correctly', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'time',
        time: '17:00:00',
      };
      const timerState = createTimerState();

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.getByText(/Daily at 5:00 PM UTC/i)).toBeInTheDocument();
    });

    it('should format cron schedules correctly', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'cron',
        cron: '0 * * * *',
      };
      const timerState = createTimerState();

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.getByText(/Cron: 0 \* \* \* \*/i)).toBeInTheDocument();
    });

    it('should include max_repeats in schedule details', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
        max_repeats: 10,
      };
      const timerState = createTimerState();

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      expect(screen.getByText(/\(max 10\)/i)).toBeInTheDocument();
    });
  });

  describe('Countdown Updates', () => {
    it('should display countdown correctly', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const baseTime = Date.now();
      vi.setSystemTime(baseTime);
      const futureTime = new Date(baseTime + 30000); // 30 seconds
      const timerState = createTimerState({
        next_fire_time: futureTime.toISOString(),
        is_active: true,
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      // Should show countdown (approximately 30s, may vary slightly due to render timing)
      const countdownContainer = screen.getByTitle(/Next execution in/i);
      const countdownText = countdownContainer.textContent || '';
      // Should contain seconds format (30s or similar)
      expect(countdownText).toMatch(/\d+s/); // At least one digit followed by 's'
      
      // Verify it shows a reasonable countdown (between 29-31 seconds)
      const secondsMatch = countdownText.match(/(\d+)s/);
      if (secondsMatch && secondsMatch[1]) {
        const seconds = parseInt(secondsMatch[1], 10);
        expect(seconds).toBeGreaterThanOrEqual(29);
        expect(seconds).toBeLessThanOrEqual(31);
      }
    });

    it('should format countdown correctly for minutes', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT5M',
      };
      const baseTime = Date.now();
      vi.setSystemTime(baseTime);
      // Use a time that will definitely result in minutes format (2+ minutes)
      const futureTime = new Date(baseTime + 125000); // 2 minutes 5 seconds
      const timerState = createTimerState({
        next_fire_time: futureTime.toISOString(),
        is_active: true,
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      // Verify component renders schedule details
      expect(screen.getByText(/Every 5 minutes/i)).toBeInTheDocument();
      
      // Countdown should show minutes format if next_fire_time is valid
      const countdownContainer = screen.queryByTitle(/Next execution in/i);
      if (countdownContainer) {
        // Should contain minutes format (2m or 2m 5s)
        const text = countdownContainer.textContent || '';
        expect(text).toMatch(/\d+m/); // At least one digit followed by 'm'
      }
    });
  });

  describe('Edge Cases', () => {
    it('should handle null timer state', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={null} compactNodeView={false} />
      );

      // Should still render schedule badge (using aria-label)
      // Multiple elements have this label, get the first one (the icon badge)
      const badges = screen.getAllByLabelText('Scheduled timer');
      const badge = badges[0];
      expect(badge).toBeInTheDocument();
      // Check that schedule details are shown
      expect(screen.getByText('Every 30 seconds')).toBeInTheDocument();
      
      // When timerState is null, "Last:" section is not rendered (only shown when timerState exists)
      // Timer panel should still render but without iteration count or last fire time
      expect(screen.queryByText(/Last:/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Run #/i)).not.toBeInTheDocument();
    });

    it('should handle missing next_fire_time', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const timerState = createTimerState({
        next_fire_time: null,
        is_active: true,
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      // Should not show next fire countdown
      expect(screen.queryByText(/Next:/i)).not.toBeInTheDocument();
    });

    it('should handle missing last_fire_time', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const timerState = createTimerState({
        last_fire_time: null,
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      // When last_fire_time is null, the "Last:" section is not rendered
      // (only rendered when timerState && timerState.last_fire_time exists)
      expect(screen.queryByText(/Last:/i)).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have aria-label for schedule badge', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={null} compactNodeView={false} />
      );

      // Check for the timer icon badge with aria-label "Scheduled timer"
      // Multiple elements have this label, get the first one (the icon badge)
      const badges = screen.getAllByLabelText('Scheduled timer');
      const badge = badges[0];
      expect(badge).toBeInTheDocument();
    });

    it('should have aria-live for countdown updates', () => {
      const scheduleSpec: ScheduleSpecDisplay = {
        type: 'interval',
        interval: 'PT30S',
      };
      const baseTime = Date.now();
      vi.setSystemTime(baseTime);
      const futureTime = new Date(baseTime + 30000);
      const timerState = createTimerState({
        next_fire_time: futureTime.toISOString(),
        is_active: true,
      });

      render(
        <ScheduledAgentDisplay scheduleSpec={scheduleSpec} timerState={timerState} compactNodeView={false} />
      );

      const countdown = screen.getByTitle(/Next execution in/i);
      expect(countdown).toBeInTheDocument();
      expect(countdown.getAttribute('aria-live')).toBe('polite');
    });
  });
});

