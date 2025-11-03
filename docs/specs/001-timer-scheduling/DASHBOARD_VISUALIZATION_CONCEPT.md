# Scheduled Agents Dashboard Visualization Concept

**Status:** Concept Phase  
**Target:** Dashboard frontend visualization for timer-based scheduled agents  
**Version:** 0.5.30+  
**Date:** January 2025

---

## 🎯 Overview

This document outlines the concept for visualizing scheduled agents on the Flock dashboard, inspired by the existing JoinSpec/BatchSpec timer visualizations in `LogicOperationsDisplay.tsx`.

### Goals

1. **Visual Identification**: Users can immediately identify which agents are scheduled vs. event-driven
2. **Timer Status**: Real-time countdown to next execution with client-side updates
3. **Execution History**: Show iteration count and last fire time
4. **Schedule Details**: Display schedule configuration (interval, time, cron)
5. **Consistent UX**: Match the visual patterns of JoinSpec/BatchSpec timers for familiarity

---

## 🎨 Visual Design Concept

### Component: `ScheduledAgentDisplay`

Similar to `LogicOperationsDisplay`, create a dedicated component for scheduled agent information that appears inside agent nodes.

#### Visual Indicators

**1. Schedule Badge (Always Visible)**
- **Icon**: ⏰ (clock emoji) or custom SVG clock icon
- **Color**: Teal/cyan theme (distinct from JoinSpec purple, BatchSpec orange)
- **Position**: Top of agent node, below status indicator
- **Text**: Schedule type abbreviation
  - `"30s"` for interval-based (every 30 seconds)
  - `"5:00 PM"` for time-based (daily at 5 PM)
  - `"0 * * * *"` for cron (shortened if too long)
  - `"1x"` for one-time datetime schedules

**2. Timer Countdown Panel (When Active)**
- **Background**: `rgba(20, 184, 166, 0.08)` (teal-500 with opacity)
- **Border**: `3px solid var(--color-teal-500, #14b8a6)`
- **Border Radius**: `var(--radius-md)`
- **Padding**: `8px 10px`
- **Content**:
  - Header with clock icon + "Scheduled Timer"
  - Next fire countdown: "Next: 23s" (updates every second)
  - Iteration count: "Run #42"
  - Last fire time: "Last: 2m ago"
  - Schedule details: "Every 30 seconds"

**3. One-Time Schedule Indicator**
- For datetime-based schedules that have completed:
  - Show "Completed" badge
  - Gray out the timer panel
  - Show completion time: "Completed at: 2025-01-15 09:00 UTC"

**4. Stopped Timer Indicator**
- For timers that hit `max_repeats`:
  - Show "Stopped" badge
  - Show final iteration: "Stopped after 10 runs"
  - Show final execution time

---

## 📊 Data Structure

### Backend Data Model

The backend should provide schedule information in agent node data:

```typescript
interface AgentNodeData {
  // ... existing fields ...
  scheduleSpec?: ScheduleSpecDisplay;
  timerState?: TimerStateDisplay;
}

interface ScheduleSpecDisplay {
  type: 'interval' | 'time' | 'datetime' | 'cron';
  interval?: string; // ISO 8601 duration string (e.g., "PT30S")
  time?: string; // Time string (e.g., "17:00:00")
  datetime?: string; // ISO 8601 datetime (e.g., "2025-01-15T09:00:00Z")
  cron?: string; // Cron expression (e.g., "0 * * * *")
  after?: string; // Initial delay (ISO 8601 duration)
  max_repeats?: number | null;
}

interface TimerStateDisplay {
  iteration: number; // Current iteration count (0-indexed)
  last_fire_time: string | null; // ISO 8601 datetime of last execution
  next_fire_time: string | null; // ISO 8601 datetime of next execution
  is_active: boolean; // Whether timer is currently running
  is_completed: boolean; // Whether one-time schedule completed
  is_stopped: boolean; // Whether timer hit max_repeats
}
```

### Backend Integration Points

**1. Graph Builder (`graph_builder.py`)**
- Extract `schedule_spec` from agent if present
- Query timer state from `TimerComponent` (if accessible)
- Include in `node_data` during `_build_agent_nodes()`

**2. Timer Component (`timer.py`)**
- Expose timer state via orchestrator or component registry
- Track `last_fire_time`, `next_fire_time`, `iteration` per agent
- Provide state snapshot for dashboard consumption

**3. WebSocket Updates**
- When timer fires, emit event: `timer_fired` with agent name, iteration, fire_time
- When timer completes/stops, emit event: `timer_completed` or `timer_stopped`

---

## 🔧 Implementation Plan

### Phase 1: Backend Data Exposure

**Tasks:**
1. Extend `TimerComponent` to track and expose timer state
   - Store `last_fire_time`, `next_fire_time`, `iteration` per agent
   - Add method: `get_timer_state(agent_name: str) -> TimerStateDisplay | None`

2. Update `GraphAssembler._build_agent_nodes()` to include schedule data
   ```python
   # In _build_agent_nodes()
   if hasattr(agent, 'schedule_spec') and agent.schedule_spec:
       node_data['scheduleSpec'] = _serialize_schedule_spec(agent.schedule_spec)
       node_data['timerState'] = timer_component.get_timer_state(agent.name)
   ```

3. Add helper function `_serialize_schedule_spec()` to convert `ScheduleSpec` to dict

**Files to Modify:**
- `src/flock/components/orchestrator/scheduling/timer.py`
- `src/flock/dashboard/graph_builder.py`

### Phase 2: Frontend Component

**Tasks:**
1. Create `ScheduledAgentDisplay.tsx` component
   - Similar structure to `LogicOperationsDisplay.tsx`
   - Client-side timer countdown (updates every second)
   - Format schedule details for display
   - Handle different schedule types

2. Integrate into `AgentNode.tsx`
   - Add `scheduleSpec` and `timerState` from node data
   - Render `ScheduledAgentDisplay` when schedule exists
   - Position below status indicator, above logic operations

3. Add TypeScript types
   - Extend `src/flock/frontend/src/types/graph.ts` with schedule interfaces

**Files to Create:**
- `src/flock/frontend/src/components/graph/ScheduledAgentDisplay.tsx`

**Files to Modify:**
- `src/flock/frontend/src/components/graph/AgentNode.tsx`
- `src/flock/frontend/src/types/graph.ts`

### Phase 3: Real-Time Updates

**Tasks:**
1. Add WebSocket event handlers for timer events
   - `timer_fired`: Update timer state when timer fires
   - `timer_completed`: Mark timer as completed
   - `timer_stopped`: Mark timer as stopped

2. Update `AgentNode` to listen for timer events
   - Update `timerState` when events received
   - Trigger re-render with new countdown

**Files to Modify:**
- `src/flock/frontend/src/services/websocket.ts`
- `src/flock/frontend/src/components/graph/AgentNode.tsx`
- `src/flock/components/orchestrator/scheduling/timer.py` (emit events)

---

## 🎨 Visual Examples

### Example 1: Interval-Based Timer (Every 30 seconds)

```
┌─────────────────────────────┐
│  health_monitor [idle]      │
│  ───────────────────────────│
│  ⏰ 30s                      │ ← Schedule badge
│  ───────────────────────────│
│  ⏰ Scheduled Timer          │
│  Next: 12s                  │ ← Countdown
│  Run #5                     │ ← Iteration
│  Last: 18s ago              │ ← Last fire
│  Every 30 seconds           │ ← Schedule details
└─────────────────────────────┘
```

### Example 2: Time-Based Timer (Daily at 5 PM)

```
┌─────────────────────────────┐
│  daily_report [idle]         │
│  ───────────────────────────│
│  ⏰ 5:00 PM                  │ ← Schedule badge
│  ───────────────────────────│
│  ⏰ Scheduled Timer          │
│  Next: 3h 42m               │ ← Countdown
│  Run #7                     │ ← Iteration
│  Last: 23h 18m ago          │ ← Last fire
│  Daily at 17:00 UTC         │ ← Schedule details
└─────────────────────────────┘
```

### Example 3: Cron Timer (Every hour)

```
┌─────────────────────────────┐
│  hourly_check [idle]        │
│  ───────────────────────────│
│  ⏰ 0 * * * *               │ ← Schedule badge (cron)
│  ───────────────────────────│
│  ⏰ Scheduled Timer          │
│  Next: 23m 15s              │ ← Countdown
│  Run #24                    │ ← Iteration
│  Last: 36m 45s ago          │ ← Last fire
│  Cron: 0 * * * * (hourly)   │ ← Schedule details
└─────────────────────────────┘
```

### Example 4: One-Time Schedule (Completed)

```
┌─────────────────────────────┐
│  reminder [idle]             │
│  ───────────────────────────│
│  ⏰ 1x                       │ ← Schedule badge (one-time)
│  ───────────────────────────│
│  ⏰ Scheduled Timer          │
│  ✓ Completed                │ ← Status badge
│  Run #1                     │ ← Iteration
│  Completed: 2h ago         │ ← Completion time
│  Scheduled: 2025-01-15 09:00│ ← Original schedule
└─────────────────────────────┘
```

### Example 5: Stopped Timer (Max Repeats)

```
┌─────────────────────────────┐
│  reminder [idle]             │
│  ───────────────────────────│
│  ⏰ 30s                      │ ← Schedule badge
│  ───────────────────────────│
│  ⏰ Scheduled Timer          │
│  ⏸ Stopped                  │ ← Status badge
│  Run #10 (final)            │ ← Final iteration
│  Stopped: 5m ago            │ ← Stop time
│  Every 30 seconds (max 10)  │ ← Schedule details
└─────────────────────────────┘
```

---

## 🔍 Code Structure

### Component Hierarchy

```
AgentNode.tsx
├── Status Indicator
├── ScheduledAgentDisplay.tsx  ← NEW
│   ├── Schedule Badge
│   └── Timer Panel
│       ├── Header (clock icon + "Scheduled Timer")
│       ├── Next Fire Countdown
│       ├── Iteration Count
│       ├── Last Fire Time
│       └── Schedule Details
├── Input/Output Counts
├── LogicOperationsDisplay.tsx  ← Existing (JoinSpec/BatchSpec)
└── Streaming Tokens
```

### Component Props

```typescript
interface ScheduledAgentDisplayProps {
  scheduleSpec: ScheduleSpecDisplay;
  timerState: TimerStateDisplay | null;
  compactNodeView?: boolean;
}
```

### Helper Functions

```typescript
// Format schedule for badge display
function formatScheduleBadge(spec: ScheduleSpecDisplay): string {
  if (spec.type === 'interval') {
    return formatDurationShort(spec.interval!); // "30s", "5m", "1h"
  } else if (spec.type === 'time') {
    return formatTime(spec.time!); // "5:00 PM"
  } else if (spec.type === 'datetime') {
    return '1x'; // One-time indicator
  } else if (spec.type === 'cron') {
    return spec.cron!.substring(0, 10); // Truncate if long
  }
  return '?';
}

// Calculate client-side countdown
function calculateNextFireCountdown(
  nextFireTime: string | null,
  clientTime: number
): string | null {
  if (!nextFireTime) return null;
  
  const next = new Date(nextFireTime).getTime();
  const remaining = Math.max(0, Math.floor((next - clientTime) / 1000));
  
  if (remaining < 60) return `${remaining}s`;
  if (remaining < 3600) return `${Math.floor(remaining / 60)}m ${remaining % 60}s`;
  return `${Math.floor(remaining / 3600)}h ${Math.floor((remaining % 3600) / 60)}m`;
}

// Format relative time
function formatRelativeTime(lastFireTime: string | null, clientTime: number): string {
  if (!lastFireTime) return 'Never';
  
  const last = new Date(lastFireTime).getTime();
  const diff = Math.floor((clientTime - last) / 1000);
  
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
```

---

## 🎯 UX Considerations

### Visual Hierarchy

1. **Schedule Badge**: Always visible, compact, shows schedule type at a glance
2. **Timer Panel**: Expanded view with full details, appears below badge
3. **Color Coding**: Teal/cyan theme distinguishes from JoinSpec (purple) and BatchSpec (orange)

### Accessibility

- Add `aria-label` attributes for screen readers
- Use `aria-live="polite"` for countdown updates
- Provide keyboard navigation for timer details
- Ensure sufficient color contrast (WCAG AA)

### Responsive Design

- **Compact Mode**: Show only badge, hide timer panel details
- **Normal Mode**: Show full timer panel with all details
- **Mobile**: Stack vertically, truncate long schedule strings

### Performance

- Client-side timer updates every second (similar to `LogicOperationsDisplay`)
- Debounce WebSocket updates to avoid excessive re-renders
- Use `useMemo` for expensive calculations (countdown formatting)

---

## 🧪 Testing Strategy

### Unit Tests

1. **Schedule Badge Formatting**
   - Test all schedule types (interval, time, datetime, cron)
   - Test edge cases (very long intervals, invalid cron)

2. **Countdown Calculation**
   - Test countdown accuracy (seconds, minutes, hours)
   - Test edge cases (zero, negative, very large)

3. **Relative Time Formatting**
   - Test different time ranges (seconds, minutes, hours, days)
   - Test edge cases (null, future time)

### Integration Tests

1. **Component Integration**
   - Test rendering in `AgentNode` with schedule data
   - Test interaction with `LogicOperationsDisplay` (both visible)

2. **WebSocket Updates**
   - Test timer state updates on `timer_fired` event
   - Test completion/stop state updates

### Visual Regression Tests

1. Screenshot tests for each schedule type
2. Screenshot tests for different states (active, completed, stopped)
3. Screenshot tests for compact vs normal mode

---

## 📋 Implementation Checklist

### Backend

- [ ] Extend `TimerComponent` to track timer state
- [ ] Add `get_timer_state(agent_name)` method
- [ ] Update `GraphAssembler._build_agent_nodes()` to include schedule data
- [ ] Add `_serialize_schedule_spec()` helper function
- [ ] Emit WebSocket events for timer fires/completions
- [ ] Add tests for timer state tracking

### Frontend

- [ ] Create `ScheduledAgentDisplay.tsx` component
- [ ] Add schedule TypeScript interfaces to `graph.ts`
- [ ] Integrate `ScheduledAgentDisplay` into `AgentNode.tsx`
- [ ] Add client-side timer countdown logic
- [ ] Add schedule formatting helpers
- [ ] Add WebSocket event handlers for timer updates
- [ ] Add accessibility attributes
- [ ] Add unit tests
- [ ] Add integration tests

### Documentation

- [ ] Update dashboard guide with scheduled agent visualization
- [ ] Add screenshots to documentation
- [ ] Update API reference for schedule data structure

---

## 🚀 Future Enhancements

### Phase 2: Advanced Features

1. **Timer Controls**
   - Pause/resume timer from dashboard
   - Manual trigger button
   - Edit schedule (with validation)

2. **Execution History**
   - Show last N executions in expandable panel
   - Execution duration, success/failure status
   - Link to trace viewer

3. **Schedule Visualization**
   - Calendar view for time-based schedules
   - Timeline view for cron schedules
   - Next N fire times preview

### Phase 3: Analytics

1. **Timer Metrics**
   - Average execution time
   - Success rate
   - Missed fires (if agent slow)

2. **Alerts**
   - Warning when timer fires during slow execution
   - Alert when max_repeats approaching
   - Alert when one-time schedule approaching

---

## 📖 References

- **JoinSpec/BatchSpec Visualization**: `src/flock/frontend/src/components/graph/LogicOperationsDisplay.tsx`
- **Timer Scheduling Design**: `docs/specs/001-timer-scheduling/design/DESIGN.md`
- **Timer Scheduling Guide**: `docs/guides/scheduling.md`
- **Dashboard Graph Builder**: `src/flock/dashboard/graph_builder.py`

---

## ✅ Acceptance Criteria

The visualization is complete when:

1. ✅ Scheduled agents show a schedule badge in agent nodes
2. ✅ Timer countdown updates every second (client-side)
3. ✅ Schedule details are clearly displayed
4. ✅ Iteration count and last fire time are visible
5. ✅ Completed/stopped timers show appropriate status
6. ✅ Visual design matches JoinSpec/BatchSpec patterns
7. ✅ WebSocket updates refresh timer state in real-time
8. ✅ Component is accessible (WCAG AA compliant)
9. ✅ Tests pass (unit + integration)
10. ✅ Documentation updated

---

**End of Concept Document**


