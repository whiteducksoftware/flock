# Feature Examples

**Purpose**: In-depth feature validation with explicit assertions

These examples validate specific Flock-Flow features with comprehensive test coverage. They're designed to:
- Validate feature behavior comprehensively
- Include explicit assertions to catch bugs
- Test edge cases and error handling
- Serve as executable documentation
- Prevent regressions

## Examples in This Directory

### `feedback_prevention.py` (Coming Soon)
**Feature**: Agent self-trigger prevention and circuit breakers
**Validates**:
- `prevent_self_trigger=True` (default) blocks infinite loops
- `where` predicates limit recursion depth
- Circuit breaker stops runaway agents at 1000 iterations

**Assertions**: Validates exact artifact counts match expectations

### More Coming Soon
Additional feature examples will be added for:
- Visibility controls (Public, Private, Labelled, Tenant, After)
- Subscription predicates and channel filtering
- Concurrency and batching
- Component lifecycle hooks
- Multiple agent coordination
- Error handling and recovery
- Telemetry and metrics
- Output utility components

## Running Feature Examples

```bash
# From project root
cd /home/ara/work/flock-flow

# Run feature validation examples
uv run python examples/features/feedback_prevention.py
```

**Note**: These examples include assertions. If an assertion fails, the example will raise an `AssertionError` with details about what went wrong.

## Creating New Feature Examples

**Checklist for feature examples**:
- [ ] Focus on ONE specific feature
- [ ] Include explicit assertions for all expected behaviors
- [ ] Test both happy path and edge cases
- [ ] Document what's being validated in comments
- [ ] Provide clear error messages in assertions
- [ ] Keep examples focused and concise

**Template**:
```python
"""
Feature Example: [Feature Name]

Validates: [Specific behaviors being tested]
"""
import asyncio
from flock.orchestrator import Flock

async def main():
    print("🧪 Feature: [Feature Name]")

    # Test Case 1: [Description]
    orchestrator = Flock()
    # ... setup and execution ...

    # Validate expected behavior
    assert condition, f"Expected [X], got [Y]"
    print("✅ [Test case 1 passed]")

    # Test Case 2: [Description]
    # ... more test cases ...

    print("\\n✅ All assertions passed! Feature working correctly.")

if __name__ == "__main__":
    asyncio.run(main())
```

## Why Feature Examples with Assertions?

Feature examples serve as:

1. **Regression Detection**: Assertions catch when features break
2. **Living Documentation**: Code shows exactly how features work
3. **Bug Prevention**: Testing edge cases reveals issues early
4. **Validation Tool**: Quick sanity check after changes
5. **Usage Reference**: Demonstrates correct API usage

## Feature vs Showcase

**Use features/** when:
- Validating specific feature behavior
- Testing edge cases and error paths
- Preventing regressions
- Documenting technical details

**Use showcase/** when:
- Demonstrating to audiences
- Creating engaging narratives
- Showing overall capabilities
- Onboarding non-technical users
