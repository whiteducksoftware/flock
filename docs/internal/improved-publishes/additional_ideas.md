# Additional Ideas for `.publishes()` Sugar

**Creative patterns and syntactic sugar for enhanced artifact publishing**

**Status**: 💡 Brainstorming / Ideas Phase
**Date**: 2025-10-15

---

## 🎯 Philosophy

While we're enhancing `.publishes()`, let's explore **ALL** the patterns that could make publishing more powerful, flexible, and expressive!

**Guiding Principles**:
- ✅ Keep it declarative (builder pattern)
- ✅ Maintain symmetry with `.consumes()` where possible
- ✅ Enable powerful patterns without complexity
- ✅ "Pay for what you use" - simple cases stay simple

---

## 1️⃣ Filtering Outputs (User's Idea!) 🔥

### Concept

Filter artifacts BEFORE publishing using predicates.

### Syntax

```python
# Filter artifacts based on validation
validator = (
    flock.agent("validator")
    .consumes(Data)
    .publishes(
        ValidationResult,
        fan_out=10,
        where=lambda r: r.score > 0.8  # Only publish high-scoring results
    )
)

# Filter with complex logic
processor = (
    flock.agent("processor")
    .publishes(
        Result,
        fan_out=100,
        where=lambda r: r.status == "success" and r.value is not None
    )
)
```

### Use Cases

**Use Case 1: Quality Filtering**
```python
# Generate 10 ideas, publish only good ones
idea_generator = (
    flock.agent("idea_generator")
    .publishes(
        Idea,
        fan_out=10,
        where=lambda i: i.novelty_score > 0.7 and i.feasibility_score > 0.6
    )
)
# Result: Might publish 3-7 ideas (only the good ones!)
```

**Use Case 2: Error Handling**
```python
# Try to generate 5 results, filter out errors
processor = (
    flock.agent("processor")
    .publishes(
        ProcessingResult,
        fan_out=5,
        where=lambda r: r.error is None  # Only successful results
    )
)
```

**Use Case 3: Sampling**
```python
# Generate 100 samples, publish only interesting ones
sampler = (
    flock.agent("sampler")
    .publishes(
        Sample,
        fan_out=100,
        where=lambda s: s.is_outlier or s.is_edge_case
    )
)
```

### Implementation Notes

```python
def _make_outputs(self, result: EvalResult) -> list[Artifact]:
    """Extract and filter artifacts."""
    artifacts = []

    for output_decl in self.outputs:
        matching = [a for a in result.artifacts if a.type == output_decl.spec.type_name]

        # Apply filter if specified
        if output_decl.filter_predicate:
            matching = [a for a in matching if output_decl.filter_predicate(a.payload)]

        artifacts.extend(matching)

    return artifacts
```

### Open Questions

- **Count validation**: If fan_out=10 but filter reduces to 3, is that an error?
  - **Option A**: Require ALL 10, then filter (might fail validation)
  - **Option B**: Generate 10, filter, accept whatever passes (more flexible)
  - **Recommendation**: Option B (more useful)

---

## 2️⃣ Transformation / Mapping

### Concept

Transform artifacts BEFORE publishing (e.g., add metadata, modify fields).

### Syntax

```python
# Add correlation IDs
task_creator = (
    flock.agent("task_creator")
    .publishes(
        Task,
        fan_out=4,
        transform=lambda t, idx: {**t, "batch_id": "batch-123", "sequence": idx}
    )
)

# Add timestamps
event_generator = (
    flock.agent("event_generator")
    .publishes(
        Event,
        fan_out=10,
        transform=lambda e, idx: {**e, "created_at": datetime.now(), "index": idx}
    )
)

# Enrich with context
enricher = (
    flock.agent("enricher")
    .publishes(
        EnrichedData,
        transform=lambda d: {**d, "metadata": get_enrichment_metadata()}
    )
)
```

### Use Cases

**Use Case 1: Sequencing**
```python
# Add sequence numbers to maintain order
.publishes(
    Task,
    fan_out=10,
    transform=lambda t, idx: {**t, "sequence_number": idx, "total": 10}
)
```

**Use Case 2: Correlation**
```python
# Link artifacts together
batch_id = uuid.uuid4()
.publishes(
    Item,
    fan_out=5,
    transform=lambda i, idx: {**i, "batch_id": str(batch_id), "item_number": idx + 1}
)
```

**Use Case 3: Metadata Injection**
```python
# Add contextual metadata to all artifacts
.publishes(
    Result,
    fan_out=3,
    transform=lambda r, idx: {
        **r,
        "pipeline_version": "v2.3",
        "environment": "production",
        "published_at": datetime.now()
    }
)
```

---

## 3️⃣ Conditional Publishing

### Concept

Publish artifacts ONLY if certain conditions are met (across all artifacts).

### Syntax

```python
# Only publish if ALL artifacts meet criteria
validator = (
    flock.agent("validator")
    .publishes(
        ValidationResult,
        fan_out=5,
        publish_if=lambda results: all(r.passed for r in results)
    )
)

# Only publish if at least N artifacts meet criteria
task_generator = (
    flock.agent("task_generator")
    .publishes(
        Task,
        fan_out=10,
        publish_if=lambda tasks: len([t for t in tasks if t.priority == "high"]) >= 3
        # "Only publish if at least 3 high-priority tasks"
    )
)

# Conditional based on aggregate
analyzer = (
    flock.agent("analyzer")
    .publishes(
        Analysis,
        fan_out=5,
        publish_if=lambda analyses: sum(a.score for a in analyses) / len(analyses) > 0.7
        # "Only publish if average score > 0.7"
    )
)
```

### Use Cases

**Use Case 1: All-or-Nothing Validation**
```python
# Generate 5 results, but only publish if ALL are valid
.publishes(
    Result,
    fan_out=5,
    publish_if=lambda results: all(r.is_valid() for r in results)
)
# If any result is invalid, NONE are published → triggers retry or error handler
```

**Use Case 2: Quality Threshold**
```python
# Only publish batch if quality is high enough
.publishes(
    Prediction,
    fan_out=100,
    publish_if=lambda preds: statistics.mean(p.confidence for p in preds) > 0.85
)
```

**Use Case 3: Quorum-Based**
```python
# Need at least 3 out of 5 agents to agree
.publishes(
    Vote,
    fan_out=5,
    publish_if=lambda votes: len([v for v in votes if v.approve]) >= 3
)
```

---

## 4️⃣ Retry Logic

### Concept

Retry LLM generation if output doesn't meet criteria.

### Syntax

```python
# Retry up to 3 times until we get valid output
task_creator = (
    flock.agent("task_creator")
    .publishes(
        Task,
        fan_out=4,
        retry_if=lambda tasks: len(tasks) < 4,  # Retry if not enough tasks
        max_retries=3
    )
)

# Retry until quality threshold met
generator = (
    flock.agent("generator")
    .publishes(
        Content,
        retry_if=lambda c: c.quality_score < 0.8,
        max_retries=5,
        backoff="exponential"  # 1s, 2s, 4s, 8s, 16s
    )
)

# Custom retry logic
validator = (
    flock.agent("validator")
    .publishes(
        ValidationResult,
        fan_out=10,
        retry_if=lambda results: any(r.error for r in results),
        retry_prompt="Previous attempt had errors. Please fix and try again.",
        max_retries=2
    )
)
```

### Use Cases

**Use Case 1: Ensure Count**
```python
# Must generate exactly 5 tasks, retry if not
.publishes(
    Task,
    fan_out=5,
    retry_if=lambda tasks: len(tasks) != 5,
    max_retries=3
)
```

**Use Case 2: Quality Enforcement**
```python
# Keep trying until we get high-quality output
.publishes(
    Essay,
    retry_if=lambda e: e.word_count < 500 or e.quality_score < 0.7,
    max_retries=5
)
```

**Use Case 3: Validation Retry**
```python
# Retry until all validations pass
.publishes(
    ValidationResult,
    fan_out=10,
    retry_if=lambda results: not all(r.passed for r in results),
    retry_prompt="Some validations failed: {failures}. Please fix.",
    max_retries=3
)
```

---

## 5️⃣ Visibility Control (Per-Artifact)

### Concept

Fine-grained visibility control with dynamic rules.

### Syntax

```python
# Visibility based on artifact content
task_creator = (
    flock.agent("task_creator")
    .publishes(
        Task,
        fan_out=4,
        visibility=lambda t: "public" if t.priority == "high" else "private"
    )
)

# Different visibility for different types
initializer = (
    flock.agent("initializer")
    .publishes(
        Metadata, visibility="public",
        AuditLog, visibility="private",
        Notification, visibility=lambda n: "team" if n.urgent else "private"
    )
)

# Conditional visibility
result_publisher = (
    flock.agent("result_publisher")
    .publishes(
        Result,
        fan_out=10,
        visibility=lambda r, idx: (
            "public" if r.is_final else
            "team" if r.is_draft else
            "private"
        )
    )
)
```

### Use Cases

**Use Case 1: Sensitive Data**
```python
# Hide sensitive results
.publishes(
    AnalysisResult,
    fan_out=5,
    visibility=lambda r: "private" if r.contains_pii else "public"
)
```

**Use Case 2: Progressive Disclosure**
```python
# Show only final results publicly
.publishes(
    Iteration,
    fan_out=10,
    visibility=lambda i, idx: "public" if idx == 9 else "private"  # Only last iteration
)
```

**Use Case 3: Team Collaboration**
```python
# Share drafts with team, finals with everyone
.publishes(
    Document,
    visibility=lambda d: "public" if d.status == "final" else "team"
)
```

---

## 6️⃣ Batching / Grouping

### Concept

Control how artifacts are grouped for publishing.

### Syntax

```python
# Publish in batches of 5
processor = (
    flock.agent("processor")
    .publishes(
        Task,
        fan_out=20,
        batch_size=5  # Publishes 4 separate batches of 5 tasks each
    )
)

# Group by property
classifier = (
    flock.agent("classifier")
    .publishes(
        Item,
        fan_out=100,
        group_by=lambda i: i.category  # Group by category before publishing
    )
)

# Time-based batching
stream_processor = (
    flock.agent("stream_processor")
    .publishes(
        Event,
        fan_out="*",  # Variable count
        batch_window=timedelta(seconds=5)  # Batch all events within 5s window
    )
)
```

### Use Cases

**Use Case 1: Rate Limiting**
```python
# Publish 100 tasks in batches of 10 (avoid overwhelming downstream)
.publishes(
    Task,
    fan_out=100,
    batch_size=10,
    batch_delay=timedelta(seconds=1)  # 1s delay between batches
)
```

**Use Case 2: Logical Grouping**
```python
# Group test cases by test suite
.publishes(
    TestCase,
    fan_out=50,
    group_by=lambda tc: tc.suite_name
)
# Result: Multiple TestCaseBatch artifacts, one per suite
```

**Use Case 3: Progressive Publishing**
```python
# Publish results as they become available
.publishes(
    Result,
    fan_out=100,
    publish_strategy="progressive",  # Don't wait for all 100
    progressive_batch_size=10  # Publish every 10 results
)
```

---

## 7️⃣ Priority / Ordering

### Concept

Control the order in which artifacts are published.

### Syntax

```python
# Priority-based publishing
task_creator = (
    flock.agent("task_creator")
    .publishes(
        Task,
        fan_out=10,
        priority=lambda t: t.priority_score,  # Higher scores publish first
        order="descending"
    )
)

# Custom ordering
query_generator = (
    flock.agent("query_generator")
    .publishes(
        Query,
        fan_out=5,
        order_by=lambda q: (q.complexity, q.estimated_time)  # Sort by multiple fields
    )
)

# Sequential with delays
gradual_loader = (
    flock.agent("gradual_loader")
    .publishes(
        DataChunk,
        fan_out=10,
        publish_order="sequential",  # One at a time
        delay_between=timedelta(milliseconds=100)  # 100ms between each
    )
)
```

### Use Cases

**Use Case 1: Priority Queue**
```python
# High-priority tasks execute first
.publishes(
    Task,
    fan_out=20,
    priority=lambda t: {"critical": 1, "high": 2, "medium": 3, "low": 4}[t.priority]
)
```

**Use Case 2: Dependency Order**
```python
# Publish in dependency order
.publishes(
    BuildTask,
    fan_out=10,
    order_by=lambda t: t.dependency_level  # 0 = no deps, 1 = depends on level 0, etc.
)
```

**Use Case 3: Load Spreading**
```python
# Spread load over time
.publishes(
    Request,
    fan_out=100,
    publish_order="sequential",
    delay_between=timedelta(milliseconds=50)  # Throttle publishing
)
```

---

## 8️⃣ Correlation / Linking

### Concept

Automatically link related artifacts together.

### Syntax

```python
# Auto-correlate all artifacts from one execution
task_creator = (
    flock.agent("task_creator")
    .publishes(
        Task,
        fan_out=4,
        correlate=True,  # All 4 tasks get same correlation_id
        correlation_key=lambda: f"batch-{datetime.now().isoformat()}"
    )
)

# Link to input artifact
processor = (
    flock.agent("processor")
    .publishes(
        Result,
        fan_out=10,
        correlate_with="input",  # Link to input artifact's correlation_id
        add_parent_ref=True  # Add parent_artifact_id field
    )
)

# Custom linking
analyzer = (
    flock.agent("analyzer")
    .publishes(
        Analysis,
        fan_out=5,
        link=lambda a, idx, input_artifact: {
            "parent_id": input_artifact.id,
            "sibling_count": 5,
            "position": idx
        }
    )
)
```

### Use Cases

**Use Case 1: Batch Tracking**
```python
# Track all tasks from same batch
.publishes(
    Task,
    fan_out=10,
    correlate=True  # All tasks get batch_id: "abc123"
)

# Later, aggregate with JoinSpec:
.consumes(Result, join=JoinSpec(by=lambda r: r.correlation_id))
```

**Use Case 2: Lineage Tracking**
```python
# Track data lineage
.publishes(
    ProcessedData,
    fan_out=5,
    add_lineage=True,  # Adds parent_artifact_id, processing_chain, etc.
)
```

**Use Case 3: Workflow Context**
```python
# Preserve workflow context across artifacts
.publishes(
    Step,
    fan_out=10,
    correlate_with="workflow",
    add_metadata=lambda s, idx: {"workflow_id": get_current_workflow_id()}
)
```

---

## 9️⃣ Sampling / Selection

### Concept

Publish only a subset of generated artifacts.

### Syntax

```python
# Random sampling
generator = (
    flock.agent("generator")
    .publishes(
        Sample,
        fan_out=100,
        sample=10,  # Publish 10 random samples out of 100
        sample_strategy="random"
    )
)

# Top-K selection
ranker = (
    flock.agent("ranker")
    .publishes(
        Result,
        fan_out=50,
        select="top_k",
        k=10,
        score_by=lambda r: r.relevance_score  # Publish top 10 by score
    )
)

# Diverse sampling
diversity_sampler = (
    flock.agent("diversity_sampler")
    .publishes(
        Candidate,
        fan_out=100,
        sample=20,
        sample_strategy="diverse",
        diversity_key=lambda c: c.category  # Ensure diverse categories
    )
)
```

### Use Cases

**Use Case 1: Exploration**
```python
# Generate many, explore few
.publishes(
    Hypothesis,
    fan_out=100,
    sample=10,  # Randomly explore 10 out of 100 hypotheses
    sample_strategy="random"
)
```

**Use Case 2: Best Results Only**
```python
# Generate 50 candidates, publish top 5
.publishes(
    Candidate,
    fan_out=50,
    select="top_k",
    k=5,
    score_by=lambda c: c.fitness_score
)
```

**Use Case 3: Representative Sample**
```python
# Ensure diverse representation
.publishes(
    Example,
    fan_out=100,
    sample=20,
    sample_strategy="stratified",
    strata_by=lambda e: e.difficulty_level  # Sample across all difficulty levels
)
```

---

## 🔟 Deduplication

### Concept

Remove duplicate artifacts before publishing.

### Syntax

```python
# Deduplicate by field
task_creator = (
    flock.agent("task_creator")
    .publishes(
        Task,
        fan_out=10,
        deduplicate_by=lambda t: t.task_id  # Only unique task_ids
    )
)

# Deduplicate by hash
content_generator = (
    flock.agent("content_generator")
    .publishes(
        Content,
        fan_out=20,
        deduplicate_by=lambda c: hash(c.text)  # Remove duplicate content
    )
)

# Fuzzy deduplication
url_extractor = (
    flock.agent("url_extractor")
    .publishes(
        URL,
        fan_out=50,
        deduplicate_by=lambda u: normalize_url(u.url),  # Normalize before comparing
        deduplicate_strategy="first"  # Keep first occurrence
    )
)
```

### Use Cases

**Use Case 1: Duplicate Prevention**
```python
# LLM sometimes generates duplicates
.publishes(
    Keyword,
    fan_out=20,
    deduplicate_by=lambda k: k.keyword.lower()  # Case-insensitive dedup
)
```

**Use Case 2: Unique IDs**
```python
# Ensure unique identifiers
.publishes(
    Entity,
    fan_out=100,
    deduplicate_by=lambda e: e.entity_id,
    on_duplicate="error"  # Raise error if duplicates found
)
```

**Use Case 3: Content Similarity**
```python
# Remove similar content
.publishes(
    Article,
    fan_out=10,
    deduplicate_by=lambda a: compute_content_hash(a.text),
    similarity_threshold=0.95  # 95% similar = duplicate
)
```

---

## 1️⃣1️⃣ Validation

### Concept

Validate artifacts before publishing with clear error messages.

### Syntax

```python
# Schema validation
task_creator = (
    flock.agent("task_creator")
    .publishes(
        Task,
        fan_out=4,
        validate=lambda t: t.priority in ["high", "medium", "low"],
        validation_error="Task priority must be high/medium/low"
    )
)

# Complex validation
result_publisher = (
    flock.agent("result_publisher")
    .publishes(
        Result,
        fan_out=10,
        validate=[
            (lambda r: r.score >= 0 and r.score <= 1, "Score must be 0-1"),
            (lambda r: len(r.data) > 0, "Data cannot be empty"),
            (lambda r: r.timestamp is not None, "Timestamp required"),
        ]
    )
)

# Cross-artifact validation
batch_validator = (
    flock.agent("batch_validator")
    .publishes(
        BatchResult,
        fan_out=5,
        validate_batch=lambda results: len(set(r.batch_id for r in results)) == 1,
        validation_error="All results must have same batch_id"
    )
)
```

### Use Cases

**Use Case 1: Data Integrity**
```python
# Ensure data quality before publishing
.publishes(
    DataRecord,
    fan_out=100,
    validate=[
        (lambda d: d.id is not None, "ID required"),
        (lambda d: d.value >= 0, "Value must be non-negative"),
        (lambda d: len(d.metadata) > 0, "Metadata required"),
    ]
)
```

**Use Case 2: Business Rules**
```python
# Enforce business constraints
.publishes(
    Order,
    fan_out=10,
    validate=lambda o: o.total >= o.subtotal + o.tax,
    validation_error="Order total must equal subtotal + tax"
)
```

**Use Case 3: Format Validation**
```python
# Validate formats
.publishes(
    EmailContact,
    fan_out=50,
    validate=lambda e: re.match(r"^[^@]+@[^@]+\.[^@]+$", e.email),
    validation_error="Invalid email format"
)
```

---

## 1️⃣2️⃣ Rate Limiting

### Concept

Control publishing rate to avoid overwhelming downstream systems.

### Syntax

```python
# Limit publish rate
bulk_publisher = (
    flock.agent("bulk_publisher")
    .publishes(
        Item,
        fan_out=1000,
        rate_limit="100/second"  # Max 100 artifacts per second
    )
)

# Token bucket algorithm
api_caller = (
    flock.agent("api_caller")
    .publishes(
        APIRequest,
        fan_out=500,
        rate_limit="50/minute",
        rate_limit_strategy="token_bucket",
        burst_size=100  # Allow bursts up to 100
    )
)

# Adaptive rate limiting
adaptive_publisher = (
    flock.agent("adaptive_publisher")
    .publishes(
        Event,
        fan_out=10000,
        rate_limit="adaptive",  # Adjust based on downstream load
        target_latency=timedelta(milliseconds=100)
    )
)
```

### Use Cases

**Use Case 1: API Rate Limits**
```python
# Respect external API limits
.publishes(
    APICall,
    fan_out=1000,
    rate_limit="100/minute"  # API allows 100 calls/min
)
```

**Use Case 2: Database Load**
```python
# Avoid overwhelming database
.publishes(
    DBWrite,
    fan_out=10000,
    rate_limit="500/second",  # DB can handle 500 writes/sec
    rate_limit_strategy="sliding_window"
)
```

**Use Case 3: Gradual Rollout**
```python
# Gradually publish to monitor impact
.publishes(
    FeatureFlag,
    fan_out=1000000,
    rate_limit="1000/hour",  # Slow rollout over ~1000 hours
    publish_order="random"  # Random users
)
```

---

## 1️⃣3️⃣ Conditional Fan-Out (Dynamic Count)

### Concept

Fan-out count determined by input data or runtime conditions.

### Syntax

```python
# Fan-out based on input
adaptive_splitter = (
    flock.agent("adaptive_splitter")
    .publishes(
        Chunk,
        fan_out=lambda input: input.size // 1000,  # 1 chunk per 1000 items
        max_fan_out=100  # Safety limit
    )
)

# Fan-out based on complexity
task_creator = (
    flock.agent("task_creator")
    .publishes(
        Task,
        fan_out=lambda input: {
            "simple": 2,
            "medium": 5,
            "complex": 10
        }[input.complexity]
    )
)

# LLM decides (with constraints)
dynamic_generator = (
    flock.agent("dynamic_generator")
    .publishes(
        Item,
        fan_out="*",  # LLM decides
        min_fan_out=3,  # At least 3
        max_fan_out=20  # At most 20
    )
)
```

### Use Cases

**Use Case 1: Data-Driven Chunking**
```python
# Chunk size based on data size
.publishes(
    Chunk,
    fan_out=lambda input: max(1, input.total_records // 1000)
)
```

**Use Case 2: Complexity-Based Tasks**
```python
# More tasks for complex problems
.publishes(
    SubTask,
    fan_out=lambda input: input.complexity_score * 2  # 2 tasks per complexity point
)
```

**Use Case 3: Adaptive Processing**
```python
# Adjust parallelism based on load
.publishes(
    Worker,
    fan_out=lambda input: get_optimal_worker_count(input.workload)
)
```

---

## 1️⃣4️⃣ Chaining / Composition

### Concept

Compose multiple publish transformations together.

### Syntax

```python
# Chain transformations
processor = (
    flock.agent("processor")
    .publishes(
        Result,
        fan_out=100
    )
    .filter_outputs(lambda r: r.score > 0.8)  # Filter
    .transform_outputs(lambda r: {**r, "metadata": {...}})  # Transform
    .sort_outputs(lambda r: r.priority)  # Sort
    .limit_outputs(10)  # Take top 10
)

# Or using pipe syntax
processor = (
    flock.agent("processor")
    .publishes(Result, fan_out=100)
    .pipe(
        filter_by(lambda r: r.score > 0.8),
        add_metadata({"version": "2.0"}),
        sort_by(lambda r: r.priority),
        take(10)
    )
)
```

### Use Cases

**Use Case 1: Processing Pipeline**
```python
# Multi-stage output processing
.publishes(Candidate, fan_out=100)
.filter_outputs(lambda c: c.is_valid)
.sort_outputs(lambda c: c.score, reverse=True)
.limit_outputs(20)
.deduplicate_outputs(lambda c: c.id)
# Result: Top 20 unique valid candidates
```

**Use Case 2: Enrichment Pipeline**
```python
# Add progressive enrichment
.publishes(Item, fan_out=50)
.transform_outputs(add_timestamps)
.transform_outputs(add_metadata)
.transform_outputs(compute_scores)
.filter_outputs(lambda i: i.score > threshold)
```

---

## 💡 Implementation Priorities

### Tier 1: Must-Have (Week 1-2)
1. ✅ **Basic fan-out** - `.publishes(A, fan_out=N)`
2. 🔥 **Output filtering** - `where=lambda x: ...` (User's idea!)
3. ✅ **Transformation** - `transform=lambda x: ...`
4. ✅ **Visibility control** - `visibility=lambda x: ...`

### Tier 2: High Value (Week 3-4)
5. **Conditional publishing** - `publish_if=lambda xs: ...`
6. **Correlation** - `correlate=True`
7. **Validation** - `validate=lambda x: ...`
8. **Deduplication** - `deduplicate_by=lambda x: ...`

### Tier 3: Advanced (Month 2)
9. **Retry logic** - `retry_if=lambda x: ...`
10. **Priority/Ordering** - `order_by=lambda x: ...`
11. **Sampling** - `sample=N, sample_strategy="..."`
12. **Batching** - `batch_size=N`

### Tier 4: Future (Month 3+)
13. **Rate limiting** - `rate_limit="100/second"`
14. **Conditional fan-out** - `fan_out=lambda input: ...`
15. **Chaining/Composition** - `.pipe(...)`

---

## 🎨 API Design Considerations

### Consistency

**Keep symmetry with `.consumes()` where possible**:
```python
# .consumes() has where= for filtering
.consumes(Task, where=lambda t: t.priority == "high")

# .publishes() should too!
.publishes(Result, fan_out=10, where=lambda r: r.success)
```

### Simplicity

**Simple cases should stay simple**:
```python
# Basic case: Just fan-out
.publishes(Task, fan_out=4)

# Advanced case: Add features as needed
.publishes(
    Task,
    fan_out=4,
    where=lambda t: t.valid,
    transform=lambda t: add_metadata(t),
    visibility=lambda t: "public" if t.important else "private"
)
```

### Discoverability

**Use clear, descriptive parameter names**:
- ✅ `where=` (filtering) - matches `.consumes()`
- ✅ `transform=` (transformation) - clear intent
- ✅ `fan_out=` (count) - already established
- ✅ `validate=` (validation) - obvious
- ❌ `f=` or `pred=` - too cryptic

### Type Safety

**Leverage type hints**:
```python
def publishes(
    self,
    *types: Type[BaseModel],
    fan_out: int | Callable[[Any], int] | Literal["*"] | None = None,
    where: Callable[[BaseModel], bool] | None = None,
    transform: Callable[[BaseModel, int], dict] | None = None,
    visibility: Visibility | Callable[[BaseModel], Visibility] = "private",
    # ... more options
) -> AgentBuilder:
```

---

## 🚀 Example: Putting It All Together

### Realistic Complex Example

```python
from datetime import datetime, timedelta
from flock import Flock, flock_type

flock = Flock()

# Generate 100 candidates, filter, transform, sample top 10
candidate_generator = (
    flock.agent("candidate_generator")
    .description(
        "Generates 100 solution candidates for the given problem. "
        "Each candidate includes a solution description, estimated complexity, "
        "and confidence score."
    )
    .consumes(Problem)
    .publishes(
        Candidate,
        fan_out=100,

        # Filter: Only valid candidates with confidence > 0.7
        where=lambda c: c.is_valid and c.confidence > 0.7,

        # Transform: Add metadata
        transform=lambda c, idx: {
            **c,
            "generated_at": datetime.now(),
            "candidate_number": idx + 1,
            "batch_id": "batch-123"
        },

        # Validate: Ensure required fields
        validate=[
            (lambda c: c.complexity in ["low", "medium", "high"], "Invalid complexity"),
            (lambda c: 0 <= c.confidence <= 1, "Confidence must be 0-1"),
        ],

        # Deduplicate: Remove duplicate solutions
        deduplicate_by=lambda c: hash(c.solution_text),

        # Visibility: High-confidence solutions are public
        visibility=lambda c: "public" if c.confidence > 0.9 else "team",

        # Correlation: Link all candidates
        correlate=True,
    )
)

# Result:
# - Generates 100 candidates
# - Filters to ~50-70 (confidence > 0.7)
# - Adds metadata to each
# - Validates all fields
# - Removes duplicates (~45-65 remain)
# - All linked with same correlation_id
# - High-confidence ones marked public
```

**This is POWERFUL!** 🔥

---

## 🤔 Open Questions

### 1. Execution Order

When multiple transformations are applied, what order?

**Proposed Order**:
1. LLM generates artifacts
2. Count validation (if fan_out specified)
3. Validation (`validate=`)
4. Transformation (`transform=`)
5. Filtering (`where=`)
6. Deduplication (`deduplicate_by=`)
7. Ordering (`order_by=`)
8. Sampling (`sample=`)
9. Batching (`batch_size=`)
10. Visibility application
11. Correlation (`correlate=`)
12. Publish to blackboard

### 2. Error Handling

What happens when:
- Validation fails?
- Filter reduces count to 0?
- Transformation throws exception?

**Proposed**: Clear error messages with hints, fail fast

### 3. Performance

Concerns:
- 100 artifacts × 10 transformations = lots of processing
- Lambda functions for each artifact = performance hit?

**Mitigations**:
- Benchmark and optimize hot paths
- Consider compiled expressions for filters
- Cache transformation results

### 4. Backwards Compatibility

**Guarantee**: All existing `.publishes()` calls continue working unchanged.

New parameters are **optional** - defaults preserve current behavior.

---

## 🎯 Recommendations

### Start With Tier 1

Implement these first (highest value, lowest complexity):
1. ✅ Basic fan-out (already designed)
2. 🔥 **Output filtering** (`where=`) - User's brilliant idea!
3. **Transformation** (`transform=`)
4. **Visibility control** (`visibility=lambda`)

These 4 features unlock 80% of use cases with minimal code.

### Save Tier 4 for Later

Features like rate limiting and chaining are powerful but:
- Complex to implement correctly
- May not be needed initially
- Can be added later without breaking changes

### Get Feedback Early

Ship Tier 1, gather user feedback, then prioritize Tier 2-4 based on real needs.

---

## 💭 Final Thoughts

**This document shows the FULL POTENTIAL** of what `.publishes()` could become!

**Philosophy**:
- Start simple (basic fan-out)
- Add features incrementally
- Maintain consistency with `.consumes()`
- Keep common cases simple
- Enable advanced cases without complexity creep

**The beauty**: All these features are **composable** - you can mix and match as needed!

```python
# Simple
.publishes(Task, fan_out=4)

# Advanced
.publishes(
    Task,
    fan_out=10,
    where=lambda t: t.valid,
    transform=add_metadata,
    visibility=determine_visibility,
    correlate=True
)
```

**Same API, different power levels!** 🚀

---

**What do you think?** Which features excite you most? Which should we prioritize?

Let's discuss and refine! 💬
