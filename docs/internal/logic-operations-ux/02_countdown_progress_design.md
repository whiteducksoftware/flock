# Countdown Timers & Progress Indicators Design
## Logic Operations UX: Time-Based and Count-Based Constraints

**Document Version:** 1.0
**Date:** October 13, 2025
**Status:** Design Proposal
**Related:** [API Design](../logic-operations/api_design.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Constraint Types](#constraint-types)
3. [Visual Design Patterns](#visual-design-patterns)
4. [Placement Strategy](#placement-strategy)
5. [State Transitions](#state-transitions)
6. [Interaction Patterns](#interaction-patterns)
7. [Accessibility](#accessibility)
8. [Technical Implementation Notes](#technical-implementation-notes)

---

## Executive Summary

### The Challenge

Flock's logic operations (JoinSpec and BatchSpec) introduce **time-based** and **count-based** constraints that require clear, real-time visualization:

- **JoinSpec**: Artifacts must arrive within X time window (e.g., "5 minutes")
- **BatchSpec**: Collect N items OR wait X timeout (e.g., "25 orders OR 30 seconds")
- **Mixed**: "Whichever comes first" logic needs simultaneous display

### Design Goals

1. **Glanceable** - Users understand constraint status at a glance
2. **Non-intrusive** - Doesn't clutter existing node UI
3. **Urgency-aware** - Visual cues for approaching deadlines
4. **Real-time** - Updates via WebSocket without UI jank
5. **Accessible** - WCAG 2.1 AA compliant

### Key Recommendations

| Constraint Type | Visual Pattern | Placement | Priority |
|----------------|---------------|-----------|----------|
| **Time countdown** | Circular progress ring | In-node badge | High |
| **Count progress** | Linear progress bar | In-node metric | High |
| **Mixed (OR logic)** | Dual indicator | In-node composite | High |
| **Waiting state** | Pulsing icon | Status indicator | Medium |

---

## Constraint Types

### 1. Time-Based Constraints

#### JoinSpec - Correlation Window
```python
# Example: Medical diagnostics must arrive within 5 minutes
.consumes(
    XRayImage,
    LabResults,
    join=JoinSpec(
        by=lambda x: x.patient_id,
        within=timedelta(minutes=5)
    )
)
```

**UX Requirements:**
- Show time remaining for each waiting artifact group
- Indicate urgency as timeout approaches
- Display when artifacts expire/discard

#### BatchSpec - Timeout Flush
```python
# Example: Flush batch every 30 seconds
.consumes(
    Order,
    batch=BatchSpec(
        size=25,
        timeout=timedelta(seconds=30)
    )
)
```

**UX Requirements:**
- Show countdown to next flush
- Indicate "partial batch pending"
- Reset timer after flush

### 2. Count-Based Constraints

#### BatchSpec - Size Threshold
```python
# Example: Collect 25 orders before processing
.consumes(
    Order,
    batch=BatchSpec(size=25, timeout=timedelta(seconds=30))
)
```

**UX Requirements:**
- Show current count vs target (e.g., "12/25")
- Visual progress percentage
- Indicate when threshold reached

### 3. Mixed Constraints (OR Logic)

#### BatchSpec - Size OR Timeout
```python
# Example: Whichever comes first
.consumes(
    Order,
    batch=BatchSpec(
        size=25,              # Count constraint
        timeout=timedelta(seconds=30)  # Time constraint
    )
)
```

**UX Requirements:**
- Show BOTH constraints simultaneously
- Indicate which will likely trigger first
- Clear when either triggers

---

## Visual Design Patterns

### Pattern 1: Circular Progress Ring (Time Countdown)

**Best for:** Time-based constraints, countdowns, urgency

```
┌─────────────────────┐
│  ⏱️  [■■■■■□□□]  45s │  ← Circular ring fills as time passes
│                     │     Color transitions: green → yellow → red
│  patient_123        │     Number shows seconds remaining
└─────────────────────┘
```

**Visual Specs:**
- **Size**: 24px diameter (compact), 32px (expanded)
- **Stroke**: 3px width
- **Colors**:
  - Green: `#10B981` (80-100% time remaining)
  - Yellow: `#FBBF24` (30-80% time remaining)
  - Red: `#EF4444` (0-30% time remaining)
- **Animation**: Smooth rotation, CSS transition 0.3s
- **Accessibility**: ARIA label "X seconds remaining for correlation"

**Pros:**
- Highly visual, easy to interpret
- Shows urgency via color
- Compact footprint
- Familiar metaphor (timer/clock)

**Cons:**
- Hard to read precise numbers
- May be too animated/distracting

---

### Pattern 2: Linear Progress Bar (Count-Based)

**Best for:** Count-based constraints, batch accumulation

```
┌─────────────────────────────────┐
│  Orders: 12/25  [████████░░░░]  │  ← Linear bar shows fill percentage
│                                 │     Label shows exact count
│  48%  |  13 more to flush       │     Secondary text shows remaining
└─────────────────────────────────┘
```

**Visual Specs:**
- **Height**: 8px (compact), 12px (expanded)
- **Width**: 100% of container minus padding
- **Colors**:
  - Background: `rgba(255,255,255,0.1)` (dark theme)
  - Fill: `#3B82F6` (info blue)
  - Near-complete: `#10B981` (success green at 90%+)
- **Animation**: Smooth width transition 0.2s ease
- **Accessibility**: ARIA label "12 of 25 orders collected"

**Pros:**
- Precise progress indication
- Easy to read exact numbers
- Minimal visual noise
- Familiar UI pattern

**Cons:**
- Takes more horizontal space
- Less urgent/attention-grabbing

---

### Pattern 3: Dual Indicator (Mixed OR Logic)

**Best for:** BatchSpec with both size AND timeout

```
┌──────────────────────────────────────┐
│  ⏱️ 18s  OR  📦 12/25 (48%)          │  ← Both constraints shown
│  [■■■■■■□□□□]  [████████░░░░]        │     Whichever fills first wins
│  "Time likely" or "Count likely"     │     Prediction hint
└──────────────────────────────────────┘
```

**Visual Specs:**
- **Layout**: Horizontal split, countdown left, count right
- **Separator**: "OR" in muted gray
- **Highlight**: Border glow on constraint closest to triggering
- **Colors**: Same as individual patterns
- **Accessibility**: ARIA label "Batch will flush in 18 seconds or after 13 more orders, whichever comes first"

**Pros:**
- Shows complete state
- Makes OR logic explicit
- Helps users predict behavior

**Cons:**
- More complex layout
- May be visually busy
- Requires more space

---

### Pattern 4: Compact Badge (In-Node Status)

**Best for:** Inline display within existing AgentNode UI

```
┌─────────────────────────────────┐
│  radiologist             🟢      │  ← Agent name and status
│                                  │
│  ↓ 3  XRayImage                  │  ← Input type
│  ↓ 2  LabResults  ⏱️ [■■■□] 45s  │  ← With countdown badge
│  ↑ 5  DiagnosticReport           │  ← Output type
└─────────────────────────────────┘
```

**Visual Specs:**
- **Size**: 16px icon + 24px countdown ring
- **Position**: Right-aligned on input row
- **Colors**: Match constraint type (time=yellow, count=blue)
- **Hover**: Tooltip with full details
- **Accessibility**: Screenreader text "2 lab results waiting, 45 seconds until expiry"

**Pros:**
- Minimal space usage
- Integrates with existing UI
- Contextual (next to relevant input type)

**Cons:**
- Limited space for details
- May clutter dense UIs

---

### Pattern 5: Status Panel Section (Dedicated Area)

**Best for:** Detailed view in NodeDetailWindow tabs

```
┌──────────────────────────────────────────────────┐
│  Batch Status                                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
│                                                   │
│  📦 Current Batch: 12/25 orders (48%)            │
│  [████████████████████░░░░░░░░░░░░░░░░░░░░]      │
│                                                   │
│  ⏱️  Timeout: 18 seconds remaining               │
│  [■■■■■■■■■■■■■■■■■■□□□□]  60% elapsed           │
│                                                   │
│  💡 Prediction: Timeout will likely trigger      │
│     (13 more orders needed in 18s = low chance)  │
│                                                   │
│  📊 History:                                      │
│  • Last flush: 30s ago (25 orders - size limit)  │
│  • Avg batch size: 23.4 orders                   │
│  • Avg flush time: 28.2 seconds                  │
└──────────────────────────────────────────────────┘
```

**Visual Specs:**
- **Location**: New tab or section in NodeDetailWindow
- **Layout**: Vertical stack, generous padding
- **Typography**: 14px body, 12px metadata
- **Colors**: Semantic (info, warning, success)
- **Accessibility**: Full semantic HTML with ARIA labels

**Pros:**
- Room for comprehensive details
- Analytics and history
- Doesn't clutter graph view

**Cons:**
- Requires user interaction (open window)
- Not glanceable from main view

---

## Placement Strategy

### Hierarchy of Visibility

**Priority 1: Critical Real-time (Always Visible)**
- **Location**: In-node badge on AgentNode
- **Use cases**: Active countdowns, near-threshold batches
- **Pattern**: Compact badge (Pattern 4)
- **Example**: JoinSpec countdown showing 10 seconds left

**Priority 2: Contextual (Visible on Hover)**
- **Location**: Tooltip on node hover
- **Use cases**: Detailed status, prediction hints
- **Pattern**: Popover with progress bars
- **Example**: "12/25 orders, 18s remaining, timeout likely"

**Priority 3: Detailed (Requires Click)**
- **Location**: NodeDetailWindow → New "Batch Status" or "Join Status" tab
- **Use cases**: Full history, analytics, configuration
- **Pattern**: Status panel (Pattern 5)
- **Example**: Batch flush history, average batch size

---

### Placement Recommendations by Constraint Type

#### JoinSpec (Correlation Window)

**In-Node Display:**
```tsx
// Add to input type row in AgentNode.tsx
<div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
  <div>↓ 2 LabResults</div>

  {/* Countdown badge for waiting artifacts */}
  {hasWaitingArtifacts && (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      padding: '2px 6px',
      background: 'rgba(251, 191, 36, 0.15)',
      borderRadius: '12px',
      fontSize: '10px',
      fontWeight: 600,
      color: '#FBBF24'
    }}>
      <svg>⏱️</svg> {/* Circular progress ring */}
      <span>{remainingSeconds}s</span>
    </div>
  )}
</div>
```

**Detail Window:**
- Show all waiting correlation groups
- List correlation keys (e.g., patient IDs)
- Individual countdowns per group
- Expiry notifications

#### BatchSpec (Count + Timeout)

**In-Node Display:**
```tsx
// Add batch status below input rows
{hasBatchSpec && (
  <div style={{
    marginTop: '8px',
    padding: '8px',
    background: 'rgba(59, 130, 246, 0.08)',
    borderRadius: '8px',
    fontSize: '11px'
  }}>
    {/* Dual indicator for count + timeout */}
    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
      <div style={{ flex: 1 }}>
        <div>📦 {currentCount}/{batchSize}</div>
        {/* Linear progress bar */}
        <ProgressBar percent={currentCount / batchSize * 100} />
      </div>
      <div style={{ color: '#888' }}>OR</div>
      <div style={{ flex: 1 }}>
        <div>⏱️ {remainingSeconds}s</div>
        {/* Circular countdown */}
        <CircularProgress percent={elapsedPercent} />
      </div>
    </div>
  </div>
)}
```

**Detail Window:**
- Full batch history (time, size, trigger reason)
- Analytics (avg batch size, avg flush time)
- Cost savings calculation (for BatchSpec examples)

---

## State Transitions

### State Machine: JoinSpec Countdown

```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│  [IDLE]                                                  │
│   │   No constraints active                             │
│   │   Display: None                                     │
│   │                                                      │
│   ├─ First artifact arrives                             │
│   │                                                      │
│   ▼                                                      │
│  [WAITING]                                               │
│   │   Countdown started                                 │
│   │   Display: Green ring, plenty of time              │
│   │                                                      │
│   ├─ 80% time elapsed                                   │
│   │                                                      │
│   ▼                                                      │
│  [APPROACHING]                                           │
│   │   Getting close to timeout                          │
│   │   Display: Yellow ring, urgency indicator          │
│   │                                                      │
│   ├─ 90% time elapsed                                   │
│   │                                                      │
│   ▼                                                      │
│  [CRITICAL]                                              │
│   │   About to expire                                   │
│   │   Display: Red ring, pulsing animation             │
│   │                                                      │
│   ├─ Match found → [MATCHED]                            │
│   │   OR                                                 │
│   ├─ Timeout → [EXPIRED]                                │
│   │                                                      │
│   ▼                                                      │
│  [MATCHED] / [EXPIRED]                                   │
│   │   Success or failure                                │
│   │   Display: Flash green (matched) or fade out       │
│   │            (expired)                                 │
│   │                                                      │
│   └─ Return to [IDLE] after 2s                          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**State Visual Specs:**

| State | Color | Icon | Animation | Duration Display |
|-------|-------|------|-----------|-----------------|
| **IDLE** | None | None | None | Hidden |
| **WAITING** | Green `#10B981` | ⏱️ | Smooth rotation | "45s remaining" |
| **APPROACHING** | Yellow `#FBBF24` | ⏰ | Faster rotation | "15s remaining" |
| **CRITICAL** | Red `#EF4444` | 🔥 | Pulse + rotate | "5s remaining!" |
| **MATCHED** | Green `#10B981` | ✓ | Flash + fade | "Matched!" |
| **EXPIRED** | Gray `#6B7280` | ✗ | Fade out | "Expired" |

---

### State Machine: BatchSpec Progress

```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│  [IDLE]                                                  │
│   │   No batch active                                   │
│   │   Display: None                                     │
│   │                                                      │
│   ├─ First artifact arrives                             │
│   │                                                      │
│   ▼                                                      │
│  [COLLECTING]                                            │
│   │   Accumulating artifacts                            │
│   │   Display: Blue progress bar, count indicator      │
│   │   Dual: Timer also running if timeout set          │
│   │                                                      │
│   ├─ 75% of size reached OR 75% of time elapsed         │
│   │                                                      │
│   ▼                                                      │
│  [NEAR_FLUSH]                                            │
│   │   Close to triggering                               │
│   │   Display: Highlight closer constraint             │
│   │             Glow effect on likely trigger           │
│   │                                                      │
│   ├─ Size reached → [FLUSH_SIZE]                        │
│   │   OR                                                 │
│   ├─ Timeout → [FLUSH_TIMEOUT]                          │
│   │                                                      │
│   ▼                                                      │
│  [FLUSH_SIZE] / [FLUSH_TIMEOUT]                          │
│   │   Batch delivered to agent                          │
│   │   Display: Flash with reason ("Size" or "Timeout") │
│   │                                                      │
│   └─ Return to [IDLE], reset counters                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**State Visual Specs:**

| State | Count Color | Time Color | Animation | Helper Text |
|-------|------------|------------|-----------|-------------|
| **IDLE** | None | None | None | "Waiting for first item" |
| **COLLECTING** | Blue `#3B82F6` | Yellow `#FBBF24` | None | "12/25 (48%) OR 18s" |
| **NEAR_FLUSH** | Glow on closest | Glow on closest | Pulse | "Count likely" or "Timeout likely" |
| **FLUSH_SIZE** | Green flash | Gray | Success flash | "Flushed: Size reached (25 items)" |
| **FLUSH_TIMEOUT** | Gray | Green flash | Success flash | "Flushed: Timeout (12 items)" |

---

## Interaction Patterns

### User Interactions

#### 1. Hover to Reveal Details

**Trigger:** Mouse hover over countdown badge or progress bar
**Response:** Tooltip with full details

```
┌─────────────────────────────────────────────┐
│  Batch Status (Hover Tooltip)              │
├─────────────────────────────────────────────┤
│                                             │
│  📦 Current: 12 of 25 orders (48%)          │
│  ⏱️  Timeout: 18 seconds remaining          │
│                                             │
│  💡 Prediction: Timeout will trigger        │
│     Need 13 more orders in 18s (~0.7/sec)   │
│     Recent rate: 0.4 orders/sec             │
│                                             │
│  🔍 Click for detailed history              │
│                                             │
└─────────────────────────────────────────────┘
```

**Implementation:**
- 300ms delay before showing (prevent flicker)
- Follows cursor (offset 10px)
- Auto-dismiss on mouse leave
- Accessible via keyboard (focus + Enter)

#### 2. Click to Open Detail Window

**Trigger:** Click on countdown badge or agent node with active constraints
**Response:** Open NodeDetailWindow with "Batch Status" or "Join Status" tab

**Detail Window Contents:**
- Real-time status (same as hover, but persistent)
- Historical data (last 10 flushes/matches)
- Analytics (avg batch size, success rate)
- Configuration display (size, timeout, correlation key)

#### 3. Prediction Hints

**Logic:** Estimate which constraint will trigger first

```typescript
// Pseudo-code for prediction
const countRate = recentItemCount / elapsedTime; // items per second
const itemsNeeded = batchSize - currentCount;
const timeToReachSize = itemsNeeded / countRate;

if (timeToReachSize < remainingTimeout) {
  prediction = "Size threshold likely";
  highlightConstraint = "count";
} else {
  prediction = "Timeout likely";
  highlightConstraint = "time";
}
```

**Display:**
- Subtle glow on highlighted constraint
- Tooltip shows reasoning
- Updates in real-time as rate changes

---

## Accessibility

### WCAG 2.1 AA Compliance

#### Color Contrast
- All text meets 4.5:1 contrast ratio minimum
- Status colors (green/yellow/red) paired with icons (not color-only)
- Alternative patterns for colorblind users:
  - Shapes: Circle (green), Triangle (yellow), Square (red)
  - Patterns: Solid fill, striped, dotted

#### Screen Reader Support
```tsx
// ARIA labels for all indicators
<div
  role="status"
  aria-label="Batch collecting: 12 of 25 orders, 48% full, 18 seconds until timeout"
  aria-live="polite"
  aria-atomic="true"
>
  {/* Visual progress indicators */}
</div>
```

**Live Region Updates:**
- Use `aria-live="polite"` for countdowns (non-disruptive)
- Use `aria-live="assertive"` for critical (< 10s remaining)
- Throttle announcements to every 10 seconds (prevent spam)

#### Keyboard Navigation
- All interactive elements focusable via Tab
- Hover tooltips also show on keyboard focus
- Enter/Space to open detail window
- Escape to dismiss tooltips/windows

#### Motion Reduction
```css
@media (prefers-reduced-motion: reduce) {
  .countdown-ring {
    animation: none; /* Disable rotation */
    transition: none; /* Instant updates */
  }

  .progress-bar {
    transition: width 0.05s linear; /* Minimal transition */
  }

  .pulse-animation {
    animation: none; /* Disable pulse */
  }
}
```

#### High Contrast Mode
```css
@media (prefers-contrast: high) {
  .countdown-badge {
    border: 2px solid currentColor; /* Visible border */
  }

  .progress-bar {
    outline: 2px solid currentColor; /* Visible outline */
  }
}
```

---

## Technical Implementation Notes

### Data Flow

#### Backend → Frontend (WebSocket)

```typescript
// WebSocket message schema
interface ConstraintStatus {
  agentName: string;
  subscriptionIndex: number;

  // For JoinSpec
  joinStatus?: {
    waitingGroups: Array<{
      correlationKey: string;
      artifactTypes: string[];
      startedAt: number; // Unix timestamp
      expiresAt: number;
      artifactCount: number;
    }>;
  };

  // For BatchSpec
  batchStatus?: {
    currentCount: number;
    targetSize: number | null;
    startedAt: number;
    timeoutAt: number | null;
    recentFlushes: Array<{
      timestamp: number;
      itemCount: number;
      triggerReason: "size" | "timeout" | "shutdown";
    }>;
  };
}
```

#### Frontend State Management

```typescript
// Add to existing AgentNode data
interface AgentNodeData {
  name: string;
  status: string;
  // ... existing fields

  // New: Constraint status
  constraints?: {
    join?: JoinConstraintState;
    batch?: BatchConstraintState;
  };
}

interface JoinConstraintState {
  waitingGroups: WaitingGroup[];
}

interface BatchConstraintState {
  currentCount: number;
  targetSize: number | null;
  timeoutRemaining: number | null; // milliseconds
  prediction: "size" | "timeout" | "unknown";
}
```

### Update Frequency

**Real-time Updates (every 1-2 seconds):**
- Countdown timers
- Batch progress counts
- Prediction calculations

**Throttled Updates (every 5 seconds):**
- Analytics/history in detail window
- Rate calculations

**Event-driven Updates (immediate):**
- Flush/match events
- State transitions (WAITING → CRITICAL)

### Performance Considerations

1. **Memoization:** Use React.memo for countdown components
2. **Virtualization:** Only render visible nodes with constraints
3. **Debouncing:** Throttle WebSocket updates to max 1 per second per node
4. **CSS Animations:** Use GPU-accelerated transforms for smooth rotation
5. **Lazy Loading:** Detail window only renders when opened

---

## Visual Mockups (ASCII Art)

### Mockup 1: JoinSpec - Medical Diagnostics

```
┌──────────────────────────────────────────────────────────┐
│  Agent View - Radiologist (JoinSpec Active)             │
├──────────────────────────────────────────────────────────┤
│                                                           │
│   ┌─────────────────────────────────────┐                │
│   │  radiologist                  🟢    │                │
│   │                                     │                │
│   │  ↓ 3  XRayImage                     │                │
│   │                                     │                │
│   │  ↓ 2  LabResults  ⏱️ [■■■■■□] 45s   │ ← Countdown   │
│   │                   🔑 patient_123     │   badge       │
│   │                                     │                │
│   │  ↑ 5  DiagnosticReport              │                │
│   └─────────────────────────────────────┘                │
│                                                           │
│   [Hover Tooltip]                                        │
│   ┌─────────────────────────────────────────────┐        │
│   │  Waiting for Match                          │        │
│   │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │        │
│   │                                             │        │
│   │  🔑 patient_123:                            │        │
│   │  • XRayImage: Arrived 1m 15s ago            │        │
│   │  • LabResults: Waiting...                   │        │
│   │  • Expires in: 45 seconds                   │        │
│   │                                             │        │
│   │  💡 Once LabResults arrives for patient_123,│        │
│   │     both will be delivered to radiologist.  │        │
│   └─────────────────────────────────────────────┘        │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Mockup 2: BatchSpec - E-commerce Orders

```
┌──────────────────────────────────────────────────────────┐
│  Agent View - Payment Processor (BatchSpec Active)      │
├──────────────────────────────────────────────────────────┤
│                                                           │
│   ┌─────────────────────────────────────┐                │
│   │  payment_processor            🟢    │                │
│   │                                     │                │
│   │  ↓ 12  Order                        │                │
│   │                                     │                │
│   │  ┌───────────────────────────────┐  │                │
│   │  │ Batch Status                  │  │                │
│   │  ├───────────────────────────────┤  │                │
│   │  │                               │  │                │
│   │  │  📦 12/25  [████████░░░░]     │  │ ← Count       │
│   │  │   48%    ∣  13 more           │  │   progress    │
│   │  │                               │  │                │
│   │  │         OR                    │  │                │
│   │  │                               │  │                │
│   │  │  ⏱️  18s  [■■■■■■□□□□]        │  │ ← Time        │
│   │  │   60%    ∣  Likely trigger    │  │   countdown   │
│   │  │                               │  │                │
│   │  └───────────────────────────────┘  │                │
│   │                                     │                │
│   │  ↑ 23  PaymentBatch                 │                │
│   └─────────────────────────────────────┘                │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Mockup 3: Detail Window - Batch History

```
┌──────────────────────────────────────────────────────────────┐
│  [×] Agent: payment_processor                                │
├──────────────────────────────────────────────────────────────┤
│  [Live Output] [Message History] [Run Status] [Batch Status]│
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Current Batch                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                               │
│  📦 Count: 12 of 25 orders (48%)                             │
│  [████████████████████░░░░░░░░░░░░░░░░░░░░░░░░]              │
│                                                               │
│  ⏱️  Timeout: 18 seconds remaining (60% elapsed)             │
│  [■■■■■■■■■■■■■■■■■■□□□□□□□□□□□□]                            │
│                                                               │
│  💡 Prediction: Timeout will likely trigger                  │
│     • Need 13 more orders in 18s = ~0.7 orders/sec           │
│     • Recent rate: 0.4 orders/sec (below target)             │
│     • 95% confidence: timeout will trigger first             │
│                                                               │
│  ─────────────────────────────────────────────────────────── │
│                                                               │
│  Batch History (Last 10 Flushes)                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                               │
│  1. 2 minutes ago  →  25 orders (SIZE)  ✓ Full batch        │
│  2. 4 minutes ago  →  18 orders (TIMEOUT)  ⏱️  Partial       │
│  3. 6 minutes ago  →  25 orders (SIZE)  ✓ Full batch        │
│  4. 8 minutes ago  →  22 orders (TIMEOUT)  ⏱️  Partial       │
│  5. 11 minutes ago →  25 orders (SIZE)  ✓ Full batch        │
│                                                               │
│  ─────────────────────────────────────────────────────────── │
│                                                               │
│  Analytics                                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                               │
│  📊 Average batch size: 23.4 orders                          │
│  ⏱️  Average flush time: 28.2 seconds                        │
│  📈 Flush trigger breakdown:                                  │
│      • Size: 60% (3 of 5)                                    │
│      • Timeout: 40% (2 of 5)                                 │
│                                                               │
│  💰 Cost Savings (vs individual processing):                 │
│      • Total orders processed: 117                           │
│      • Batches created: 5                                    │
│      • Transaction fees saved: $23.40                        │
│        (117 × $0.20 saved per batched order)                 │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Mockup 4: Compact View (Space-Constrained)

```
┌──────────────────────────┐
│  radiologist       🟢    │  ← Compact mode
│  ↓ 3/2 ⏱️45s  ↑ 5        │  ← Minimal indicators
└──────────────────────────┘
     ↑      ↑      ↑
     │      │      └─ Output count
     │      └─ Countdown badge
     └─ Input counts (3 XRay, 2 Lab)
```

---

## Recommendations Summary

### Phase 1: MVP (Immediate)
1. **Implement Pattern 4** (Compact Badge) for in-node display
2. **JoinSpec countdown** with color transitions
3. **BatchSpec count** with linear progress
4. **Basic tooltips** on hover

### Phase 2: Enhanced (Near-term)
5. **Pattern 3** (Dual Indicator) for mixed constraints
6. **Prediction hints** ("timeout likely")
7. **Detail Window tab** (Pattern 5) for history
8. **State transition animations** (flash on flush)

### Phase 3: Advanced (Long-term)
9. **Analytics dashboard** (avg batch size, cost savings)
10. **Configurable thresholds** (custom warning at 80%)
11. **Sound notifications** (optional, for critical states)
12. **Historical playback** (replay constraint behavior)

---

## Open Design Questions

1. **Should we show expired/discarded artifacts?**
   - Option A: Fade out silently (clean UI)
   - Option B: Show "3 expired" counter (transparency)
   - Recommendation: B (helps debug JoinSpec issues)

2. **How to handle multiple waiting groups (JoinSpec)?**
   - Option A: Show count only ("2 groups waiting")
   - Option B: Show list of correlation keys
   - Recommendation: A for compact view, B in detail window

3. **Should predictions be visible by default?**
   - Option A: Always show ("timeout likely")
   - Option B: Only in hover tooltip
   - Recommendation: A (helps users understand behavior)

4. **What to do when both constraints are close (50/50)?**
   - Option A: Show "uncertain" state
   - Option B: Highlight both with equal intensity
   - Recommendation: B (more informative)

---

**Document Prepared By:** Claude Code - Interaction Architecture
**Next Steps:**
1. Review with Flock core team
2. Create React component specs
3. Implement in `AgentNode.tsx` and `NodeDetailWindow.tsx`
4. Add WebSocket schema for constraint status
5. User testing with examples (medical, e-commerce)

---

*This design document is a living specification. Update as implementation progresses and user feedback is gathered.*
