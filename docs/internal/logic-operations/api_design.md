# Logic Operations API Design
## AND Gates, Batching, and Time Windows for Flock 0.6+

**Document Version:** 1.0
**Date:** October 13, 2025
**Status:** 🚧 Proposal (Features Not Yet Implemented)
**Target:** Flock v0.6 (JoinSpec), v0.7 (BatchSpec)

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Industry Comparison](#industry-comparison)
4. [Proposed API Design](#proposed-api-design)
5. [Real-World Examples](#real-world-examples)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Decision Framework](#decision-framework)

---

## 🎯 Executive Summary

### The Problem

**Flock 0.5 has a critical gap:** `.consumes(A, B)` behaves as an **OR gate** but developers expect an **AND gate**. Two features are documented but not implemented:
- **JoinSpec** - Correlated AND gates with time windows
- **BatchSpec** - Batch processing for cost optimization

### The Solution

This document proposes a clean, intuitive API that:
- ✅ Makes common cases easy (simple AND, simple OR)
- ✅ Makes complex cases possible (correlation, batching, time windows)
- ✅ Aligns with developer intuition and industry standards
- ✅ Prevents silent failures and footguns

### Key Recommendations

| Feature | Recommendation | Priority |
|---------|---------------|----------|
| **Simple AND gate** | `.consumes(A, B)` = AND (change default) | 🔴 Critical |
| **Simple OR gate** | `.consumes(A).consumes(B)` = OR (chaining) | 🔴 Critical |
| **Correlated AND** | `join=JoinSpec(by=..., within=...)` | 🔴 Critical |
| **Batching** | `batch=BatchSpec(size=..., timeout=...)` | 🟡 High |
| **Explicit methods** | `consumes_all()`, `consumes_any()` (optional) | 🟢 Nice-to-have |

---

## 📊 Current State Analysis

### What Exists Today (v0.5)

**Data Structures Defined:**
```python
@dataclass
class JoinSpec:
    kind: str  # e.g., "all_of"
    window: float
    by: Callable[[Artifact], Any] | None = None

@dataclass
class BatchSpec:
    size: int
    within: float
    by: Callable[[Artifact], Any] | None = None
```

**Current Behavior:**
```python
# Developer writes:
agent.consumes(TypeA, TypeB)

# Developer expects: AND gate (wait for both)
# Actual behavior: OR gate (trigger on either)
# Result: Silent failure! 💥
```

### The Footgun Example

**From `examples/02-dashboard/09_debate_club.py`:**
```python
judge = (
    flock.agent("judge")
    .description("Evaluates BOTH arguments and declares a winner")
    .consumes(ProArgument, ContraArgument)  # ← Expects AND, gets OR!
    .publishes(DebateVerdict)
)
```

**What happens:**
1. ProArgument published → Judge triggered (gets only ProArgument)
2. ContraArgument published → Judge triggered AGAIN (gets only ContraArgument)
3. Judge runs twice with partial data (works by accident due to DSPy engine forgiveness)

**Impact:** HIGH - Core multi-agent workflows silently broken

---

## 🌍 Industry Comparison

### How Other Frameworks Handle Logic Operations

#### 1. Apache Airflow (Workflow Orchestration)

**Approach:** List of dependencies = AND by default

```python
# AND gate (default)
task_c.set_upstream([task_a, task_b])
# task_c runs when BOTH task_a AND task_b complete

# OR gate (explicit trigger rule)
task_c = BashOperator(
    task_id='task_c',
    trigger_rule='one_success'  # Explicit OR
)
```

**Lessons:**
- ✅ AND is the intuitive default
- ✅ OR requires explicit configuration
- ✅ Named trigger rules (clear intent)

---

#### 2. RxJS (Reactive Extensions)

**Approach:** Explicit operators for everything

```javascript
// AND gate - explicit combineLatest
combineLatest([stream_a, stream_b]).subscribe(([a, b]) => {
    // Both values available
});

// OR gate - explicit merge
merge([stream_a, stream_b]).subscribe(value => {
    // Whichever comes first
});

// Batching - explicit buffer operators
stream.pipe(
    bufferTime(5000),  // 5 second window
    bufferCount(10)    // Or 10 items
).subscribe(batch => {
    // Array of items
});
```

**Lessons:**
- ✅ No ambiguity - everything explicit
- ✅ Rich operator library for complex patterns
- ⚠️ Steeper learning curve

---

#### 3. Temporal (Distributed Workflows)

**Approach:** Explicit Promise.all vs Promise.race

```typescript
// AND gate - Promise.all
const [resultA, resultB] = await Promise.all([
    workflow.executeActivity(activityA),
    workflow.executeActivity(activityB)
]);

// OR gate - Promise.race
const firstResult = await Promise.race([
    workflow.executeActivity(activityA),
    workflow.executeActivity(activityB)
]);
```

**Lessons:**
- ✅ Leverages language primitives (Promise semantics)
- ✅ Clear intent (all vs race)
- ✅ Familiar to developers

---

#### 4. AWS Step Functions (State Machines)

**Approach:** Explicit parallel state

```json
{
  "Type": "Parallel",
  "Branches": [
    {"StartAt": "TaskA", "States": {...}},
    {"StartAt": "TaskB", "States": {...}}
  ],
  "Next": "JoinResults"
}
```

**Lessons:**
- ✅ Visual representation (DAG)
- ✅ Explicit parallel blocks
- ⚠️ Verbose JSON configuration

---

#### 5. Prefect (Modern Workflow Engine)

**Approach:** Depends-on list = AND, multiple upstreams explicit

```python
from prefect import flow, task

@task
def task_c(a_result, b_result):
    # Gets both results - AND gate
    pass

@flow
def my_flow():
    a = task_a()
    b = task_b()
    c = task_c(a, b)  # Depends on both (AND)
```

**Lessons:**
- ✅ Function arguments make dependencies explicit
- ✅ Type-safe coordination
- ✅ AND is natural default

---

### Industry Consensus

| Framework | AND Default | OR Explicit | Batching | Time Windows |
|-----------|-------------|-------------|----------|--------------|
| **Airflow** | ✅ Yes | ⚠️ Trigger rule | ❌ No | ❌ No |
| **RxJS** | ⚠️ Explicit | ⚠️ Explicit | ✅ bufferTime/Count | ✅ window operators |
| **Temporal** | ✅ Promise.all | ✅ Promise.race | ⚠️ Manual | ✅ withTimeout |
| **Step Functions** | ✅ Parallel | ⚠️ Choice state | ❌ No | ⚠️ Wait state |
| **Prefect** | ✅ Args | ⚠️ Manual | ⚠️ Task groups | ❌ No |

**Key Insight:** **AND is the universal default for multi-dependency coordination**

---

## 🎨 Proposed API Design

### Design Principles

1. **Principle of Least Surprise** - Natural language alignment
2. **Safe by Default** - Correct behavior without docs
3. **Progressive Disclosure** - Simple cases simple, complex cases possible
4. **Type Safety** - Leverage Pydantic for validation
5. **Performance First** - Batching for cost, correlation for correctness

---

### Tier 1: Simple Cases (90% of Use Cases)

#### Simple AND Gate (Recommended Default)

```python
# Multiple types in single consume = AND
diagnostician.consumes(XRayAnalysis, LabResults)
```

**Semantics:**
- Agent triggered when BOTH artifacts are available
- Agent receives tuple: `(XRayAnalysis, LabResults)`
- No correlation, no time constraint
- Order-independent (first-come-first-serve)

**Agent Signature:**
```python
async def diagnose(
    ctx: Context,
    xray: XRayAnalysis,
    labs: LabResults
) -> list[Diagnosis]:
    # Both artifacts available
    return [Diagnosis(...)]
```

---

#### Simple OR Gate (Multiple Consumes)

```python
# Multiple consume calls = OR
error_handler
    .consumes(ValidationError)
    .consumes(NetworkError)
    .consumes(TimeoutError)
```

**Semantics:**
- Agent triggered when ANY artifact type published
- Agent receives single artifact (not tuple)
- Each subscription independent

**Agent Signature:**
```python
async def handle_error(
    ctx: Context,
    error: ValidationError | NetworkError | TimeoutError
) -> list[ErrorReport]:
    # One error at a time
    return [ErrorReport(...)]
```

---

### Tier 2: Advanced Coordination (8% of Use Cases)

#### Correlated AND with Time Window (JoinSpec)

```python
# Same patient, within 1 hour
diagnostician.consumes(
    XRayAnalysis,
    LabResults,
    join=JoinSpec(
        by=lambda artifact: artifact.patient_id,
        within=timedelta(hours=1)
    )
)
```

**Semantics:**
- Wait for BOTH artifacts
- Must have **same correlation key** (patient_id)
- Must arrive **within time window** (1 hour of each other)
- If timeout: discard oldest, keep waiting for new matches

**Agent Signature:**
```python
async def diagnose(
    ctx: Context,
    xray: XRayAnalysis,      # Same patient_id
    labs: LabResults         # Same patient_id, within 1 hour
) -> list[Diagnosis]:
    assert xray.patient_id == labs.patient_id  # Guaranteed by framework
    return [Diagnosis(...)]
```

**Use Cases:**
- Healthcare: Same patient's multi-modal data
- Trading: Same stock's price + sentiment signals
- E-commerce: Same user's browse + purchase events
- Manufacturing: Same batch's quality checks

---

#### Batching for Performance (BatchSpec)

```python
# Process up to 50 events, or every 30 seconds
processor.consumes(
    Event,
    batch=BatchSpec(
        size=50,
        timeout=timedelta(seconds=30)
    )
)
```

**Semantics:**
- Collect artifacts into batches
- Flush when **count reaches size** OR **timeout elapses**
- Whichever comes first triggers delivery
- Timeout resets after each flush

**Agent Signature:**
```python
async def process_batch(
    ctx: Context,
    events: list[Event]  # Batch of 1-50 events
) -> list[Result]:
    # Bulk processing for efficiency
    return [process_one(e) for e in events]
```

**Use Cases:**
- Cost optimization: Batch LLM API calls
- Performance: Bulk database inserts
- Rate limiting: Throttle downstream services
- Analytics: Aggregate metrics

---

### Tier 3: Complex Patterns (2% of Use Cases)

#### Batched Correlated Joins

```python
# Batch of correlated pairs
risk_analyzer.consumes(
    Transaction,
    AccountSnapshot,
    join=JoinSpec(
        by=lambda x: x.account_id,
        within=timedelta(minutes=10)
    ),
    batch=BatchSpec(
        size=100,
        timeout=timedelta(minutes=1)
    )
)
```

**Semantics:**
- Correlate Transaction + AccountSnapshot by account_id
- Pairs must arrive within 10 minutes of each other
- Collect up to 100 pairs or flush every minute
- Agent receives batch of correlated pairs

**Agent Signature:**
```python
async def analyze_risk(
    ctx: Context,
    pairs: list[tuple[Transaction, AccountSnapshot]]
) -> list[RiskAlert]:
    # Batch of correlated pairs
    return [analyze_pair(txn, snapshot) for txn, snapshot in pairs]
```

---

### Alternative: Explicit Methods (Optional Enhancement)

**If we want to avoid breaking changes:**

```python
# Explicit AND
agent.consumes_all(TypeA, TypeB)

# Explicit OR
agent.consumes_any(TypeA, TypeB)

# Current .consumes() deprecated
agent.consumes(TypeA, TypeB)  # ⚠️ Warning: Ambiguous! Use consumes_all or consumes_any
```

**Trade-offs:**
- ✅ Zero breaking changes
- ✅ Crystal-clear intent
- ⚠️ More verbose
- ⚠️ Two ways to do the same thing

---

## 💼 Real-World Examples

### Example 1: Healthcare Diagnostic System

**Scenario:** Multi-modal patient diagnosis requiring coordinated data from multiple sources.

#### Current Implementation (Broken - OR Gate)

```python
# ❌ CURRENT: Silently broken
diagnostician = (
    flock.agent("diagnostician")
    .consumes(XRayAnalysis, LabResults)  # Expects AND, gets OR!
    .publishes(Diagnosis)
)

# What happens:
# 1. XRay published → Diagnostician runs with only XRay (incomplete!)
# 2. Labs published → Diagnostician runs AGAIN with only Labs (incomplete!)
# 3. Two incomplete diagnoses produced
```

#### Proposed Implementation (Fixed - Simple AND)

```python
# ✅ PROPOSED: Clear AND semantics
diagnostician = (
    flock.agent("diagnostician")
    .consumes(XRayAnalysis, LabResults)  # AND gate - waits for both
    .publishes(Diagnosis)
)

async def diagnose(
    ctx: Context,
    xray: XRayAnalysis,
    labs: LabResults
) -> list[Diagnosis]:
    # Both available together!
    return [Diagnosis(
        condition=analyze_both(xray, labs),
        confidence=0.95
    )]
```

#### Advanced: Same Patient, Recent Data (Correlated AND)

```python
# ✅ ADVANCED: Correlated with time constraint
diagnostician = (
    flock.agent("diagnostician")
    .consumes(
        XRayAnalysis,
        LabResults,
        join=JoinSpec(
            by=lambda x: x.patient_id,        # Same patient
            within=timedelta(hours=1)          # Within 1 hour
        )
    )
    .publishes(Diagnosis)
)

# Guarantees:
# - XRay and Labs are from SAME patient
# - Both arrived within 1 hour of each other
# - Stale data (>1 hour apart) discarded
```

---

### Example 2: Financial Trading System

**Scenario:** Execute trades when correlated signals align within time window.

#### Multi-Signal Trading Strategy

```python
@flock_type
class PriceSignal(BaseModel):
    symbol: str
    price: float
    timestamp: datetime
    volume: int

@flock_type
class SentimentSignal(BaseModel):
    symbol: str
    sentiment_score: float  # -1.0 to 1.0
    timestamp: datetime
    source: str

@flock_type
class TradeOrder(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL"]
    quantity: int
    reasoning: str
```

#### Proposed Implementation

```python
# Correlated AND with tight time window
trader = (
    flock.agent("trader")
    .consumes(
        PriceSignal,
        SentimentSignal,
        join=JoinSpec(
            by=lambda x: x.symbol,              # Same stock
            within=timedelta(minutes=5)          # Fresh signals only
        )
    )
    .publishes(TradeOrder)
)

async def execute_trade(
    ctx: Context,
    price: PriceSignal,
    sentiment: SentimentSignal
) -> list[TradeOrder]:
    # Both signals correlated by symbol and recent
    assert price.symbol == sentiment.symbol

    if sentiment.sentiment_score > 0.7 and price.volume > 1000000:
        return [TradeOrder(
            symbol=price.symbol,
            action="BUY",
            quantity=100,
            reasoning=f"Strong sentiment ({sentiment.sentiment_score}) + high volume"
        )]
    return []
```

**Why JoinSpec Matters Here:**
- ❌ Without correlation: Buy AAPL based on TSLA sentiment! (disaster)
- ❌ Without time window: Buy based on yesterday's stale sentiment (bad trade)
- ✅ With JoinSpec: Only trade when fresh correlated signals align (safe)

---

### Example 3: E-Commerce Recommendation Engine

**Scenario:** Batch-process user events for efficient LLM-based recommendations.

#### Cost-Optimized Batch Processing

```python
@flock_type
class UserEvent(BaseModel):
    user_id: str
    event_type: Literal["view", "cart", "purchase", "search"]
    item_id: str
    timestamp: datetime
    session_id: str

@flock_type
class RecommendationSet(BaseModel):
    user_id: str
    recommended_items: list[str]
    reasoning: str
    confidence: float
```

#### Proposed Implementation

```python
# Batch processing for cost efficiency
recommender = (
    flock.agent("recommender")
    .consumes(
        UserEvent,
        batch=BatchSpec(
            size=50,                         # Up to 50 events
            timeout=timedelta(seconds=30)    # Or every 30 seconds
        )
    )
    .publishes(RecommendationSet)
)

async def generate_recommendations(
    ctx: Context,
    events: list[UserEvent]
) -> list[RecommendationSet]:
    # Batch of 1-50 events (grouped by user internally)
    user_events = group_by_user(events)

    recommendations = []
    for user_id, user_event_list in user_events.items():
        # Single LLM call per user (efficient!)
        rec = await analyze_user_behavior(user_event_list)
        recommendations.append(RecommendationSet(
            user_id=user_id,
            recommended_items=rec.items,
            reasoning=rec.reasoning,
            confidence=rec.confidence
        ))

    return recommendations
```

**Cost Savings:**
- ❌ Without batching: 50 individual LLM calls ($0.50)
- ✅ With batching: 1 LLM call for 50 events ($0.02)
- **💰 25x cost reduction!**

---

### Example 4: Manufacturing Quality Control

**Scenario:** Correlate quality checks from multiple stations for same production batch.

#### Multi-Stage Quality Analysis

```python
@flock_type
class VisualInspection(BaseModel):
    batch_id: str
    station: str
    defects_found: list[str]
    timestamp: datetime
    inspector_id: str

@flock_type
class DimensionalCheck(BaseModel):
    batch_id: str
    station: str
    measurements: dict[str, float]
    within_tolerance: bool
    timestamp: datetime

@flock_type
class QualityReport(BaseModel):
    batch_id: str
    passed: bool
    defects: list[str]
    action: Literal["PASS", "REWORK", "SCRAP"]
```

#### Proposed Implementation

```python
# Correlated quality checks for same batch
quality_analyzer = (
    flock.agent("quality_analyzer")
    .consumes(
        VisualInspection,
        DimensionalCheck,
        join=JoinSpec(
            by=lambda x: x.batch_id,           # Same production batch
            within=timedelta(minutes=30)        # Checks within 30 min
        )
    )
    .publishes(QualityReport)
)

async def analyze_quality(
    ctx: Context,
    visual: VisualInspection,
    dimensional: DimensionalCheck
) -> list[QualityReport]:
    # Both checks for same batch, recent
    assert visual.batch_id == dimensional.batch_id

    if visual.defects_found or not dimensional.within_tolerance:
        return [QualityReport(
            batch_id=visual.batch_id,
            passed=False,
            defects=visual.defects_found + ["dimensional_failure"],
            action="REWORK" if len(visual.defects_found) < 3 else "SCRAP"
        )]

    return [QualityReport(
        batch_id=visual.batch_id,
        passed=True,
        defects=[],
        action="PASS"
    )]
```

---

### Example 5: Customer Support Escalation

**Scenario:** OR gate for handling multiple error types with same handler.

#### Polymorphic Error Handling

```python
@flock_type
class ValidationError(BaseModel):
    field: str
    message: str
    user_input: str

@flock_type
class NetworkError(BaseModel):
    endpoint: str
    status_code: int
    retry_count: int

@flock_type
class TimeoutError(BaseModel):
    operation: str
    timeout_seconds: int

@flock_type
class ErrorReport(BaseModel):
    severity: Literal["Low", "Medium", "High", "Critical"]
    message: str
    suggested_action: str
```

#### Proposed Implementation (OR Gate)

```python
# OR gate - handle any error type
error_handler = (
    flock.agent("error_handler")
    .consumes(ValidationError)      # OR
    .consumes(NetworkError)         # OR
    .consumes(TimeoutError)         # OR
    .publishes(ErrorReport)
)

async def handle_error(
    ctx: Context,
    error: ValidationError | NetworkError | TimeoutError
) -> list[ErrorReport]:
    # Receives ONE error at a time
    if isinstance(error, ValidationError):
        return [ErrorReport(
            severity="Low",
            message=f"Invalid input: {error.field}",
            suggested_action="Show user-friendly validation message"
        )]
    elif isinstance(error, NetworkError):
        severity = "High" if error.retry_count > 3 else "Medium"
        return [ErrorReport(
            severity=severity,
            message=f"Network failure: {error.endpoint}",
            suggested_action="Retry with exponential backoff"
        )]
    elif isinstance(error, TimeoutError):
        return [ErrorReport(
            severity="Critical",
            message=f"Operation timeout: {error.operation}",
            suggested_action="Alert ops team"
        )]
```

**Why OR Gate Makes Sense:**
- Different error types, same handling logic
- No correlation needed (errors independent)
- Process each error individually

---

## 🗺️ Implementation Roadmap

### Phase 1: Simple AND Gate (v0.6 - 2-3 weeks)

**Goal:** Make `.consumes(A, B)` behave as AND gate

**Implementation:**
1. Change subscription matching logic to require ALL types present
2. Implement artifact collection and delivery
3. Update agent signature to receive tuple
4. Add comprehensive tests

**Breaking Change Migration:**
```python
# Old code (OR behavior)
agent.consumes(TypeA, TypeB)  # Triggered on A or B

# New behavior (AND)
agent.consumes(TypeA, TypeB)  # Waits for both A and B

# For old OR behavior, use chaining:
agent.consumes(TypeA).consumes(TypeB)  # OR gate
```

**Estimated Effort:** 2-3 weeks
- Week 1: Core orchestrator changes
- Week 2: Agent signature updates, tests
- Week 3: Example updates, documentation

---

### Phase 2: JoinSpec - Correlated AND (v0.6 - 2-3 weeks)

**Goal:** Implement correlated joins with time windows

**Implementation:**
1. Correlation key extraction and grouping
2. Time window tracking and expiry
3. Matched pair delivery to agents
4. Tests for correlation edge cases

**New Functionality:**
```python
agent.consumes(
    TypeA, TypeB,
    join=JoinSpec(
        by=lambda x: x.correlation_key,
        within=timedelta(minutes=5)
    )
)
```

**Estimated Effort:** 2-3 weeks
- Week 1: Correlation engine
- Week 2: Time window management
- Week 3: Tests, edge cases, documentation

---

### Phase 3: BatchSpec - Batch Processing (v0.7 - 1-2 weeks)

**Goal:** Implement batch collection and delivery

**Implementation:**
1. Batch accumulator per agent/subscription
2. Size-based and timeout-based flushing
3. Batch delivery to agents
4. Tests for batch edge cases

**New Functionality:**
```python
agent.consumes(
    Event,
    batch=BatchSpec(size=50, timeout=timedelta(seconds=30))
)
```

**Estimated Effort:** 1-2 weeks
- Week 1: Batch accumulator, flushing logic
- Week 2: Tests, documentation

---

### Phase 4: Combined Features (v0.7 - 1 week)

**Goal:** Support batched correlated joins

**Implementation:**
1. Combine join and batch logic
2. Batch of correlated pairs delivery
3. Integration tests

**New Functionality:**
```python
agent.consumes(
    TypeA, TypeB,
    join=JoinSpec(...),
    batch=BatchSpec(...)
)
```

**Estimated Effort:** 1 week

---

### Total Timeline

| Phase | Feature | Duration | Dependency |
|-------|---------|----------|------------|
| **1** | Simple AND | 2-3 weeks | None |
| **2** | JoinSpec | 2-3 weeks | Phase 1 |
| **3** | BatchSpec | 1-2 weeks | Phase 1 |
| **4** | Combined | 1 week | Phases 2 & 3 |

**Total: 6-9 weeks** for complete implementation

---

## 🎯 Decision Framework

### Decision Matrix

Use this matrix to decide API design:

| Consideration | Option A: Change Default | Option B: Explicit Methods | Option C: Do Nothing |
|---------------|-------------------------|---------------------------|---------------------|
| **Developer Intuition** | ✅ High (matches expectations) | ✅ High (clear intent) | ❌ Low (confusing) |
| **Breaking Changes** | ⚠️ Yes (migration needed) | ✅ No (additive only) | ✅ No changes |
| **Footgun Prevention** | ✅ Prevents silent bugs | ✅ Forces correct usage | ❌ Easy to misuse |
| **API Simplicity** | ✅ Single method | ⚠️ More methods | ✅ Current API |
| **Common Case** | ✅ Easy (AND default) | ⚠️ Verbose | ❌ Wrong behavior |
| **Industry Alignment** | ✅ Matches standards | ✅ Explicit patterns | ❌ Non-standard |
| **Implementation Effort** | ⚠️ High (migration) | ⚠️ Medium (new methods) | ✅ Zero |

### Recommended Approach: **Hybrid Strategy**

**Phase 1 (v0.6): Add Explicit Methods**
```python
# New explicit API (no breaking changes)
agent.consumes_all(A, B)    # AND - clear intent
agent.consumes_any(A, B)    # OR - clear intent

# Deprecate ambiguous API
agent.consumes(A, B)  # ⚠️ Warning: Use consumes_all or consumes_any
```

**Phase 2 (v1.0): Change Default**
```python
# After 6-month deprecation period
agent.consumes(A, B)            # AND (new default)
agent.consumes(A).consumes(B)  # OR (chaining)
```

**Benefits:**
- ✅ Zero breaking changes in v0.6
- ✅ Clear migration path
- ✅ Forces developers to choose explicitly
- ✅ Natural transition to intuitive default in v1.0

---

## 📝 Open Questions for Discussion

### 1. Breaking Change Timing

**Question:** When should we change the default behavior of `.consumes(A, B)`?

**Options:**
- **A) v0.6 (immediate)** - Fast but breaks existing code
- **B) v1.0 (6 months)** - Safe but delayed value
- **C) Never (keep OR)** - Consistent but unintuitive

**Recommendation:** B (v1.0 with explicit methods in v0.6)

---

### 2. Join Timeout Behavior

**Question:** What happens when artifacts don't arrive within the time window?

**Options:**
- **A) Discard and wait for new matches** - Stateless, simple
- **B) Publish partial match event** - Allows recovery logic
- **C) Extend window once** - Grace period for late arrivals

**Recommendation:** A (discard) with optional B (partial match events)

---

### 3. Batch Partial Flush

**Question:** Should we deliver partial batches when agent stops/restarts?

**Options:**
- **A) Yes, flush on shutdown** - No data loss
- **B) No, discard partial** - Simpler, idempotent
- **C) Configurable** - Flexibility

**Recommendation:** A (flush on shutdown) for durability

---

### 4. Agent Signature Complexity

**Question:** How should agents receive complex combinations?

**Current Proposal:**
```python
# Simple AND - tuple
async def process(ctx, a: TypeA, b: TypeB) -> list[Result]

# Batched - list
async def process(ctx, items: list[TypeA]) -> list[Result]

# Batched joins - list of tuples
async def process(ctx, pairs: list[tuple[TypeA, TypeB]]) -> list[Result]
```

**Alternative:** Unified wrapper object
```python
async def process(ctx, input: AgentInput) -> list[Result]:
    if input.is_batch:
        items = input.batch
    elif input.is_join:
        a, b = input.joined_pair
```

**Recommendation:** Current proposal (type-safe, explicit)

---

## 📚 References

### Industry Standards
- [Airflow DAG Design](https://airflow.apache.org/docs/apache-airflow/stable/concepts/dags.html)
- [RxJS Operators](https://rxjs.dev/guide/operators)
- [Temporal Workflows](https://docs.temporal.io/workflows)
- [Step Functions Parallel State](https://docs.aws.amazon.com/step-functions/latest/dg/amazon-states-language-parallel-state.html)
- [Prefect Task Dependencies](https://docs.prefect.io/concepts/tasks/)

### Academic Background
- [Blackboard Architecture (Hearsay-II)](https://en.wikipedia.org/wiki/Blackboard_system)
- [Event Correlation in Complex Systems](https://dl.acm.org/doi/10.1145/1018210.1018211)
- [Stream Processing Patterns](https://www.oreilly.com/library/view/streaming-systems/9781491983867/)

### Flock Documentation
- [Current Analysis: 01-core-orchestration-actual-behavior.md](../feature-analysis/01-core-orchestration-actual-behavior.md)
- [Current Analysis: 05-advanced-features-validation.md](../feature-analysis/05-advanced-features-validation.md)

---

## 🎉 Conclusion

### Summary of Recommendations

**Immediate Actions (v0.6):**
1. ✅ Implement simple AND gate (`.consumes(A, B)` waits for both)
2. ✅ Add explicit methods (`consumes_all()`, `consumes_any()`)
3. ✅ Implement JoinSpec for correlated AND with time windows
4. ✅ Remove vapor-ware examples from documentation

**Short-term Actions (v0.7):**
5. ✅ Implement BatchSpec for cost-optimized batch processing
6. ✅ Support combined batched joins
7. ✅ Comprehensive examples and documentation

**Long-term Actions (v1.0):**
8. ✅ Change default after 6-month deprecation
9. ✅ Add advanced join types (any_of, at_least_n)
10. ✅ Performance optimizations and scale testing

### Expected Impact

**Developer Experience:**
- 🎯 Intuitive API that matches natural language
- 🔒 Safe by default (prevents silent failures)
- 📚 Clear migration path with no surprises

**Framework Capabilities:**
- ✅ Multi-signal coordination (healthcare, trading, manufacturing)
- ✅ Cost optimization (batch LLM calls)
- ✅ Correlation correctness (same patient, same stock, same batch)

**Production Readiness:**
- ✅ Feature parity with industry standards
- ✅ Comprehensive test coverage
- ✅ Real-world examples and patterns

---

**Missing features, ayayaya! But now we have a plan! 🚀**

**Document Prepared By:** Claude Code Analysis Team
**For Discussion With:** Flock Core Development Team
**Next Steps:** Review, decide on approach, implement in sprints

---

*This document is a living specification. Update as implementation progresses and requirements evolve.*
