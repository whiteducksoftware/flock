---
tags:
  - semantic
  - subscriptions
  - ai
  - embeddings
  - routing
description: Comprehensive guide to semantic subscriptions for intelligent artifact matching using local AI embeddings
---

# Semantic Subscriptions

Semantic subscriptions enable agents to match artifacts based on **meaning** rather than just type matching. This allows for intelligent routing, context retrieval, and semantic filtering using sentence embeddings.

## Overview

Traditional subscriptions match artifacts by type and predicate logic. Semantic subscriptions add an AI-powered layer that understands the **semantic similarity** between text content, enabling:

- **Intelligent Routing**: Direct artifacts to agents based on meaning, not keywords
- **Context Retrieval**: Find historically relevant artifacts for informed decision-making
- **Semantic Filtering**: Filter artifacts by conceptual similarity
- **Graceful Degradation**: Falls back to type matching if semantic features unavailable

All processing happens **locally** using the `all-MiniLM-L6-v2` model (~90MB) - no API keys or internet connection required.

## Installation

Semantic features require the optional `semantic` extra:

```bash
uv add flock-core[semantic]
# or
pip install flock-core[semantic]
```

This installs `sentence-transformers` (~90MB) with the `all-MiniLM-L6-v2` model for local embedding generation.

### Dependency Information

- **Package**: `sentence-transformers`
- **Model**: `all-MiniLM-L6-v2`
- **Model Size**: ~90MB download
- **License**: Apache 2.0
- **Runtime**: CPU-optimized (no GPU required)

## Core Concepts

### Embeddings

Semantic matching uses **embeddings** - numerical vector representations of text that capture meaning:

```python
"security vulnerability" → [0.23, -0.15, 0.87, ..., 0.12]  # 384 dimensions
"SQL injection attack"   → [0.26, -0.18, 0.82, ..., 0.09]  # Semantically similar
"billing refund"         → [-0.45, 0.73, -0.12, ..., 0.34] # Semantically different
```

The distance between these vectors determines semantic similarity using cosine similarity (range: 0.0 to 1.0).

### Similarity Thresholds

The `semantic_threshold` parameter controls how similar text must be to match:

- **0.7-0.9**: Very strict - nearly identical concepts
- **0.4-0.6**: Moderate - related concepts (default: 0.4)
- **0.2-0.3**: Loose - broadly related topics

Higher thresholds reduce false positives but may miss valid matches. Lower thresholds increase recall but may match unrelated content.

## Basic Usage

### Simple Semantic Matching

Use `semantic_match` with a text query to filter artifacts by meaning:

```python
from flock import Flock
from pydantic import BaseModel

class SupportTicket(BaseModel):
    message: str
    priority: str

flock = Flock()

# Agent only processes security-related tickets
security_agent = (
    flock.agent("security_handler")
    .consumes(SupportTicket, semantic_match="security vulnerability")
    .publishes(SecurityAlert)
)
```

When a `SupportTicket` is published, it matches if its content is semantically similar to "security vulnerability" (threshold ≥ 0.4).

### Adjusting the Threshold

Control matching strictness with `semantic_threshold`:

```python
# Strict matching - only very similar content
security_agent = (
    flock.agent("security_handler")
    .consumes(
        SupportTicket,
        semantic_match="security vulnerability",
        semantic_threshold=0.7  # Stricter than default
    )
    .publishes(SecurityAlert)
)

# Loose matching - broadly related content
support_agent = (
    flock.agent("support_handler")
    .consumes(
        SupportTicket,
        semantic_match="technical issue",
        semantic_threshold=0.25  # More permissive
    )
    .publishes(SupportResponse)
)
```

### Field-Specific Matching

Match against a specific field instead of all text:

```python
# Only match the "description" field
agent = (
    flock.agent("handler")
    .consumes(
        Article,
        semantic_match={
            "query": "machine learning",
            "field": "abstract",  # Only match abstract field
            "threshold": 0.6
        }
    )
)
```

## Advanced Patterns

### Multiple Predicates (AND Logic)

Combine multiple semantic filters - artifact must match ALL:

```python
# Match tickets about BOTH billing AND refunds
agent = (
    flock.agent("billing_refund_handler")
    .consumes(
        SupportTicket,
        semantic_match=["billing payment", "refund request"]  # Both must match
    )
)
```

Each query is evaluated independently. The artifact matches only if it meets the threshold for ALL queries.

### Combining with Type and Predicate Filters

Semantic matching works alongside traditional filters:

```python
# Type filter + Predicate filter + Semantic filter
agent = (
    flock.agent("critical_security")
    .consumes(
        SupportTicket,
        where=lambda t: t.priority == "critical",  # Predicate filter
        semantic_match="security vulnerability",    # Semantic filter
        semantic_threshold=0.6
    )
)
```

All filters must pass:
1. Type must be `SupportTicket`
2. Priority must be "critical"
3. Semantic similarity must be ≥ 0.6

### Semantic Context Provider

Retrieve historically relevant artifacts for context-aware processing:

```python
from flock.semantic import SemanticContextProvider
from flock.components.agent import EngineComponent
from flock.utils.runtime import EvalInputs, EvalResult

class ContextAwareEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        ticket = SupportTicket(**inputs.artifacts[0].payload)

        # Find similar historical tickets
        provider = SemanticContextProvider(
            query_text=ticket.message,
            threshold=0.4,
            limit=5
        )
        similar = await provider.get_context(flock.store)

        # Use similar tickets for informed response
        if similar:
            past_resolutions = [s.payload["resolution"] for s in similar]
            recommended_action = most_common(past_resolutions)
        else:
            recommended_action = "Escalate to on-call engineer"

        return EvalResult(
            artifacts=[Response(action=recommended_action)],
            state={"similar_count": len(similar)}
        )
```

#### Advanced Context Provider Options

```python
# Match specific field
provider = SemanticContextProvider(
    query_text="authentication issue",
    extract_field="description",  # Only match this field
    threshold=0.6,
    limit=10
)

# Add type and predicate filters
provider = SemanticContextProvider(
    query_text="database error",
    artifact_type=LogEntry,
    where=lambda a: a.payload["severity"] == "error",
    threshold=0.4,
    limit=20
)
```

## API Reference

### Subscription Parameters

#### `semantic_match`

**Type**: `str | list[str] | dict[str, Any] | None`

Specifies semantic matching criteria for subscription.

**String format** (simple):
```python
.consumes(Task, semantic_match="urgent priority")
```
Uses default threshold (0.4) and matches against all text fields.

**List format** (multiple predicates):
```python
.consumes(Task, semantic_match=["urgent", "high priority"])
```
ALL predicates must match (AND logic).

**Dict format** (advanced configuration):
```python
.consumes(Task, semantic_match={
    "query": "urgent",
    "threshold": 0.6,  # Custom threshold
    "field": "description"  # Match specific field
})
```

#### `semantic_threshold`

**Type**: `float` (default: 0.0)

Controls the minimum similarity score for matching when using simple string or list formats of `semantic_match`.

```python
# Loose matching
.consumes(Ticket, semantic_match="security", semantic_threshold=0.3)

# Moderate matching (recommended)
.consumes(Ticket, semantic_match="security", semantic_threshold=0.5)

# Strict matching
.consumes(Ticket, semantic_match="security", semantic_threshold=0.7)
```

**Note**: If using dict format with explicit `threshold`, that takes precedence over `semantic_threshold`.

### SemanticContextProvider

Retrieves semantically relevant artifacts from the artifact store.

```python
class SemanticContextProvider:
    def __init__(
        self,
        query_text: str,
        threshold: float = 0.4,
        limit: int = 10,
        extract_field: str | None = None,
        artifact_type: type[BaseModel] | None = None,
        where: Callable[[Artifact], bool] | None = None
    ):
        """
        Args:
            query_text: Semantic query to match against
            threshold: Minimum similarity score (0.0-1.0)
            limit: Maximum number of results
            extract_field: Optional field name to extract from payload
            artifact_type: Optional type filter
            where: Optional predicate for additional filtering
        """

    async def get_context(self, store: ArtifactStore) -> list[Artifact]:
        """Retrieve semantically relevant artifacts."""
```

**Example**:
```python
provider = SemanticContextProvider(
    query_text="database connection error",
    threshold=0.5,
    limit=10,
    extract_field="message",
    artifact_type=LogEntry,
    where=lambda a: a.payload["severity"] == "error"
)

similar_logs = await provider.get_context(flock.store)
```

### EmbeddingService

Low-level service for generating embeddings and computing similarity.

```python
from flock.semantic import EmbeddingService

service = EmbeddingService.get_instance()  # Singleton

# Single text
embedding = service.embed("some text")  # np.ndarray (384,)

# Batch (more efficient for multiple texts)
embeddings = service.embed_batch(["text1", "text2", "text3"])

# Similarity between two texts
score = service.similarity("text1", "text2")  # float [0.0, 1.0]
```

**Features**:
- **LRU cache**: 10,000 embedding capacity
- **Lazy loading**: Model loaded on first use
- **Thread-safe**: Singleton pattern
- **Automatic normalization**: Handles shape conversion

### TextPredicate

Internal dataclass representing a semantic predicate.

```python
@dataclass
class TextPredicate:
    query: str                    # The semantic query
    threshold: float = 0.4        # Minimum similarity
    field: str | None = None      # Optional field extraction
```

You typically don't construct these directly - use `semantic_match` parameter instead.

## Performance Characteristics

### Model Specifications

- **Model**: all-MiniLM-L6-v2
- **Parameters**: 22 million
- **Size**: ~90MB download
- **Architecture**: 6-layer transformer (distilled from BERT)
- **Embedding dimensions**: 384
- **Training**: Semantic textual similarity tasks

### Runtime Performance

- **Embedding generation**: ~10-50ms per text (CPU)
- **Batch processing**: 3-5x faster than individual calls
- **Cache hit latency**: ~0.1ms (LRU lookup)
- **Similarity computation**: ~0.01ms (cosine similarity)
- **Memory footprint**: ~150MB model + ~6MB per 10k cached embeddings

### Optimization Tips

**1. Batch Processing**: Use `embed_batch()` for multiple texts:
```python
service = EmbeddingService.get_instance()
embeddings = service.embed_batch(texts)  # 3-5x faster than loop
```

**2. Cache Warm-up**: Pre-compute common queries:
```python
# Warm up cache at startup
for common_query in ["security", "billing", "technical"]:
    service.embed(common_query)
```

**3. Field Extraction**: Match specific fields to reduce computation:
```python
# Better: Only process "message" field
.consumes(Ticket, semantic_match={"query": "security", "field": "message"})

# Slower: Process all text fields
.consumes(Ticket, semantic_match="security")
```

**4. Predicate Ordering**: Put cheap filters first:
```python
# Good: Type and predicate filter before expensive semantic matching
.consumes(
    Ticket,
    where=lambda t: t.priority == "high",  # Fast
    semantic_match="security"              # Slower
)
```

## Best Practices

### 1. Choose Appropriate Thresholds

Start with default (0.4) and adjust based on observed false positives/negatives:

```python
# Strict (0.7-0.9): High precision, may miss valid matches
.consumes(Task, semantic_match="exact concept", semantic_threshold=0.8)

# Moderate (0.4-0.6): Balanced precision/recall (recommended)
.consumes(Task, semantic_match="related concept")  # Uses default 0.4

# Loose (0.2-0.3): High recall, may include unrelated content
.consumes(Task, semantic_match="broad topic", semantic_threshold=0.3)
```

### 2. Use Field Extraction for Targeted Matching

Focus on relevant fields to improve accuracy:

```python
# Match only article body, ignore title and metadata
provider = SemanticContextProvider(
    query_text="AI research",
    extract_field="body",
    threshold=0.5
)
```

### 3. Combine Filters for Precision

Layer semantic matching with type and predicate filters:

```python
# Type + Predicate + Semantic filters
.consumes(
    LogEntry,
    where=lambda log: log.severity == "error",
    semantic_match="database connection"
)
```

### 4. Leverage Context Provider for Historical Insight

Enrich processing with relevant past artifacts:

```python
# Find similar past incidents to inform resolution
similar_incidents = await provider.get_context(store)
resolution_history = [s.payload["resolution"] for s in similar_incidents]
```

### 5. Monitor and Tune

Track matching behavior and adjust thresholds:

```python
class MonitoringEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Log semantic match scores for tuning
        ctx.logger.info(f"Matched with threshold {threshold}")
        return EvalResult(artifacts=[], state={})
```

## Graceful Degradation

If `sentence-transformers` is not installed:

- Semantic predicates are **ignored** (fall back to type matching)
- `SemanticContextProvider.get_context()` returns **empty list**
- Core Flock functionality is **unaffected**
- No crashes or errors

Check availability:

```python
from flock.semantic import SEMANTIC_AVAILABLE

if SEMANTIC_AVAILABLE:
    # Use semantic features
    .consumes(Task, semantic_match="urgent")
else:
    # Fall back to predicate matching
    .consumes(Task, where=lambda t: "urgent" in t.description.lower())
```

## Troubleshooting

### No Matches Despite Relevant Content

**Symptom**: Semantic matching not finding obviously relevant artifacts

**Solutions**:

1. **Lower the threshold**:
   ```python
   semantic_match={"query": "...", "threshold": 0.3}
   ```

2. **Use more general query terms**:
   ```python
   # Better: Broader terms
   semantic_match="database error"

   # Worse: Overly specific
   semantic_match="PostgreSQL connection timeout on port 5432"
   ```

3. **Check field extraction**:
   ```python
   # If matching wrong field, specify the right one
   semantic_match={"query": "...", "field": "description"}
   ```

4. **Verify installation**:
   ```bash
   python -c "from flock.semantic import SEMANTIC_AVAILABLE; print(SEMANTIC_AVAILABLE)"
   ```

### Performance Issues with Large Artifact Counts

**Symptom**: Slow semantic matching when many artifacts in store

**Solutions**:

1. **Add type filters**:
   ```python
   provider = SemanticContextProvider(
       query_text="...",
       artifact_type=SpecificType  # Reduces candidate set
   )
   ```

2. **Add predicate filters**:
   ```python
   where=lambda a: a.payload["status"] == "active"
   ```

3. **Use more specific queries** to reduce candidate matches

4. **Limit result count**:
   ```python
   provider = SemanticContextProvider(query_text="...", limit=10)
   ```

### Import Errors

**Symptom**: `ImportError: sentence-transformers not found`

**Solution**:
```bash
uv add flock-core[semantic]
# or
pip install flock-core[semantic]
```

### Memory Issues

**Symptom**: High memory usage with semantic features

**Causes and Solutions**:

1. **Model loading** (~150MB):
   - This is normal - model must be in memory
   - Consider if semantic features are needed

2. **Cache growth** (~6MB per 10k embeddings):
   - Cache auto-evicts at 10,000 entries (LRU)
   - No action needed - self-limiting

3. **Too many artifacts** in context retrieval:
   - Reduce `limit` parameter
   - Add more filters to narrow results

## Migration Guide

### From Type-Only Matching

**Before** (keyword matching):
```python
.consumes(
    SupportTicket,
    where=lambda t: any(kw in t.message.lower()
                       for kw in ["security", "vulnerability", "exploit"])
)
```

**After** (semantic matching):
```python
.consumes(SupportTicket, semantic_match="security vulnerability")
```

**Benefits**:
- Matches "SQL injection", "XSS attack", "data breach" automatically
- No brittle keyword lists to maintain
- Better recall with same precision

### Adding Context Retrieval

**Before** (no historical context):
```python
class MyEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Process in isolation
        return EvalResult(artifacts=[...])
```

**After** (with context):
```python
from flock.semantic import SemanticContextProvider

class MyEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group):
        # Retrieve relevant historical context
        provider = SemanticContextProvider(
            query_text=inputs.artifacts[0].payload["message"],
            threshold=0.4,
            limit=5
        )
        similar = await provider.get_context(flock.store)

        # Make informed decision with context
        return EvalResult(
            artifacts=[...],
            state={"context_count": len(similar)}
        )
```

## Technical Details

### Similarity Computation

Semantic similarity uses cosine similarity on normalized embeddings:

```python
similarity = cosine_similarity(embedding_a, embedding_b)
           = dot(embedding_a, embedding_b) / (norm(a) * norm(b))
```

**Result range**: [0.0, 1.0]
- **1.0**: Identical semantics
- **0.7-0.9**: Very similar concepts
- **0.4-0.6**: Related concepts
- **0.2-0.3**: Loosely related
- **0.0-0.1**: Unrelated

### Caching Strategy

LRU (Least Recently Used) cache with 10,000 entry capacity:

- **Cache key**: Hash of normalized text
- **Eviction**: Least recently used when full
- **Hit rate**: Typically 60-80% in production workloads
- **Memory**: ~6MB per 10,000 cached embeddings (384 floats each)
- **Persistence**: In-memory only (cleared on restart)

### Model Training

The `all-MiniLM-L6-v2` model is trained on:
- **Semantic textual similarity** datasets
- **Natural language inference** tasks
- **Paraphrase detection** tasks

This training enables it to understand semantic relationships beyond keyword overlap.

## Examples

See the [Semantic Routing Tutorial](../tutorials/semantic-routing.md) for a complete step-by-step example.

Additional examples in `examples/08-semantic/`:

- `00_verify_semantic_features.py` - Installation verification
- `01_intelligent_ticket_routing.py` - Multi-agent semantic routing
- `02_multi_criteria_filtering.py` - Multiple semantic predicates

## License

Semantic subscriptions use `sentence-transformers`, which is Apache 2.0 licensed.
