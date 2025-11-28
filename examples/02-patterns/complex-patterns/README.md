# Complex Patterns

Advanced workflow patterns for sophisticated agent orchestration.

## Examples

### 01_fan_out_selection.py

**Three patterns for reacting to "the best" from fan-out outputs:**

| Pattern | Approach | Pros | Cons | Use When |
|---------|----------|------|------|----------|
| **1. Threshold** | `where=lambda h: h.confidence >= 0.85` | Simple, no extra agents | Not guaranteed "THE best", 0-N matches | "Good enough" is acceptable |
| **2. Two-Stage** | `batch=BatchSpec(size=5)` + selector agent | Guaranteed single best | Extra LLM call | Need deterministic selection |
| **3. Self-Selection** | `is_recommended=True` field | Single LLM call, full context | Relies on LLM compliance | LLM is reliable |

```bash
# Run with Pattern 3 (default)
uv run python examples/02-patterns/complex-patterns/01_fan_out_selection.py

# Edit PATTERN variable (1, 2, or 3) to try different approaches
```

## When to Use Complex Patterns

- **Fan-out with selection**: When you need ONE output from N variations
- **Multi-stage processing**: When artifacts need transformation or filtering
- **Conditional cascades**: When downstream behavior depends on artifact content

## Related Examples

- `examples/02-patterns/publish/04-fan-out.py` - Basic fan-out
- `examples/02-patterns/publish/06_dynamic_fan_out.py` - Dynamic range fan-out
- `examples/01-getting-started/10_workflow_conditions.py` - Until conditions
