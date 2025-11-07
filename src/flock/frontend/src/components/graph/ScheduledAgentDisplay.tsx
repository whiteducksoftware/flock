import { memo, useState, useEffect } from 'react';
import { ScheduleSpecDisplay, TimerStateDisplay } from '../../types/graph';

interface ScheduledAgentDisplayProps {
  scheduleSpec: ScheduleSpecDisplay;
  timerState: TimerStateDisplay | null;
  compactNodeView?: boolean;
}

/**
 * Phase 1.6: Scheduled Agents Visualization
 *
 * Displays timer-based scheduled agent information in agent nodes:
 * - Schedule badge (compact indicator)
 * - Timer countdown to next execution
 * - Iteration count
 * - Last fire time
 * - Schedule details
 *
 * Enhanced with:
 * - Client-side timer countdown for real-time updates
 * - Schedule formatting for different types (interval, time, datetime, cron)
 * - State handling (active, completed, stopped)
 * - Accessibility attributes
 */
const ScheduledAgentDisplay = memo(({ scheduleSpec, timerState, compactNodeView = false }: ScheduledAgentDisplayProps) => {
  const [clientTime, setClientTime] = useState(Date.now());

  // Client-side timer: Update every second for real-time countdown
  useEffect(() => {
    const interval = setInterval(() => {
      setClientTime(Date.now());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Calculate next fire countdown
  const calculateNextFireCountdown = (nextFireTime: string | null): string | null => {
    if (!nextFireTime) return null;

    try {
      const next = new Date(nextFireTime).getTime();
      const remaining = Math.max(0, Math.floor((next - clientTime) / 1000));

      if (remaining < 60) return `${remaining}s`;
      if (remaining < 3600) {
        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
      }
      const hours = Math.floor(remaining / 3600);
      const minutes = Math.floor((remaining % 3600) / 60);
      return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
    } catch {
      return null;
    }
  };

  // Format relative time
  const formatRelativeTime = (lastFireTime: string | null): string => {
    if (!lastFireTime) return 'Never';

    try {
      const last = new Date(lastFireTime).getTime();
      const diff = Math.floor((clientTime - last) / 1000);

      if (diff < 60) return `${diff}s ago`;
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      return `${Math.floor(diff / 86400)}d ago`;
    } catch {
      return 'Unknown';
    }
  };

  // Format schedule details
  const formatScheduleDetails = (spec: ScheduleSpecDisplay): string => {
    let base = '';
    if (spec.type === 'interval' && spec.interval) {
      const match = spec.interval.match(/PT?(\d+)([SMH])|P(\d+)D/);
      if (match) {
        const value = match[1] || match[3];
        const unit = match[2] || 'D';
        const unitName = unit === 'S' ? 'seconds' : unit === 'M' ? 'minutes' : unit === 'H' ? 'hours' : 'days';
        base = `Every ${value} ${unitName}`;
      } else {
        base = `Every ${spec.interval}`;
      }
    } else if (spec.type === 'time' && spec.time) {
      const [hours, minutes] = spec.time.split(':');
      const hour = parseInt(hours || '0', 10);
      const ampm = hour >= 12 ? 'PM' : 'AM';
      const displayHour = hour % 12 || 12;
      base = `Daily at ${displayHour}:${minutes} ${ampm} UTC`;
    } else if (spec.type === 'datetime' && spec.datetime) {
      try {
        const dt = new Date(spec.datetime);
        base = `Scheduled: ${dt.toLocaleString()}`;
      } catch {
        base = `Scheduled: ${spec.datetime}`;
      }
    } else if (spec.type === 'cron' && spec.cron) {
      base = `Cron: ${spec.cron}`;
    } else {
      base = 'Unknown schedule';
    }

    // Add max_repeats if specified
    if (spec.max_repeats !== null && spec.max_repeats !== undefined) {
      base += ` (max ${spec.max_repeats})`;
    }

    return base;
  };

  const nextFireCountdown = timerState ? calculateNextFireCountdown(timerState.next_fire_time) : null;
  const lastFireRelative = timerState ? formatRelativeTime(timerState.last_fire_time) : 'Never';
  const scheduleDetails = formatScheduleDetails(scheduleSpec);

  const isCompleted = timerState?.is_completed ?? false;
  const isStopped = timerState?.is_stopped ?? false;
  const isActive = timerState?.is_active ?? true;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
      {/* Timer Panel */}
      {!compactNodeView && (
        <div
          style={{
            padding: '8px 10px',
            background: 'rgba(20, 184, 166, 0.08)',
            borderLeft: '3px solid var(--color-teal-500, #14b8a6)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-xs)',
          }}
          role="region"
          aria-label="Scheduled timer details"
        >
          {/* Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginBottom: '6px',
          }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '20px',
                height: '20px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--color-teal-100, #ccfbf1)',
                color: 'var(--color-teal-700, #0f766e)',
                fontSize: '12px',
                fontWeight: 700,
              }}
              aria-label="Scheduled timer"
            >
              ⏰
            </div>
            <div style={{
              fontSize: '10px',
              fontFamily: 'var(--font-family-mono)',
              color: 'var(--color-teal-700, #0f766e)',
              fontWeight: 600,
            }}>
              Scheduled Timer
            </div>
          </div>

          {/* Status Badge */}
          {(isCompleted || isStopped) && (
            <div style={{
              display: 'inline-block',
              padding: '2px 6px',
              background: isCompleted ? 'var(--color-success-light, #86efac)' : 'var(--color-warning-light, #fde047)',
              color: isCompleted ? 'var(--color-success-dark, #166534)' : 'var(--color-warning-dark, #854d0e)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '9px',
              fontWeight: 600,
              marginBottom: '6px',
            }}>
              {isCompleted ? '✓ Completed' : '⏸ Stopped'}
            </div>
          )}

          {/* Timer Info */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '10px' }}>
            {/* Next Fire Countdown */}
            {nextFireCountdown && isActive && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  color: 'var(--color-teal-600, #0d9488)',
                  fontWeight: 600,
                }}
                title={`Next execution in ${nextFireCountdown}`}
                aria-live="polite"
                aria-atomic="true"
              >
                <span>Next:</span>
                <span>{nextFireCountdown}</span>
              </div>
            )}

            {/* Iteration Count */}
            {timerState && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  color: 'var(--color-teal-600, #0d9488)',
                }}
                title={`Timer has fired ${timerState.iteration} times`}
              >
                <span>Run #{timerState.iteration + 1}</span>
                {isStopped && (
                  <span style={{ fontSize: '9px', opacity: 0.8 }}>(final)</span>
                )}
              </div>
            )}

            {/* Last Fire Time */}
            {timerState && timerState.last_fire_time && (
              <div
                style={{
                  fontSize: '9px',
                  color: 'var(--color-text-tertiary)',
                  opacity: 0.7,
                }}
                title={`Last execution: ${lastFireRelative}`}
              >
                Last: {lastFireRelative}
              </div>
            )}

            {/* Schedule Details */}
            <div
              style={{
                fontSize: '9px',
                color: 'var(--color-text-tertiary)',
                opacity: 0.7,
                marginTop: '2px',
              }}
              title={scheduleDetails}
            >
              {scheduleDetails}
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

ScheduledAgentDisplay.displayName = 'ScheduledAgentDisplay';

export default ScheduledAgentDisplay;

