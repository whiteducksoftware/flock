# Waiting States & Batch Collection UX Research
## Research for JoinSpec and BatchSpec Visualization

**Document Version:** 1.0
**Date:** October 13, 2025
**Status:** Research Complete
**Purpose:** Inform dashboard design for agent waiting states, batch collection, and correlation matching

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Research Context](#research-context)
3. [Industry Analysis](#industry-analysis)
4. [Visual Design Patterns](#visual-design-patterns)
5. [Information Architecture](#information-architecture)
6. [Backend Data Requirements](#backend-data-requirements)
7. [Recommendations](#recommendations)
8. [References](#references)

---

## Executive Summary

### Research Goals

This research investigated UX patterns for visualizing agent waiting states in two critical scenarios:

1. **JoinSpec Pattern**: Agents waiting for multiple correlated inputs within time windows
2. **BatchSpec Pattern**: Agents collecting items until batch size or timeout threshold

### Key Findings

**Pattern Discovery**: 5+ industry tools analyzed (Airflow, Prefect, Temporal, Kafka monitoring, n8n)

**Core Insights**:
- **Color-coded state systems** are universal (green=success, blue=running, yellow=waiting, red=error)
- **Dual indicators** (count + timeout) work best for batch collection
- **Timeline visualizations** effectively show correlation windows
- **Progress bars need 200-400ms transitions** for optimal UX
- **Backend should compute display state**, not frontend

### Critical Recommendations

1. Use determinate progress indicators (15/25 collected) when batch size is known
2. Show both countdown timer AND progress toward batch size
3. Visualize correlation keys explicitly ("waiting for patient_id: 12345")
4. Use color intensity to indicate urgency (time running out)
5. Provide backend-computed display states to minimize frontend logic

---

## Research Context

### The Problem Space

**JoinSpec Context** (Medical Diagnostics Example):
```python
radiologist.consumes(
    XRayImage,
    LabResults,
    join=JoinSpec(
        by=lambda x: x.patient_id,        # Correlation key
        within=timedelta(minutes=5)        # Time window
    )
)
```

**User Questions**:
- Is the agent waiting for inputs?
- Which specific inputs are missing (X-ray or Lab results)?
- What patient_id is it waiting for?
- How much time remains before timeout?
- What happens if timeout expires?

**BatchSpec Context** (E-commerce Example):
```python
payment_processor.consumes(
    Order,
    batch=BatchSpec(
        size=25,                           # Target batch size
        timeout=timedelta(seconds=30)      # Max wait time
    )
)
```

**User Questions**:
- How many items collected so far (15/25)?
- How much time until timeout flush?
- What triggers the flush (size or timeout)?
- Can I see the items in the current batch?
- What's the cost savings from batching?

### Success Criteria

A successful UX design should:
1. Communicate agent state without requiring user to read code
2. Show progress toward completion (batch filling or correlation matching)
3. Indicate time pressure (countdown to timeout)
4. Reveal what action is blocking progress
5. Minimize cognitive load (glanceable status)

---

## Industry Analysis

### 1. Apache Airflow - Workflow Orchestration

**Analyzed Features**:
- Task instance state visualization in grid view
- Color-coded squares representing task states
- Comprehensive state model

**State Model**:
```
none → scheduled → queued → running → success
                              ↓
                           failed
```

**Visual Patterns**:
- **Grid View**: Each square = task instance, color = state
- **Color System**:
  - Light gray: None/not scheduled
  - Light blue: Scheduled
  - Yellow/orange: Queued (waiting)
  - Green: Running
  - Dark green: Success
  - Red: Failed
- **Hover Details**: Shows duration, start time, end time
- **Customizable**: `airflow_local_settings.py` allows custom state colors

**Key Takeaways**:
- ✅ Color-coding is primary communication method
- ✅ Multiple views (grid, graph, Gantt) serve different needs
- ✅ Hover interactions reveal detailed state information
- ✅ "Queued" (waiting) state is visually distinct from "Running"
- ⚠️ Does not show progress toward completion while waiting

**Relevance to Flock**:
- Adopt similar color system for agent states
- Use "queued/waiting" as distinct visual state
- Provide hover tooltips for detailed correlation/batch info

---

### 2. Prefect - Modern Workflow Engine

**Analyzed Features**:
- Real-time UI with timeline visualization
- Flow run states with pause/resume capabilities
- Input waiting mechanism

**State Visualization**:
- **Timeline View**: Horizontal timeline showing task sequence and duration
- **Gantt Chart**: Visual representation of parallel execution
- **State Transitions**: Clear visual indication of state changes
- **Pause/Resume**: Special state for flows waiting for user input

**Wait for Input Pattern**:
```python
# Prefect's waiting pattern
pause_flow_run(wait_for_input=UserInputModel)
# Flow pauses until user submits form in UI
```

**Visual Elements**:
- Task duration bars (proportional to execution time)
- Real-time updates (live status changes)
- Color-coded states (similar to Airflow)
- Interactive controls (resume, cancel)

**Key Takeaways**:
- ✅ Timeline view excellent for showing duration-based waiting
- ✅ Real-time updates critical for waiting state UX
- ✅ Interactive controls reduce user anxiety during waits
- ✅ Forms/inputs can be embedded in waiting state UI
- ⚠️ Focus on sequential flows, less on correlation

**Relevance to Flock**:
- Timeline view could show JoinSpec time windows
- Real-time updates essential for batch fill progress
- Interactive "force flush" for batch debugging

---

### 3. Temporal - Distributed Workflows

**Analyzed Features**:
- Long-running workflow state inspection
- Query API for reading workflow state
- Efficient waiting through event sourcing

**Technical Pattern**:
```typescript
// Temporal's waiting semantics
await Promise.all([activityA(), activityB()])  // AND (wait for both)
await Promise.race([activityA(), activityB()]) // OR (first wins)
```

**State Management**:
- **Cold Storage**: Workflow state persisted, not in memory
- **On-Demand Loading**: State loaded only when queried
- **Awaitable APIs**: Explicit await points for coordination
- **State Queries**: Read-only inspection without side effects

**Key Takeaways**:
- ✅ Explicit await semantics (Promise.all = JoinSpec-like)
- ✅ State inspection separate from execution
- ✅ Efficient for long-running waits (hours/days)
- ⚠️ Less visual, more code-centric

**Relevance to Flock**:
- Backend should maintain queryable waiting state
- Distinguish between "actively waiting" and "cold storage"
- WebSocket updates for real-time dashboard

---

### 4. Kafka Monitoring Tools - Stream Processing

**Analyzed Tools**:
- Confluent Control Center
- CMAK (Cluster Manager for Apache Kafka)
- Burrow + BurrowUI
- Prometheus + Grafana dashboards

**Key Metrics Visualized**:
- **Consumer Lag**: Number of messages behind (e.g., "150 messages behind")
- **Offset Position**: Current vs latest offset
- **Partition-Level Detail**: Per-partition lag visualization
- **Lag Trend**: Historical lag over time (growing/shrinking)

**Visual Patterns**:

**1. Consumer Lag Dashboard** (Confluent Control Center):
- Numeric badge: "150 messages behind"
- Trend line: Lag over last hour
- Color coding: Green (<100), Yellow (100-1000), Red (>1000)
- Per-partition breakdown

**2. Offset Visualization** (Grafana):
- Line chart: Current offset vs latest offset
- Gap between lines = lag
- Rate of change shows throughput

**3. Queue Depth Indicator**:
- Progress bar showing "caught up" state
- Example: [=========>    ] 75% caught up

**Key Takeaways**:
- ✅ Numeric indicators critical ("15 of 25" style)
- ✅ Trend lines show whether situation improving/worsening
- ✅ Color-coded thresholds for urgency
- ✅ Drill-down from aggregate to detail
- ✅ Rate of change matters (items/sec)

**Relevance to Flock**:
- BatchSpec needs "15/25 collected" indicator
- Show collection rate ("2 items/sec")
- Color urgency: green (plenty of time), yellow (approaching timeout), red (critical)
- Historical trend: "Typical batch: 18 items before timeout"

---

### 5. n8n - Workflow Automation

**Analyzed Features**:
- Visual workflow editor with node states
- Wait node with multiple modes
- Real-time execution status

**Wait Node Modes**:
1. **After Time Interval**: Wait for duration (e.g., 30 seconds)
2. **At Specified Time**: Wait until specific timestamp
3. **On Webhook Call**: Wait for external trigger
4. **On Form Submission**: Wait for user input

**Visual Indicators**:
- Status labels: "Waiting, Running, Succeeded, Cancelled, Failed"
- Node color changes based on state
- Execution log filterable by status
- Outputs visible next to node during execution

**Key Takeaways**:
- ✅ Multiple wait types clearly differentiated in UI
- ✅ Execution log provides audit trail
- ✅ Status filters help find waiting/stuck nodes
- ✅ Inline output preview reduces context switching

**Relevance to Flock**:
- Agent card should show wait reason ("waiting for X-ray")
- Execution history shows previous wait durations
- Filter agents by state: "show all waiting agents"

---

### 6. Dagster - Data Orchestration

**Analyzed Features**:
- Asset materialization states
- Run queue management
- Live updating asset graph

**Waiting Behavior**:
- Assets wait for upstream in-progress runs to complete
- Run queue shows "Queued" and "In Progress" tabs
- Asset graph updates live during materialization

**Visual Elements**:
- Asset status badges (Materialized, In Progress, Failed)
- Run queue with waiting explanation
- Dependency graph shows blocking relationships

**Key Takeaways**:
- ✅ Explicit dependency visualization (what's blocking what)
- ✅ Queue position indicator ("3rd in queue")
- ✅ Live updates without full page refresh
- ✅ Action buttons on queued items (cancel, prioritize)

**Relevance to Flock**:
- Show dependency: "Waiting for LabResults (2 minutes elapsed)"
- Queue depth if multiple agents waiting for same resource
- Cancel/skip actions for stuck waiting states

---

## Visual Design Patterns

### Pattern 1: State Color System

**Industry Standard Colors**:

| State | Color | Hex | Usage |
|-------|-------|-----|-------|
| **Success** | Green | `#10B981` | Task completed, batch flushed |
| **Running** | Blue | `#3B82F6` | Actively processing |
| **Waiting** | Yellow/Amber | `#F59E0B` | JoinSpec waiting, batch collecting |
| **Error** | Red | `#EF4444` | Timeout expired, correlation failed |
| **Cancelled** | Gray | `#6B7280` | User cancelled, disabled |
| **Scheduled** | Light blue | `#93C5FD` | Queued, not started |

**Color Intensity for Urgency**:
- Light yellow: `#FEF3C7` - Just started waiting (>80% time remaining)
- Medium yellow: `#FCD34D` - Mid-wait (40-80% time remaining)
- Dark amber: `#F59E0B` - Urgent (20-40% time remaining)
- Orange: `#F97316` - Critical (<20% time remaining)

**Accessibility**:
- Use patterns/icons in addition to color (colorblind users)
- Minimum contrast ratio: 4.5:1 (WCAG AA)
- Provide text labels alongside color indicators

---

### Pattern 2: Progress Indicators

**Best Practices** (from Nielsen Norman Group research):

**Timing Rules**:
- **< 1 second**: No indicator needed
- **1-10 seconds**: Indeterminate spinner or pulse
- **> 10 seconds**: Determinate progress bar with percentage

**For Batch Collection** (Determinate):
```
[████████░░░░░░░░] 15/25 orders collected (60%)
```

**For Time Window** (Countdown):
```
⏱ 2:45 remaining (of 5:00)
[██████████████░░░░] 55% elapsed
```

**Hybrid Indicator** (Both conditions):
```
[████████░░░░░░░░] 15/25 orders
⏱ 12s remaining OR batch size reached
```

**Animation Timing**:
- Smooth transitions: 200-400ms
- Updates: Every 100-500ms (not more frequent)
- Avoid jank: Use CSS transforms (not layout changes)

---

### Pattern 3: Correlation Matching Visualization

**Approaches**:

**A. List-Based** (Simple):
```
Waiting for:
✓ X-ray (received 2m ago)
⏳ Lab results (patient_id: 12345)
```

**B. Timeline-Based** (Visual):
```
Timeline: [━━━━X━━━━━━?━━] 5min window
           ↑           ↑
         X-ray      Timeout
         received   in 3m
```

**C. Badge-Based** (Compact):
```
Agent: radiologist
[1/2] patient_id: 12345  ⏱ 3:15 remaining
↳ Waiting for: LabResults
```

**Recommended**: Combination of A + C
- Badge on agent card (compact)
- Expandable list on click (detail)

---

### Pattern 4: Batch Fill Visualization

**Approaches**:

**A. Progress Bar + Count**:
```
Payment Batch #47
[████████░░░░░░░░] 15/25 orders (60%)
$1,245.50 total | Est. savings: $3.00
```

**B. Grid/Tile View**:
```
[✓][✓][✓][✓][✓]
[✓][✓][✓][✓][✓]
[✓][✓][✓][✓][✓]
[░][░][░][░][░]
[░][░][░][░][░]
```

**C. List with Scroll**:
```
Orders in batch (15/25):
1. Order #1001 - $45.99 ✓
2. Order #1002 - $129.50 ✓
...
15. Order #1015 - $32.00 ✓
```

**Recommended**: A (primary) + C (detail view)
- Progress bar always visible
- List on hover or expand

---

### Pattern 5: Timeout Countdown

**Visual Treatments**:

**A. Numeric Countdown**:
```
⏱ 00:27 remaining
```

**B. Progress Bar (Depleting)**:
```
[██████████░░░░░░] 15s remaining (of 30s)
```

**C. Pie Chart/Radial**:
```
  ⏰
  ╱ ╲
 ╱   ╲
╱ 27s ╲
```

**D. Color-Shifting Bar**:
```
[████████░░░░░░] ← Green (>50% time left)
[████████░░░░░░] ← Yellow (25-50% time left)
[████████░░░░░░] ← Orange (<25% time left)
```

**Recommended**: A + D (color-shifting numeric countdown)
- Clear, accessible
- Color provides glanceable urgency
- No extra space requirements

---

## Information Architecture

### Agent Card States

**Proposed Information Hierarchy**:

#### State 1: Idle (No Waiting)
```
┌─────────────────────────────┐
│ 🤖 radiologist              │
│ Status: Ready               │
│ Last run: 2 min ago         │
└─────────────────────────────┘
```

#### State 2: Waiting (JoinSpec)
```
┌─────────────────────────────┐
│ 🤖 radiologist              │
│ ⏳ Waiting [1/2]            │
│ patient_id: 12345           │
│ ✓ XRayImage (2m ago)        │
│ ⏱ LabResults (3:15 left)    │
│ ────────────────────────    │
│ [██████░░░░] 2/5 min        │
└─────────────────────────────┘
```

#### State 3: Collecting (BatchSpec)
```
┌─────────────────────────────┐
│ 🤖 payment_processor        │
│ 📦 Collecting [15/25]       │
│ $1,245.50 total             │
│ ⏱ 12s OR 10 more orders     │
│ ────────────────────────    │
│ [████████░░░░░░] 60%        │
│ Rate: 2.3 items/sec         │
└─────────────────────────────┘
```

#### State 4: Processing
```
┌─────────────────────────────┐
│ 🤖 radiologist              │
│ 🔄 Processing...            │
│ Duration: 3s                │
└─────────────────────────────┘
```

#### State 5: Completed
```
┌─────────────────────────────┐
│ 🤖 radiologist              │
│ ✅ Completed                │
│ Published: DiagnosticReport │
│ Duration: 5.2s              │
└─────────────────────────────┘
```

#### State 6: Timeout/Error
```
┌─────────────────────────────┐
│ 🤖 radiologist              │
│ ⏰ Timeout expired          │
│ Discarded: XRayImage        │
│ patient_id: 12345           │
│ Missing: LabResults         │
│ ────────────────────────    │
│ [⟳ Retry] [🗑️ Clear]       │
└─────────────────────────────┘
```

---

### Detail View (Expanded State)

**When user clicks waiting agent**:

```
┌───────────────────────────────────────────────┐
│ Agent: radiologist                            │
│ Status: Waiting for correlation               │
├───────────────────────────────────────────────┤
│ JoinSpec Configuration:                       │
│   Correlation key: patient_id                 │
│   Time window: 5 minutes                      │
│   Strategy: all_of (AND gate)                 │
├───────────────────────────────────────────────┤
│ Current Correlation: patient_id = 12345       │
│                                               │
│ ✓ XRayImage                                   │
│   Received: 2024-10-13 14:32:15 (2m ago)     │
│   Quality: high                               │
│   Exam type: chest_xray                       │
│                                               │
│ ⏳ LabResults (waiting)                       │
│   Expected: within 3m 15s                     │
│   Timeout at: 14:37:15                        │
│                                               │
│ Timeline:                                     │
│ [━━X━━━━━━?━━━━━━━━T] 5min window            │
│    ↑       ↑         ↑                        │
│  X-ray  Now(2m)  Timeout(3m)                  │
│                                               │
│ Actions:                                      │
│ [Force Match] [Cancel Wait] [View History]   │
└───────────────────────────────────────────────┘
```

---

### Dashboard Layout Recommendations

**Three-Panel Layout**:

```
┌────────────────────────────────────────────────────┐
│ Header: Flock Dashboard                           │
├────────────┬───────────────────────┬──────────────┤
│            │                       │              │
│  Agents    │   Visualization       │  Inspector   │
│  List      │   (Graph/Timeline)    │  (Details)   │
│            │                       │              │
│  [Agent 1] │   ┌─┐   ┌─┐          │  Selected:   │
│  [Agent 2] │   │A│──▶│B│──▶       │  Agent B     │
│  [Agent 3] │   └─┘   └─┘          │              │
│  [Agent 4] │     ▼                 │  Status:     │
│  [Agent 5] │   ┌─┐                 │  Waiting     │
│            │   │C│                 │              │
│            │   └─┘                 │  [Details]   │
│            │                       │              │
├────────────┴───────────────────────┴──────────────┤
│ Status Bar: 3 running, 2 waiting, 5 idle          │
└────────────────────────────────────────────────────┘
```

**Filtering & Search**:
- Filter by state: "Show only waiting agents"
- Search by correlation key: "patient_id: 12345"
- Group by: Agent type, status, time waiting

---

## Backend Data Requirements

### WebSocket Message Schema

**For JoinSpec Waiting State**:

```json
{
  "event": "agent_state_update",
  "timestamp": "2025-10-13T14:35:00Z",
  "agent_id": "radiologist_1",
  "state": "waiting_for_join",
  "join_status": {
    "spec_type": "JoinSpec",
    "correlation_key_field": "patient_id",
    "correlation_key_value": "12345",
    "time_window_seconds": 300,
    "elapsed_seconds": 120,
    "remaining_seconds": 180,
    "urgency": "normal",
    "required_inputs": [
      {
        "type": "XRayImage",
        "status": "received",
        "received_at": "2025-10-13T14:32:00Z",
        "age_seconds": 180
      },
      {
        "type": "LabResults",
        "status": "waiting",
        "timeout_at": "2025-10-13T14:37:00Z"
      }
    ],
    "display_state": {
      "status_text": "Waiting (1/2)",
      "status_color": "yellow",
      "progress_percent": 40,
      "urgency_level": "normal"
    }
  }
}
```

**For BatchSpec Collecting State**:

```json
{
  "event": "agent_state_update",
  "timestamp": "2025-10-13T14:35:12Z",
  "agent_id": "payment_processor_1",
  "state": "collecting_batch",
  "batch_status": {
    "spec_type": "BatchSpec",
    "target_size": 25,
    "current_size": 15,
    "timeout_seconds": 30,
    "elapsed_seconds": 18,
    "remaining_seconds": 12,
    "urgency": "medium",
    "collection_rate": 2.3,
    "items_collected": [
      {
        "type": "Order",
        "order_id": "1001",
        "amount": 45.99,
        "collected_at": "2025-10-13T14:34:54Z"
      }
    ],
    "aggregates": {
      "total_amount": 1245.50,
      "estimated_savings": 3.00,
      "avg_order_value": 83.03
    },
    "display_state": {
      "status_text": "Collecting (15/25)",
      "status_color": "yellow",
      "progress_percent": 60,
      "urgency_level": "medium",
      "primary_metric": "15/25 orders",
      "secondary_metric": "12s OR 10 more",
      "tertiary_metric": "$1,245.50 total"
    }
  }
}
```

### Display State Computation (Backend)

**Urgency Levels**:

```python
def compute_urgency(elapsed: float, total: float) -> str:
    """Compute urgency level for color-coding"""
    percent_elapsed = (elapsed / total) * 100

    if percent_elapsed < 50:
        return "low"        # Green/Light yellow
    elif percent_elapsed < 75:
        return "normal"     # Yellow
    elif percent_elapsed < 90:
        return "medium"     # Amber/Orange
    else:
        return "high"       # Dark orange/Red
```

**Status Text Templates**:

```python
# JoinSpec
"Waiting ({received}/{required})"
"Waiting for {missing_type}"

# BatchSpec
"Collecting ({current}/{target})"
"Collecting ({current} items)"
```

**Progress Percent**:

```python
# For JoinSpec (time-based)
progress_percent = (elapsed_seconds / time_window_seconds) * 100

# For BatchSpec (size-based, primary)
progress_percent = (current_size / target_size) * 100

# For BatchSpec (time-based, secondary)
time_progress = (elapsed_seconds / timeout_seconds) * 100
```

---

### REST API Endpoints

**Get Agent State**:
```
GET /api/agents/{agent_id}/state

Response:
{
  "agent_id": "radiologist_1",
  "state": "waiting_for_join",
  "join_status": { ... },
  "last_updated": "2025-10-13T14:35:00Z"
}
```

**Get Waiting Agents** (Filtered):
```
GET /api/agents?state=waiting_for_join

Response:
{
  "agents": [
    { "agent_id": "radiologist_1", ... },
    { "agent_id": "radiologist_2", ... }
  ],
  "total": 2
}
```

**Get Batch Details**:
```
GET /api/agents/{agent_id}/batch/current

Response:
{
  "batch_id": "batch_47",
  "current_size": 15,
  "target_size": 25,
  "items": [ ... ],
  "aggregates": { ... }
}
```

**Force Actions** (Debugging):
```
POST /api/agents/{agent_id}/force_flush
POST /api/agents/{agent_id}/cancel_wait
POST /api/agents/{agent_id}/force_match

Response:
{
  "action": "force_flush",
  "success": true,
  "batch_id": "batch_47",
  "items_flushed": 15
}
```

---

### Historical Data

**Track Wait Duration**:
```json
{
  "agent_id": "radiologist_1",
  "correlation_key": "patient_id:12345",
  "wait_started": "2025-10-13T14:32:00Z",
  "wait_ended": "2025-10-13T14:35:30Z",
  "wait_duration_seconds": 210,
  "outcome": "matched" | "timeout" | "cancelled",
  "inputs_received": {
    "XRayImage": "2025-10-13T14:32:00Z",
    "LabResults": "2025-10-13T14:35:30Z"
  }
}
```

**Batch Statistics**:
```json
{
  "agent_id": "payment_processor_1",
  "batch_id": "batch_47",
  "started": "2025-10-13T14:34:30Z",
  "flushed": "2025-10-13T14:35:12Z",
  "duration_seconds": 42,
  "flush_reason": "timeout",
  "target_size": 25,
  "actual_size": 15,
  "fill_rate": 0.60
}
```

---

## Recommendations

### Critical (Implement First)

**1. Color-Coded State System**
- Adopt industry-standard colors (green/blue/yellow/red)
- Use color intensity for urgency (light→dark as timeout approaches)
- Include icons/patterns for accessibility
- **Backend provides**: `display_state.status_color` and `display_state.urgency_level`

**2. Dual Progress Indicators for Batches**
- Primary: Count progress (15/25 orders)
- Secondary: Time remaining (12s until flush)
- Show whichever condition is closer to triggering
- **Backend provides**: `display_state.primary_metric`, `secondary_metric`

**3. Explicit Correlation Key Display**
- Show correlation key value prominently ("patient_id: 12345")
- List which inputs received vs waiting
- Timeline visualization for time window
- **Backend provides**: `correlation_key_value`, `required_inputs[]`

**4. Backend-Computed Display State**
- Frontend should NOT compute urgency, progress, or display text
- Backend sends ready-to-display state in every update
- Reduces frontend complexity, ensures consistency
- **Backend provides**: `display_state` object with all computed values

**5. Real-Time WebSocket Updates**
- Push state updates every 1-2 seconds during waiting
- Include timestamp for staleness detection
- Batch updates when multiple agents change
- **Backend provides**: WebSocket event stream

---

### High Priority (Implement Soon)

**6. Detail View on Demand**
- Click agent card to expand full details
- Show raw correlation keys, timestamps, configurations
- Provide debug actions (force flush, cancel wait)
- **Backend provides**: Full state object via REST API

**7. Historical Wait Analytics**
- Show typical wait duration for this agent
- Graph distribution: "Usually matches in 2-3 minutes"
- Identify agents with frequent timeouts
- **Backend provides**: Aggregate statistics API

**8. Filterable Agent List**
- Filter by state (waiting, running, idle)
- Search by correlation key
- Sort by urgency or wait duration
- **Backend provides**: Filtered list endpoint

**9. Batch Content Preview**
- Show first 5 items in current batch
- Aggregate metrics (total amount, count)
- Estimated cost savings from batching
- **Backend provides**: `items_collected[]` with aggregates

**10. Timeline Visualization**
- Visual timeline for JoinSpec time windows
- Mark: first input, current time, timeout
- Show elapsed vs remaining proportionally
- **Frontend renders** using backend-provided timestamps

---

### Nice to Have (Future Enhancements)

**11. Predictive Wait Times**
- ML model predicts: "LabResults typically arrive in 90s"
- Anomaly detection: "Unusual delay for this correlation key"
- **Backend provides**: Predictions based on historical data

**12. Interactive Force Actions**
- Button: "Force flush now" (for debugging)
- Button: "Skip this correlation" (move on)
- Confirm dialogs with impact explanation
- **Backend provides**: Action endpoints with validation

**13. Notification System**
- Alert if agent waiting > expected time
- Notify when batch flush occurs
- Configurable thresholds per agent
- **Backend provides**: Alert rules and webhook delivery

**14. Correlation Debugging**
- Show all items with same correlation key (across time)
- Highlight mismatches: "XRay for patient_id=123, Lab for patient_id=124"
- Suggest fixes for common issues
- **Backend provides**: Correlation key index and search

**15. Batch Performance Metrics**
- Cost savings per batch (vs individual processing)
- Average batch size over time
- Flush reason distribution (size vs timeout)
- ROI of batching feature
- **Backend provides**: Analytics aggregations

---

## Implementation Phases

### Phase 1: Core Waiting States (2 weeks)
**Goal**: Display basic waiting states with progress

**Deliverables**:
- Agent card with 6 states (idle, waiting, collecting, processing, completed, error)
- Color-coded state system
- Progress indicators for JoinSpec (time) and BatchSpec (count + time)
- Real-time WebSocket updates
- Backend display_state computation

**Metrics**:
- Agent state visible within 100ms of update
- Accurate progress percentage (±1%)
- Color correctly reflects urgency

---

### Phase 2: Detail Views (1 week)
**Goal**: Provide drill-down details for waiting agents

**Deliverables**:
- Expandable agent card detail view
- Full correlation key and input status display
- Timeline visualization for time windows
- Batch content list with aggregates
- REST API for detail retrieval

**Metrics**:
- Detail view loads <500ms
- All configuration parameters visible
- Timeline accurately represents time window

---

### Phase 3: Filtering & Search (1 week)
**Goal**: Help users find agents by state

**Deliverables**:
- Filter by agent state
- Search by correlation key
- Sort by urgency or wait duration
- Group by agent type
- Filtered list endpoint

**Metrics**:
- Filter applies <200ms
- Search handles 1000+ agents
- Sort stable and performant

---

### Phase 4: Historical Analytics (2 weeks)
**Goal**: Provide insights into wait patterns

**Deliverables**:
- Wait duration statistics per agent
- Batch fill rate analytics
- Timeout frequency analysis
- Performance trend graphs
- Analytics API endpoints

**Metrics**:
- Historical data queryable back 30 days
- Aggregations computed <1s
- Trends actionable (identify slow agents)

---

### Phase 5: Advanced Features (2 weeks)
**Goal**: Debugging and prediction tools

**Deliverables**:
- Force action buttons (flush, cancel, skip)
- Predictive wait time estimates
- Anomaly detection alerts
- Correlation debugging tools
- Notification system

**Metrics**:
- Force actions execute <1s
- Predictions accurate within 20%
- Anomalies detected within 1 minute

---

## Design Mockups (ASCII)

### Agent Card - JoinSpec Waiting

```
┌─────────────────────────────────────────┐
│ 🤖 radiologist                    [≡]  │ ← Header with menu
├─────────────────────────────────────────┤
│ ⏳ Waiting (1/2)              ⚡ Normal │ ← Status + urgency
├─────────────────────────────────────────┤
│ Correlation: patient_id = 12345         │ ← Correlation key
│                                         │
│ ✓ XRayImage           2m ago           │ ← Received input
│ ⏱ LabResults          3:15 left        │ ← Waiting for input
│                                         │
│ Time Window:                            │
│ [███████░░░░░░░░░░] 2:00 / 5:00        │ ← Progress bar
│                                         │
└─────────────────────────────────────────┘
```

### Agent Card - BatchSpec Collecting

```
┌─────────────────────────────────────────┐
│ 🤖 payment_processor          [≡]      │
├─────────────────────────────────────────┤
│ 📦 Collecting               ⚡ Medium   │
├─────────────────────────────────────────┤
│ Batch Progress:                         │
│ [████████░░░░░░] 15 / 25 orders (60%)  │
│                                         │
│ Flush Condition:                        │
│ ⏱ 12s OR 10 more orders (whichever first)│
│                                         │
│ Metrics:                                │
│ • Total: $1,245.50                      │
│ • Rate: 2.3 items/sec                   │
│ • Savings: $3.00 vs individual          │
│                                         │
└─────────────────────────────────────────┘
```

### Detail View - JoinSpec (Expanded)

```
┌────────────────────────────────────────────────────┐
│ Agent: radiologist                          [Close] │
├────────────────────────────────────────────────────┤
│ Status: Waiting for correlation                    │
│ Started: 14:32:00 (3m 15s ago)                     │
│ Timeout: 14:37:00 (1m 45s remaining)               │
├────────────────────────────────────────────────────┤
│ JoinSpec Configuration:                            │
│ • Correlation: by patient_id                       │
│ • Window: 300 seconds (5 minutes)                  │
│ • Strategy: all_of (require all inputs)            │
│ • Required: XRayImage, LabResults                  │
├────────────────────────────────────────────────────┤
│ Current Match: patient_id = 12345                  │
│                                                    │
│ ✓ XRayImage                                        │
│   Received: 14:32:15 (2m 45s ago)                  │
│   exam_type: chest_xray                            │
│   image_quality: high                              │
│   technician_notes: "Clear lung fields..."         │
│                                                    │
│ ⏳ LabResults (waiting)                            │
│   Timeout in: 1m 45s                               │
│   Expected fields: blood_work, markers             │
│                                                    │
│ Timeline:                                          │
│ ┌──────────────────────────────────────────┐      │
│ │ 14:32:00    14:35:15    14:37:00         │      │
│ │    ▼           ▼           ▼             │      │
│ │ [━━X━━━━━━━━━━⬤━━━━━━━━━━T]             │      │
│ │  Start    Now(65%)     Timeout           │      │
│ └──────────────────────────────────────────┘      │
│                                                    │
│ Historical Context:                                │
│ • Typical wait: 2m 30s                             │
│ • Success rate: 94% (47 of 50 recent)              │
│ • Timeout rate: 6%                                 │
│                                                    │
│ Actions:                                           │
│ [Force Match] [Cancel Wait] [View Similar]        │
└────────────────────────────────────────────────────┘
```

### Dashboard Overview

```
┌──────────────────────────────────────────────────────────────┐
│ Flock Dashboard                          [⚙️ Settings] [👤]  │
├──────────────────────────────────────────────────────────────┤
│ ┌────────────┬───────────────────────────────┬──────────────┐│
│ │ Agents (8) │ Status Overview               │ Filters      ││
│ │            │                               │              ││
│ │ 🟢 Running │ ┌───────────────────────────┐ │ State:       ││
│ │ (3)        │ │  Workflow Visualization   │ │ [All  ▼]    ││
│ │            │ │                           │ │              ││
│ │ 🟡 Waiting │ │  ┌─┐      ┌─┐      ┌─┐   │ │ Search:      ││
│ │ (2)        │ │  │A│─────▶│B│─────▶│C│   │ │ [patient_id] ││
│ │            │ │  └─┘      └─┘      └─┘   │ │              ││
│ │ ⚪ Idle   │ │    │        │              │ │ Sort by:     ││
│ │ (3)        │ │    ▼        ▼              │ │ [Urgency ▼] ││
│ │            │ │  ┌─┐      ┌─┐              │ │              ││
│ │ ❌ Error  │ │  │D│      │E│              │ │              ││
│ │ (0)        │ │  └─┘      └─┘              │ │              ││
│ │            │ └───────────────────────────┘ │              ││
│ ├────────────┤                               │              ││
│ │            │ Real-time Metrics             │              ││
│ │ Agent List │ ┌───────────────────────────┐ │              ││
│ │            │ │ Throughput: 15.3 msg/sec  │ │              ││
│ │ radiolog.. │ │ Avg Wait: 2m 15s          │ │              ││
│ │ ⏳ Wait 1/2│ │ Batch Savings: $45.00/hr  │ │              ││
│ │            │ └───────────────────────────┘ │              ││
│ │ payment_.. │                               │              ││
│ │ 📦 15/25   │                               │              ││
│ │            │                               │              ││
│ │ analyzer   │                               │              ││
│ │ 🔄 Running │                               │              ││
│ │            │                               │              ││
│ └────────────┴───────────────────────────────┴──────────────┘│
├──────────────────────────────────────────────────────────────┤
│ Status: Connected | Last update: 0.5s ago | 3 active agents │
└──────────────────────────────────────────────────────────────┘
```

---

## References

### Industry Tools Analyzed

1. **Apache Airflow**
   - Docs: https://airflow.apache.org/docs/apache-airflow/stable/ui.html
   - State model: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html
   - Key insight: Color-coded task states in grid view

2. **Prefect**
   - Docs: https://docs.prefect.io/latest/concepts/flows/
   - Key insight: Timeline view for flow run visualization

3. **Temporal**
   - Docs: https://docs.temporal.io/workflow-execution
   - Key insight: Long-running wait state management

4. **Confluent Control Center** (Kafka)
   - Key insight: Consumer lag visualization with numeric indicators

5. **n8n**
   - Docs: https://docs.n8n.io/workflows/
   - Wait node: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.wait/
   - Key insight: Multiple wait types clearly differentiated

6. **Dagster**
   - Docs: https://docs.dagster.io/guides/automate/declarative-automation
   - Key insight: Dependency-based waiting visualization

### UX Research Sources

7. **Nielsen Norman Group - Progress Indicators**
   - Article: https://www.nngroup.com/articles/progress-indicators/
   - Key insight: 1s/10s timing thresholds, percent-done animation

8. **Smashing Magazine - Real-Time Dashboards**
   - Key insight: 200-400ms transition timing, color-coded states

9. **Pencil & Paper - Loading UX Patterns**
   - Key insight: Determinate vs indeterminate indicators

10. **RxJS Documentation**
    - Docs: https://rxjs.dev/
    - Key insight: Operator-based stream correlation patterns

### Technical Standards

11. **WCAG 2.1** (Web Content Accessibility Guidelines)
    - Color contrast: 4.5:1 minimum
    - Non-color indicators required

12. **Material Design - Progress Indicators**
    - Timing: Smooth 200-400ms transitions
    - Types: Linear, circular, determinate, indeterminate

---

## Appendices

### Appendix A: Color Palette Recommendations

**Primary State Colors** (Tailwind CSS):
```css
/* Success */
.state-success { background-color: #10B981; } /* green-500 */

/* Running */
.state-running { background-color: #3B82F6; } /* blue-500 */

/* Waiting */
.state-waiting { background-color: #F59E0B; } /* amber-500 */

/* Error */
.state-error { background-color: #EF4444; } /* red-500 */

/* Idle */
.state-idle { background-color: #9CA3AF; } /* gray-400 */
```

**Urgency Gradient** (for time-based intensity):
```css
/* Low urgency (>80% time remaining) */
.urgency-low { background-color: #FEF3C7; } /* amber-100 */

/* Normal (40-80%) */
.urgency-normal { background-color: #FCD34D; } /* amber-300 */

/* Medium (20-40%) */
.urgency-medium { background-color: #F59E0B; } /* amber-500 */

/* High (<20%) */
.urgency-high { background-color: #F97316; } /* orange-500 */

/* Critical (<5%) */
.urgency-critical { background-color: #EF4444; } /* red-500 */
```

---

### Appendix B: Sample WebSocket Payloads

**Initial Connection**:
```json
{
  "type": "connection_established",
  "client_id": "dash_abc123",
  "timestamp": "2025-10-13T14:30:00Z",
  "subscriptions": ["agent_state_updates", "batch_events"]
}
```

**Agent State Update** (JoinSpec):
```json
{
  "type": "agent_state_update",
  "timestamp": "2025-10-13T14:35:15.234Z",
  "agent_id": "radiologist_1",
  "agent_name": "radiologist",
  "state": "waiting_for_join",
  "join_status": {
    "spec_type": "JoinSpec",
    "correlation_key_field": "patient_id",
    "correlation_key_value": "12345",
    "time_window_seconds": 300,
    "started_at": "2025-10-13T14:32:00Z",
    "timeout_at": "2025-10-13T14:37:00Z",
    "elapsed_seconds": 195,
    "remaining_seconds": 105,
    "progress_percent": 65,
    "urgency": "normal",
    "required_inputs": [
      {
        "type": "XRayImage",
        "status": "received",
        "received_at": "2025-10-13T14:32:15Z",
        "age_seconds": 180,
        "payload_summary": {
          "exam_type": "chest_xray",
          "image_quality": "high"
        }
      },
      {
        "type": "LabResults",
        "status": "waiting",
        "timeout_in_seconds": 105
      }
    ],
    "display_state": {
      "status_text": "Waiting (1/2)",
      "status_subtext": "patient_id: 12345",
      "status_color": "yellow",
      "urgency_level": "normal",
      "progress_percent": 65,
      "primary_metric": "3:15 remaining",
      "secondary_metric": "Waiting for LabResults"
    }
  }
}
```

**Batch Update** (BatchSpec):
```json
{
  "type": "agent_state_update",
  "timestamp": "2025-10-13T14:35:12.456Z",
  "agent_id": "payment_processor_1",
  "agent_name": "payment_processor",
  "state": "collecting_batch",
  "batch_status": {
    "spec_type": "BatchSpec",
    "batch_id": "batch_47",
    "target_size": 25,
    "current_size": 15,
    "timeout_seconds": 30,
    "started_at": "2025-10-13T14:34:30Z",
    "flush_at": "2025-10-13T14:35:00Z",
    "elapsed_seconds": 42,
    "remaining_seconds": 18,
    "progress_percent": 60,
    "urgency": "medium",
    "collection_rate_per_sec": 2.3,
    "items_needed": 10,
    "aggregates": {
      "total_amount": 1245.50,
      "avg_amount": 83.03,
      "estimated_savings": 3.00,
      "currency": "USD"
    },
    "display_state": {
      "status_text": "Collecting (15/25)",
      "status_subtext": "Batch #47",
      "status_color": "yellow",
      "urgency_level": "medium",
      "progress_percent": 60,
      "primary_metric": "15/25 orders",
      "secondary_metric": "18s OR 10 more",
      "tertiary_metric": "$1,245.50 total"
    }
  }
}
```

**Batch Flushed** (Event):
```json
{
  "type": "batch_flushed",
  "timestamp": "2025-10-13T14:35:12.789Z",
  "agent_id": "payment_processor_1",
  "batch_id": "batch_47",
  "flush_reason": "timeout",
  "target_size": 25,
  "actual_size": 15,
  "duration_seconds": 42,
  "aggregates": {
    "total_amount": 1245.50,
    "savings": 3.00
  }
}
```

**Join Matched** (Event):
```json
{
  "type": "join_matched",
  "timestamp": "2025-10-13T14:35:30.123Z",
  "agent_id": "radiologist_1",
  "correlation_key_value": "12345",
  "wait_duration_seconds": 210,
  "matched_inputs": [
    {
      "type": "XRayImage",
      "received_at": "2025-10-13T14:32:15Z"
    },
    {
      "type": "LabResults",
      "received_at": "2025-10-13T14:35:30Z"
    }
  ]
}
```

**Join Timeout** (Event):
```json
{
  "type": "join_timeout",
  "timestamp": "2025-10-13T14:37:00.000Z",
  "agent_id": "radiologist_1",
  "correlation_key_value": "12345",
  "wait_duration_seconds": 300,
  "received_inputs": [
    {
      "type": "XRayImage",
      "received_at": "2025-10-13T14:32:15Z"
    }
  ],
  "missing_inputs": ["LabResults"],
  "action_taken": "discarded"
}
```

---

### Appendix C: Backend State Machine

**Agent States**:

```python
from enum import Enum

class AgentState(str, Enum):
    """Agent execution states"""
    IDLE = "idle"                      # No activity
    WAITING_FOR_JOIN = "waiting_for_join"  # JoinSpec waiting
    COLLECTING_BATCH = "collecting_batch"  # BatchSpec collecting
    PROCESSING = "processing"          # Actively running
    COMPLETED = "completed"            # Finished successfully
    ERROR = "error"                    # Error occurred
    TIMEOUT = "timeout"                # Timeout expired
```

**State Transitions**:

```
IDLE ──────────────────────────────────────────────┐
  │                                                 │
  │ (artifact arrives)                              │
  ▼                                                 │
WAITING_FOR_JOIN ──(all inputs received)──┐        │
  │                                        │        │
  │ (timeout)                              ▼        │
  ├────────────────────────────────▶ PROCESSING ───┤
  │                                        │        │
COLLECTING_BATCH ──(size or timeout)──────┘        │
  │                                                 │
  │                                                 ▼
  │                                            COMPLETED
  │                                                 │
  └─────────────────(error)────────▶ ERROR ◀───────┘
```

---

### Appendix D: Performance Benchmarks

**Target Metrics**:

| Metric | Target | Critical |
|--------|--------|----------|
| WebSocket message latency | <100ms | <500ms |
| State update frequency | 1-2 Hz | 0.5 Hz |
| UI render time (agent card) | <16ms | <100ms |
| Dashboard load time | <1s | <3s |
| Detail view load time | <500ms | <1s |
| Filter/search response | <200ms | <1s |
| Historical query response | <1s | <3s |

**Optimization Strategies**:
- WebSocket connection pooling
- Backend state computation (not frontend)
- Throttled updates (max 2 Hz)
- Virtual scrolling for agent list (>100 agents)
- Lazy loading for detail views
- Cached historical aggregations

---

## Conclusion

This research analyzed 6 industry-leading tools (Airflow, Prefect, Temporal, Kafka monitoring, n8n, Dagster) and identified consistent UX patterns for visualizing waiting states and batch collection:

**Key Patterns**:
1. **Color-coded state systems** (green/blue/yellow/red)
2. **Dual indicators** for batch collection (count + time)
3. **Timeline visualizations** for time windows
4. **Backend-computed display state** (minimize frontend logic)
5. **Real-time updates** via WebSocket

**Critical Backend Requirements**:
- Compute `display_state` object with ready-to-render values
- Provide urgency levels based on time/size thresholds
- Push real-time updates every 1-2 seconds
- Expose REST API for detail views
- Track historical wait statistics

**Next Steps**:
1. Review this research with design team
2. Create high-fidelity mockups based on recommendations
3. Implement backend `display_state` computation
4. Build frontend components in phases (core → detail → analytics)
5. User testing with real JoinSpec/BatchSpec examples

---

**Document Status**: Research Complete ✅
**Ready for**: Design Phase
**Estimated Implementation**: 8 weeks (5 phases)

**Prepared by**: User Research Analysis
**Date**: October 13, 2025
