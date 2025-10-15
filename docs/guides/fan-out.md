---
title: Fan-Out Publishing
description: Produce multiple outputs from a single agent execution with filtering, validation, and dynamic visibility
tags:
  - fan-out
  - publishing
  - filtering
  - validation
  - advanced
search:
  boost: 2.0
---

# Fan-Out Publishing

Generate multiple artifacts from a single agent execution with intelligent filtering, validation, and per-artifact visibility control.

---

## Overview

**Fan-out publishing** allows agents to produce **multiple instances** of an output type in a single execution. Instead of generating one artifact, your agent can create N variants, apply quality filters, enforce validation rules, and control visibility per artifact.

**Why fan-out matters:**

- 🎯 **Content Generation** - Generate 10 blog ideas, keep top 3 by quality score
- 🐛 **Code Analysis** - Find 5 potential bugs, validate each has proper severity
- 📧 **Notifications** - Create personalized messages with dynamic recipient lists
- 🧪 **A/B Testing** - Generate variations, filter by quality metrics before publishing

---

## Basic Fan-Out

### Single Output (Default Behavior)

```python
from flock import Flock, flock_type
from pydantic import BaseModel

@flock_type
class ProductBrief(BaseModel):
    market: str
    audience: str

@flock_type
class ProductIdea(BaseModel):
    name: str
    description: str
    score: float

# Traditional: One idea per brief
flock = Flock("openai/gpt-4.1")
idea_generator = (
    flock.agent("generator")
    .consumes(ProductBrief)
    .publishes(ProductIdea)  # Produces 1 idea
)
```

### Multiple Outputs (Fan-Out)

```python
# Fan-out: Ten ideas per brief
idea_generator = (
    flock.agent("generator")
    .consumes(ProductBrief)
    .publishes(ProductIdea, fan_out=10)  # Produces 10 ideas!
)

# Now when you publish a brief:
await flock.publish(ProductBrief(market="EdTech", audience="Teachers"))
await flock.run_until_idle()

# Result: 10 ProductIdea artifacts published to the blackboard
ideas = await flock.store.get_by_type(ProductIdea)
print(f"Generated {len(ideas)} ideas")  # Output: Generated 10 ideas
```

**What just happened:**

- ✅ Single agent execution produced 10 artifacts
- ✅ Each artifact is independently published to the blackboard
- ✅ Downstream agents can consume any or all of them
- ✅ No manual loops or duplicate agent definitions needed

---

## WHERE Filtering

Filter outputs **before publishing** to reduce noise and save downstream processing costs.

### Basic Filtering

```python
# Only publish high-quality ideas (score >= 8.0)
idea_generator = (
    flock.agent("generator")
    .consumes(ProductBrief)
    .publishes(
        ProductIdea,
        fan_out=20,  # Generate 20 candidates
        where=lambda idea: idea.score >= 8.0  # Only publish if score >= 8
    )
)
```

**Result:**

- Engine generates 20 ProductIdea instances
- Filter evaluates: `lambda idea: idea.score >= 8.0` for each
- Only ideas with `score >= 8.0` are published
- If 3 pass the filter, 3 artifacts published (not 20!)

### Complex Predicates

```python
@flock_type
class CodeReview(BaseModel):
    file: str
    issue: str
    severity: str
    confidence: float
    line_number: int

# Only publish critical issues with high confidence
code_reviewer = (
    flock.agent("reviewer")
    .consumes(CodeSubmission)
    .publishes(
        CodeReview,
        fan_out=10,
        where=lambda r: r.severity == "Critical" and r.confidence >= 0.85
    )
)
```

### Multiple Conditions

```python
# Combine multiple conditions
product_ranker = (
    flock.agent("ranker")
    .consumes(SearchQuery)
    .publishes(
        Product,
        fan_out=50,  # Evaluate 50 products
        where=lambda p: (
            p.price < 100 and          # Under budget
            p.rating >= 4.5 and        # High rated
            p.in_stock and             # Available now
            len(p.reviews) >= 10       # Sufficient reviews
        )
    )
)
```

**When to use WHERE:**

- ✅ Reduce noise (only publish high-quality outputs)
- ✅ Save downstream costs (fewer artifacts = fewer agent activations)
- ✅ Implement business rules (only critical bugs, high-confidence predictions)
- ✅ Quality thresholds (score >= 8, confidence >= 0.9)

---

## VALIDATE Checks

Enforce **quality standards** with fail-fast validation. If any artifact fails validation, the entire execution raises an error.

### Single Validation

```python
# Enforce severity is a valid enum value
code_reviewer = (
    flock.agent("reviewer")
    .consumes(CodeSubmission)
    .publishes(
        CodeReview,
        fan_out=5,
        validate=lambda r: r.severity in ["Critical", "High", "Medium", "Low"]
    )
)
```

**Behavior:**

- If ANY review has invalid severity (e.g., "URGENT"), entire execution fails
- `ValueError` raised with error message
- No artifacts published (atomic operation)

### Multiple Checks with Custom Messages

```python
# Multiple validation rules with clear error messages
idea_validator = (
    flock.agent("validator")
    .consumes(ProductBrief)
    .publishes(
        ProductIdea,
        fan_out=10,
        validate=[
            (lambda i: i.score >= 0 and i.score <= 10, "Score must be between 0 and 10"),
            (lambda i: len(i.name) >= 5, "Name must be at least 5 characters"),
            (lambda i: len(i.description) >= 20, "Description must be at least 20 characters"),
            (lambda i: i.name != i.description, "Name and description must be different"),
        ]
    )
)
```

**Behavior:**

- ALL checks must pass for EVERY artifact
- First failing check raises `ValueError` with custom message
- Example error: `"Score must be between 0 and 10: __main__.ProductIdea"`
- No artifacts published if any check fails

### When to use VALIDATE

**✅ Use VALIDATE for:**

- Contract enforcement (required fields, enum values, ranges)
- Data integrity (foreign keys, checksums, formats)
- Business invariants (price > 0, date ranges, uniqueness)
- Quality gates (minimum length, required patterns, cross-field rules)

**❌ Don't use VALIDATE for:**

- Optional filtering (use `where` instead)
- Quality scores (use `where` for thresholds)
- Performance optimization (use `where` to reduce volume)

**Key difference:**

- **WHERE** = Reduce volume (filter out low-quality, keep good ones)
- **VALIDATE** = Enforce contracts (fail if ANY artifact is invalid)

---

## Dynamic Visibility

Control **per-artifact access** based on content. Instead of static visibility for all artifacts, compute visibility dynamically for each one.

### Static Visibility (Default)

```python
# All notifications go to the same agents
notifier = (
    flock.agent("notifier")
    .consumes(Alert)
    .publishes(
        Notification,
        fan_out=3,
        visibility=PrivateVisibility(agents=["admin", "operator"])  # Static
    )
)
```

### Dynamic Visibility

```python
from flock.visibility import PrivateVisibility

@flock_type
class Notification(BaseModel):
    recipient: str  # Agent name to notify
    message: str
    priority: str

# Compute visibility per artifact based on recipient field
notifier = (
    flock.agent("notifier")
    .consumes(Alert)
    .publishes(
        Notification,
        fan_out=3,
        visibility=lambda n: PrivateVisibility(agents=[n.recipient])  # Dynamic!
    )
)
```

**What just happened:**

- Each Notification artifact gets its own visibility
- `lambda n: PrivateVisibility(agents=[n.recipient])` computed per artifact
- Notification 1: recipient="admin" → only "admin" agent sees it
- Notification 2: recipient="operator" → only "operator" agent sees it
- Notification 3: recipient="security" → only "security" agent sees it

### Advanced Visibility Patterns

#### Role-Based Dynamic Visibility

```python
from flock.visibility import LabelledVisibility

@flock_type
class Report(BaseModel):
    title: str
    content: str
    classification: str  # "public", "confidential", "secret"

# Map classification to required labels
classification_to_labels = {
    "public": set(),
    "confidential": {"clearance:confidential"},
    "secret": {"clearance:secret"},
}

report_generator = (
    flock.agent("reporter")
    .consumes(ReportRequest)
    .publishes(
        Report,
        fan_out=5,
        visibility=lambda r: LabelledVisibility(
            required_labels=classification_to_labels[r.classification]
        )
    )
)
```

#### Tenant-Based Dynamic Visibility

```python
from flock.visibility import TenantVisibility

@flock_type
class CustomerData(BaseModel):
    customer_id: str
    data: dict

# Each customer's data only visible within their tenant
data_processor = (
    flock.agent("processor")
    .consumes(BatchRequest)
    .publishes(
        CustomerData,
        fan_out=100,  # Process 100 customers
        visibility=lambda d: TenantVisibility(tenant_id=d.customer_id)
    )
)
```

---

## Combining Features

Fan-out features compose naturally for powerful workflows.

### WHERE + VALIDATE

```python
# Generate many, filter quality, enforce standards
idea_machine = (
    flock.agent("generator")
    .consumes(ProductBrief)
    .publishes(
        ProductIdea,
        fan_out=50,  # Generate 50 candidates
        where=lambda i: i.score >= 7.0,  # Keep only score >= 7
        validate=[  # Enforce quality standards on those that pass filter
            (lambda i: len(i.name) >= 5, "Name too short"),
            (lambda i: i.score <= 10, "Score out of range"),
        ]
    )
)
```

**Execution order:**

1. Engine generates 50 ProductIdea instances
2. WHERE filter: Keep only `score >= 7.0` (maybe 15 remain)
3. VALIDATE checks: Ensure all 15 meet quality standards
4. If any validation fails: Raise error, publish nothing
5. If all pass: Publish 15 artifacts

### WHERE + VALIDATE + Dynamic Visibility

```python
# Complete workflow: Generate, filter, validate, target
notification_pipeline = (
    flock.agent("notifier")
    .consumes(AlertBatch)
    .publishes(
        Notification,
        fan_out=20,
        where=lambda n: n.priority in ["High", "Critical"],  # Filter by priority
        validate=[
            (lambda n: n.recipient in valid_agents, "Invalid recipient"),
            (lambda n: len(n.message) <= 500, "Message too long"),
        ],
        visibility=lambda n: PrivateVisibility(agents=[n.recipient])  # Target agent
    )
)
```

**What just happened:**

1. Generate 20 notification candidates
2. Filter: Keep only High/Critical priority (maybe 5 remain)
3. Validate: Check recipient is valid and message not too long
4. Visibility: Route each notification to its specific recipient
5. Publish: 5 artifacts, each visible only to its target agent

---

## Best Practices

### Fan-Out Count Selection

```python
# ✅ GOOD: Reasonable fan-out counts
.publishes(Idea, fan_out=10)     # Generate diverse ideas
.publishes(Review, fan_out=5)    # Multiple review perspectives
.publishes(Variant, fan_out=3)   # A/B/C testing

# ⚠️ CAREFUL: Large fan-out = high LLM costs
.publishes(Product, fan_out=100)  # 100 LLM calls per execution!

# ✅ BETTER: Combine with WHERE to reduce volume
.publishes(Product, fan_out=100, where=lambda p: p.score >= 8)  # Maybe 10 published
```

**Rule of thumb:**

- **fan_out <= 10**: Safe for most use cases
- **fan_out 11-50**: Monitor LLM costs, consider WHERE filtering
- **fan_out > 50**: Requires WHERE filtering or you'll burn budget

### WHERE vs VALIDATE

```python
# ❌ WRONG: Using VALIDATE for optional filtering
.publishes(
    Idea,
    fan_out=10,
    validate=lambda i: i.score >= 8  # Will fail if ANY idea scores < 8!
)

# ✅ CORRECT: Use WHERE for optional filtering
.publishes(
    Idea,
    fan_out=10,
    where=lambda i: i.score >= 8  # Filters out low-scoring ideas
)

# ✅ CORRECT: Use VALIDATE for contracts
.publishes(
    Idea,
    fan_out=10,
    validate=lambda i: i.score >= 0 and i.score <= 10  # Score must be valid range
)
```

### Error Handling

```python
# Validation failures are intentional errors
try:
    await flock.run_until_idle()
except ValueError as e:
    # Handle validation failure
    print(f"Quality check failed: {e}")
    # Maybe: retry with different parameters, alert operators, etc.
```

### Performance Optimization

```python
# ✅ EFFICIENT: Filter early to reduce downstream costs
analyzer = (
    flock.agent("analyzer")
    .consumes(Document)
    .publishes(
        Insight,
        fan_out=50,  # Generate 50 insights
        where=lambda i: i.confidence >= 0.9  # But only publish high-confidence ones
    )
)

# Downstream agents only process ~5 insights instead of 50
# Saves: 45 agent executions = 45x cost reduction!
```

---

## Common Patterns

### Content Generation Pipeline

```python
# Generate many, keep best
blog_writer = (
    flock.agent("writer")
    .consumes(Topic)
    .publishes(
        BlogPost,
        fan_out=10,
        where=lambda p: p.quality_score >= 8.5,
        validate=[(lambda p: len(p.content) >= 500, "Post too short")]
    )
)
```

### Code Review Automation

```python
# Find issues, validate severity
reviewer = (
    flock.agent("reviewer")
    .consumes(PullRequest)
    .publishes(
        Issue,
        fan_out=20,  # Look for up to 20 issues
        where=lambda i: i.severity != "Info",  # Skip informational
        validate=[
            (lambda i: i.severity in ["Critical", "High", "Medium", "Low"], "Invalid severity"),
            (lambda i: i.line_number > 0, "Invalid line number"),
        ]
    )
)
```

### A/B Testing Generator

```python
# Generate variants, ensure diversity
variant_generator = (
    flock.agent("generator")
    .consumes(ExperimentSpec)
    .publishes(
        Variant,
        fan_out=5,  # A, B, C, D, E variants
        validate=[
            (lambda v: len(v.name) > 0, "Variant needs name"),
            (lambda v: v.change_magnitude > 0, "Must have actual change"),
        ]
    )
)
```

### Multi-Tenant Notifications

```python
# Route to customers dynamically
notifier = (
    flock.agent("notifier")
    .consumes(Event)
    .publishes(
        Notification,
        fan_out=100,  # Notify up to 100 customers
        where=lambda n: n.customer_opted_in,  # Respect preferences
        visibility=lambda n: TenantVisibility(tenant_id=n.customer_id)
    )
)
```

---

## How It Works

### Engine Contract

Engines implement `evaluate_fanout()` to support fan-out publishing:

```python
from flock.engine import Engine, EvalResult
from flock.types import OutputGroup

class MyEngine(Engine):
    async def evaluate_fanout(
        self,
        ctx: Context,
        inputs: list[Artifact],
        output_group: OutputGroup
    ) -> EvalResult:
        """
        Generate exactly `output_group.total_count` artifacts.

        Returns:
            EvalResult with artifacts matching output_group specifications
        """
        artifacts = []

        # output_group contains all output declarations
        for output_decl in output_group.outputs:
            count = output_decl.count  # How many of this type to produce
            type_name = output_decl.spec.type_name

            # Generate 'count' instances of this type
            for i in range(count):
                artifact = self.generate_artifact(type_name, inputs)
                artifacts.append(artifact)

        return EvalResult(artifacts=artifacts)
```

**Default engines (DSPyEngine, LiteLLMEngine) support fan-out automatically.**

### Execution Pipeline

When an agent executes with fan-out:

1. **Engine Execution**: Engine's `evaluate_fanout()` generates exactly N artifacts
2. **Contract Validation**: Framework verifies engine produced expected count
3. **WHERE Filtering**: Apply predicates, reduce artifact set (non-error)
4. **VALIDATE Checks**: Enforce quality standards (error if any fail)
5. **Visibility Application**: Compute visibility per artifact (static or dynamic)
6. **Publishing**: Publish filtered, validated artifacts to blackboard

```python
# Example execution flow:
# 1. Engine generates: 20 ProductIdea instances
# 2. Contract check: ✅ 20 == fan_out=20
# 3. WHERE filter: score >= 8.0 → 5 ideas remain
# 4. VALIDATE: all 5 pass validation checks
# 5. Visibility: compute per artifact
# 6. Publish: 5 artifacts to blackboard
```

### Type Safety

Fan-out preserves full type safety:

```python
# Predicates receive Pydantic model instances
where=lambda idea: idea.score >= 8.0  # 'idea' is ProductIdea (not dict!)

# Framework reconstructs models from payload dicts before predicate evaluation
model_cls = type_registry.resolve(output_decl.spec.type_name)
model_instance = model_cls(**artifact.payload)
result = predicate(model_instance)
```

---

## Troubleshooting

### Issue: Engine produces wrong count

**Symptom**: `ValueError: Expected 10 artifacts, got 7`

**Cause**: Engine didn't fulfill fan-out contract

**Solution**: Ensure your custom engine produces exactly `count` artifacts:

```python
async def evaluate_fanout(self, ctx, inputs, output_group):
    artifacts = []
    for output_decl in output_group.outputs:
        for i in range(output_decl.count):  # Produce EXACTLY this many
            artifacts.append(self.generate_one())
    return EvalResult(artifacts=artifacts)
```

### Issue: Validation fails unexpectedly

**Symptom**: `ValueError: Score must be between 0 and 10: ProductIdea`

**Cause**: One or more artifacts failed validation

**Solution**: Debug by logging artifacts before validation:

```python
# Temporarily remove validate to see what's being generated
.publishes(ProductIdea, fan_out=10)  # Remove validate temporarily

# Check generated artifacts
ideas = await flock.store.get_by_type(ProductIdea)
for idea in ideas:
    print(f"Idea: {idea.name}, Score: {idea.score}")  # Find the bad one
```

### Issue: No artifacts published

**Symptom**: `where` filter excludes everything

**Solution**: Check your predicate logic:

```python
# Too restrictive?
where=lambda i: i.score >= 9.5  # Maybe nothing scores this high

# Adjust threshold or add logging
where=lambda i: i.score >= 8.0  # More reasonable
```

### Issue: Dynamic visibility not working

**Symptom**: Wrong agents receiving artifacts

**Cause**: Visibility function returns wrong value

**Solution**: Test visibility function in isolation:

```python
# Test visibility logic
test_notification = Notification(recipient="admin", message="test", priority="High")
visibility = lambda n: PrivateVisibility(agents=[n.recipient])
result = visibility(test_notification)
print(f"Agents: {result.agents}")  # Should be ['admin']
```

---

## Migration Guide

### From Single Output

```python
# Before: One idea per execution
old_agent = (
    flock.agent("generator")
    .consumes(Brief)
    .publishes(Idea)
)

# After: Multiple ideas per execution
new_agent = (
    flock.agent("generator")
    .consumes(Brief)
    .publishes(Idea, fan_out=10)
)
```

### From Manual Loops

```python
# ❌ Before: Manual loop (inefficient)
for i in range(10):
    await flock.invoke(agent, brief, publish_outputs=True)
# Result: 10 separate agent executions

# ✅ After: Fan-out (efficient)
agent.publishes(Idea, fan_out=10)
await flock.invoke(agent, brief, publish_outputs=True)
# Result: 1 agent execution producing 10 artifacts
```

### Adding Filtering

```python
# Before: No filtering
.publishes(Idea, fan_out=20)

# After: Filter for quality
.publishes(
    Idea,
    fan_out=20,
    where=lambda i: i.score >= 8.0
)
```

### Adding Validation

```python
# Before: Hope for valid outputs
.publishes(Review, fan_out=5)

# After: Enforce validity
.publishes(
    Review,
    fan_out=5,
    validate=lambda r: r.severity in ["Critical", "High", "Medium", "Low"]
)
```

---

## Next Steps

- **[Agent Guide](agents.md)** - Complete agent development reference
- **[Visibility Guide](visibility.md)** - Deep dive on visibility controls
- **[Testing Guide](testing.md)** - Test fan-out agents effectively
- **[Examples](../../examples/)** - See fan-out in action

---

## Summary

Fan-out publishing transforms single-output agents into multi-output generators with:

- 🎯 **fan_out=N** - Produce N artifacts per execution
- 🔍 **where** - Filter outputs before publishing (reduce noise)
- ✅ **validate** - Enforce quality standards (fail-fast)
- 🔒 **visibility** - Control access per artifact (static or dynamic)

**Key principles:**

- WHERE filters (reduce volume, non-error)
- VALIDATE enforces (fail-fast, atomic)
- Visibility can be computed per artifact
- All features compose naturally

**Use fan-out when you need:**

- Multiple variations/perspectives from one execution
- Quality filtering before publishing downstream
- Dynamic routing based on artifact content
- Efficient multi-output generation

---

*Last updated: October 15, 2025*
