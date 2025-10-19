---
title: Testing Strategies
description: Comprehensive guide to testing Flock agents - unit tests, integration tests, mocking, and best practices
tags:
  - testing
  - quality
  - best-practices
search:
  boost: 1.3
---

# 🧪 Testing Flock Agents

Testing multi-agent systems can be challenging, but Flock's declarative architecture makes it straightforward. This guide covers testing strategies from unit tests to integration tests.

---

## 🎯 Testing Philosophy

### Why Flock Makes Testing Easier

**Declarative architecture enables isolation:**
- ✅ **Agent isolation** - Test agents independently without the full workflow
- ✅ **Type contracts** - Mock inputs and outputs with Pydantic models
- ✅ **Deterministic behavior** - Same inputs produce same outputs (with temperature=0)
- ✅ **No graph dependencies** - No need to wire up entire workflows for unit tests

**Traditional graph-based frameworks:**
- ❌ Require full graph instantiation
- ❌ Tight coupling makes isolation difficult
- ❌ Hard to mock intermediate states

---

## 📊 Test Categories

### 1. Unit Tests - Individual Agent Behavior

Test a single agent in isolation with mocked inputs.

```python
import pytest
from pydantic import BaseModel
from flock import Flock, flock_type

@flock_type
class CodeSnippet(BaseModel):
    code: str
    language: str

@flock_type
class BugReport(BaseModel):
    bugs_found: list[str]
    severity: str

@pytest.mark.asyncio
async def test_bug_detector_finds_null_pointer():
    """Unit test: Bug detector identifies null pointer issues."""
    # Arrange
    flock = Flock("openai/gpt-4.1", temperature=0)
    bug_detector = flock.agent("bug_detector").consumes(CodeSnippet).publishes(BugReport)

    test_code = CodeSnippet(
        code="def foo(x): return x.bar",
        language="python"
    )

    # Act
    await flock.publish(test_code)
    await flock.run_until_idle()

    # Assert
    reports = await flock.store.get_by_type(BugReport)
    assert len(reports) == 1
    assert any("null" in bug.lower() or "none" in bug.lower() for bug in reports[0].bugs_found)
    assert reports[0].severity in ["Critical", "High", "Medium", "Low"]
```

**Best practices:**
- Use `temperature=0` for deterministic outputs
- Test one agent at a time
- Mock external dependencies
- Assert on type constraints (Pydantic validates structure)

---

### 2. Integration Tests - Multi-Agent Workflows

Test multiple agents working together.

```python
@pytest.mark.asyncio
async def test_code_review_workflow():
    """Integration test: Full code review with bug detection and security audit."""
    # Arrange
    flock = Flock("openai/gpt-4.1", temperature=0)

    @flock_type
    class CodeSubmission(BaseModel):
        code: str
        language: str

    @flock_type
    class BugAnalysis(BaseModel):
        bugs_found: list[str]
        severity: str

    @flock_type
    class SecurityAnalysis(BaseModel):
        vulnerabilities: list[str]
        risk_level: str

    @flock_type
    class FinalReview(BaseModel):
        overall_assessment: str
        action_items: list[str]

    # Setup agents
    bug_detector = flock.agent("bug_detector").consumes(CodeSubmission).publishes(BugAnalysis)
    security = flock.agent("security").consumes(CodeSubmission).publishes(SecurityAnalysis)
    reviewer = flock.agent("reviewer").consumes(BugAnalysis, SecurityAnalysis).publishes(FinalReview)

    # Act
    await flock.publish(CodeSubmission(
        code="def process(data): eval(data)",  # Obvious security issue
        language="python"
    ))
    await flock.run_until_idle()

    # Assert workflow completion
    bug_reports = await flock.store.get_by_type(BugAnalysis)
    security_reports = await flock.store.get_by_type(SecurityAnalysis)
    reviews = await flock.store.get_by_type(FinalReview)

    assert len(bug_reports) == 1
    assert len(security_reports) == 1
    assert len(reviews) == 1

    # Assert security issue detected
    assert any("eval" in vuln.lower() for vuln in security_reports[0].vulnerabilities)
    assert security_reports[0].risk_level in ["Critical", "High"]
```

**Best practices:**
- Test end-to-end workflows
- Verify all expected artifacts are published
- Check agent coordination (parallel execution, dependency waiting)
- Use realistic test data

---

### 3. Contract Tests - Type Safety Validation

Test that agents respect Pydantic contracts.

```python
import pytest
from pydantic import ValidationError, Field

@flock_type
class StrictAnalysis(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    category: str = Field(pattern="^(Bug|Security|Performance)$")
    description: str = Field(min_length=20, max_length=500)

@pytest.mark.asyncio
async def test_analysis_respects_constraints():
    """Contract test: Agent outputs respect field constraints."""
    flock = Flock("openai/gpt-4.1", temperature=0)

    @flock_type
    class Input(BaseModel):
        data: str

    analyzer = flock.agent("analyzer").consumes(Input).publishes(StrictAnalysis)

    # Act
    await flock.publish(Input(data="Test input"))
    await flock.run_until_idle()

    # Assert - if this doesn't raise, Pydantic validated the output
    analyses = await flock.store.get_by_type(StrictAnalysis)
    assert len(analyses) == 1

    analysis = analyses[0]
    assert 0.0 <= analysis.confidence <= 1.0
    assert analysis.category in ["Bug", "Security", "Performance"]
    assert 20 <= len(analysis.description) <= 500

def test_invalid_analysis_rejected():
    """Contract test: Invalid outputs are rejected."""
    with pytest.raises(ValidationError):
        StrictAnalysis(
            confidence=1.5,  # > 1.0, should fail
            category="Invalid",  # Not in allowed values
            description="Too short"  # < 20 chars
        )
```

**Best practices:**
- Test field constraints (min/max, patterns, ranges)
- Verify Pydantic validation catches invalid data
- Use explicit test cases for edge cases

---

### 4. Conditional Subscription Tests

Test agents with `where` clauses.

```python
@pytest.mark.asyncio
async def test_conditional_consumption():
    """Test agent only processes high-severity items."""
    flock = Flock("openai/gpt-4.1")

    @flock_type
    class Alert(BaseModel):
        message: str
        severity: str

    @flock_type
    class EscalatedAlert(BaseModel):
        original: Alert
        escalated_to: str

    # Only process Critical/High severity
    escalator = flock.agent("escalator").consumes(
        Alert,
        where=lambda a: a.severity in ["Critical", "High"]
    ).publishes(EscalatedAlert)

    # Act
    await flock.publish(Alert(message="Server down", severity="Critical"))
    await flock.publish(Alert(message="Typo in docs", severity="Low"))
    await flock.run_until_idle()

    # Assert - only Critical alert was escalated
    escalations = await flock.store.get_by_type(EscalatedAlert)
    assert len(escalations) == 1
    assert escalations[0].original.severity == "Critical"
```

---

### 5. Batch Processing Tests

Test agents with batch specifications.

```python
from datetime import timedelta
from flock.subscription import BatchSpec

@pytest.mark.asyncio
async def test_batch_processing():
    """Test agent batches multiple events."""
    flock = Flock("openai/gpt-4.1")

    @flock_type
    class Event(BaseModel):
        data: str

    @flock_type
    class BatchSummary(BaseModel):
        event_count: int
        summary: str

    # Wait for 5 events or 30 seconds
    batch_processor = flock.agent("batcher").consumes(
        Event,
        batch=BatchSpec(size=5, timeout=timedelta(seconds=30))
    ).publishes(BatchSummary)

    # Act - publish 5 events
    for i in range(5):
        await flock.publish(Event(data=f"Event {i}"))

    await flock.run_until_idle()

    # Assert - agent processed batch of 5
    summaries = await flock.store.get_by_type(BatchSummary)
    assert len(summaries) == 1
    assert summaries[0].event_count == 5
```

---

### 6. Visibility and Security Tests

Test access control with visibility types.

```python
from flock.core.visibility import PrivateVisibility, TenantVisibility
from flock.identity import AgentIdentity

@pytest.mark.asyncio
async def test_private_visibility_access_control():
    """Test private visibility restricts access."""
    flock = Flock("openai/gpt-4.1")

    @flock_type
    class SensitiveData(BaseModel):
        secret: str

    @flock_type
    class ProcessedData(BaseModel):
        result: str

    # Publisher restricts to specific agent
    publisher = flock.agent("publisher").publishes(
        SensitiveData,
        visibility=PrivateVisibility(agents={"authorized_processor"})
    )

    # Authorized agent should see it
    authorized = (
        flock.agent("authorized_processor")
        .identity(AgentIdentity(name="authorized_processor"))
        .consumes(SensitiveData)
        .publishes(ProcessedData)
    )

    # Unauthorized agent should NOT see it
    unauthorized = (
        flock.agent("hacker")
        .identity(AgentIdentity(name="hacker"))
        .consumes(SensitiveData)
        .publishes(ProcessedData)
    )

    # Act
    await flock.publish(SensitiveData(secret="classified"))
    await flock.run_until_idle()

    # Assert - only authorized agent processed it
    results = await flock.store.get_by_type(ProcessedData)
    assert len(results) == 1  # Only one processor ran

    # Verify it was the authorized one by checking trace
    # (In production, use tracing to verify)
```

---

## 🛠️ Testing Patterns

### Pattern 1: Arrange-Act-Assert

```python
@pytest.mark.asyncio
async def test_agent_behavior():
    # Arrange - Setup
    flock = Flock("openai/gpt-4o-mini", temperature=0)
    agent = flock.agent("test_agent").consumes(Input).publishes(Output)
    test_input = Input(data="test")

    # Act - Execute
    await flock.publish(test_input)
    await flock.run_until_idle()

    # Assert - Verify
    outputs = await flock.store.get_by_type(Output)
    assert len(outputs) == 1
    assert outputs[0].field == expected_value
```

### Pattern 2: Parametrized Tests

```python
@pytest.mark.parametrize("severity,expected_action", [
    ("Critical", "page_oncall"),
    ("High", "send_email"),
    ("Medium", "log_warning"),
    ("Low", "ignore"),
])
@pytest.mark.asyncio
async def test_severity_routing(severity, expected_action):
    """Test different severity levels route correctly."""
    flock = Flock("openai/gpt-4.1")

    @flock_type
    class Alert(BaseModel):
        severity: str

    @flock_type
    class Action(BaseModel):
        action_type: str

    handler = flock.agent("handler").consumes(Alert).publishes(Action)

    await flock.publish(Alert(severity=severity))
    await flock.run_until_idle()

    actions = await flock.store.get_by_type(Action)
    assert actions[0].action_type == expected_action
```

### Pattern 3: Fixtures for Reusability

```python
@pytest.fixture
async def code_review_flock():
    """Reusable flock setup for code review tests."""
    flock = Flock("openai/gpt-4.1", temperature=0)

    @flock_type
    class CodeSubmission(BaseModel):
        code: str

    @flock_type
    class Review(BaseModel):
        rating: int
        comments: list[str]

    reviewer = flock.agent("reviewer").consumes(CodeSubmission).publishes(Review)

    yield flock  # Provide to test

    # Cleanup (if needed)
    await flock.store.clear()

@pytest.mark.asyncio
async def test_with_fixture(code_review_flock):
    """Test using reusable fixture."""
    await code_review_flock.publish(CodeSubmission(code="def foo(): pass"))
    await code_review_flock.run_until_idle()

    reviews = await code_review_flock.store.get_by_type(Review)
    assert len(reviews) == 1
```

---

## 🎓 Advanced Testing Techniques

### Mocking External Services

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
@patch('external_api.call_service')
async def test_agent_with_mocked_api(mock_call):
    """Test agent that calls external API."""
    mock_call.return_value = {"result": "mocked_response"}

    flock = Flock("openai/gpt-4.1")
    # ... rest of test
```

### Testing Circuit Breakers

```python
@pytest.mark.asyncio
async def test_circuit_breaker_prevents_runaway():
    """Test circuit breaker stops infinite loops."""
    flock = Flock("openai/gpt-4.1", max_agent_iterations=100)

    @flock_type
    class Trigger(BaseModel):
        count: int

    # Agent that triggers itself (feedback loop)
    looper = flock.agent("looper").consumes(Trigger).publishes(Trigger)

    await flock.publish(Trigger(count=0))

    with pytest.raises(Exception) as exc_info:
        await flock.run_until_idle()

    assert "max_agent_iterations" in str(exc_info.value)
```

### Testing with Tracing

```python
@pytest.mark.asyncio
async def test_with_tracing():
    """Test with tracing enabled for debugging."""
    import os
    os.environ["FLOCK_AUTO_TRACE"] = "true"

    flock = Flock("openai/gpt-4.1")

    async with flock.traced_run("test_workflow"):
        # ... test code
        pass

    # Query traces for assertions
    import duckdb
    conn = duckdb.connect('.flock/traces.duckdb')
    traces = conn.execute("""
        SELECT name, duration_ms
        FROM spans
        WHERE trace_name = 'test_workflow'
    """).fetchall()

    assert len(traces) > 0
```

---

## 📏 Coverage Requirements

### Flock Project Standards

- **Overall coverage:** 75%+ minimum (currently 77.65%)
- **Critical paths:** 100% (orchestrator, subscription, visibility, agent)
- **Frontend:** 80%+ recommended

### Running Coverage

```bash
# Backend coverage
poe test-cov

# With failure on < 80%
poe test-cov-fail

# Critical path tests (must pass)
poe test-critical

# Frontend coverage
cd frontend && npm test -- --coverage

# E2E tests
poe test-e2e
```

---

## ⚠️ Common Pitfalls

### 1. Non-Deterministic Outputs

**Problem:** LLM outputs vary, tests flake.

**Solution:** Use `temperature=0` and specific prompts.

```python
# ❌ Flaky test
flock = Flock("openai/gpt-4.1")  # Default temperature=1.0

# ✅ Deterministic test
flock = Flock("openai/gpt-4.1", temperature=0)
```

### 2. Forgetting to Await `run_until_idle()`

**Problem:** Agents don't execute, assertions fail.

```python
# ❌ Forgot to run
await flock.publish(input)
results = await flock.store.get_by_type(Output)  # Empty!

# ✅ Correct
await flock.publish(input)
await flock.run_until_idle()  # Let agents execute
results = await flock.store.get_by_type(Output)
```

### 3. Over-Asserting on LLM Output

**Problem:** Tests break on minor wording changes.

**Solution:** Assert on structure, not exact text.

```python
# ❌ Too brittle
assert result.summary == "The code has a null pointer exception in line 5"

# ✅ Assert on structure
assert "null" in result.summary.lower()
assert result.severity in ["Critical", "High"]
assert len(result.summary) > 20
```

### 4. Not Testing Visibility

**Problem:** Security bugs slip through.

**Solution:** Explicitly test access control.

```python
@pytest.mark.asyncio
async def test_unauthorized_access_blocked():
    """Test unauthorized agents cannot access private data."""
    # Setup with visibility restrictions
    # Assert unauthorized agent received nothing
```

---

## 🚀 Testing Best Practices

### 1. Test Pyramid Strategy

```
       /\
      /E2E\       <- Few (5-10 tests)
     /------\
    /Integr.\    <- Medium (20-30 tests)
   /----------\
  /Unit Tests \  <- Many (100+ tests)
 /--------------\
```

- **Many unit tests** - Fast, isolated, test individual agents
- **Medium integration tests** - Test multi-agent coordination
- **Few E2E tests** - Test complete workflows

### 2. Keep Tests Fast

```python
# ✅ Use small models for tests
flock = Flock("openai/gpt-4.1")

# ✅ Use minimal data
test_input = CodeSnippet(code="def foo(): pass")  # Not 1000 lines

# ✅ Run tests in parallel
pytest -n auto  # Parallel execution
```

### 3. Test Names Should Tell a Story

```python
# ✅ Good names
def test_bug_detector_identifies_null_pointer_in_python_code()
def test_security_agent_flags_sql_injection_vulnerability()
def test_reviewer_waits_for_both_bug_and_security_analysis()

# ❌ Bad names
def test_agent_1()
def test_workflow()
```

### 4. Use Descriptive Docstrings

```python
@pytest.mark.asyncio
async def test_conditional_routing():
    """
    Test that urgent cases (Critical/High) are routed to on-call team
    while non-urgent cases (Medium/Low) are routed to email queue.

    Validates:
    - Conditional consumption with 'where' clause
    - Multiple agents consuming same type with different filters
    - Correct routing based on severity field
    """
    # Test implementation
```

---

## 📚 Example Test Suite Structure

```
tests/
├── unit/
│   ├── test_agents.py           # Individual agent behavior
│   ├── test_subscriptions.py    # Subscription patterns
│   └── test_visibility.py       # Access control
├── integration/
│   ├── test_workflows.py        # Multi-agent workflows
│   ├── test_parallel.py         # Parallel execution
│   └── test_dependencies.py     # Dependency resolution
├── contract/
│   └── test_types.py            # Pydantic validation
├── e2e/
│   └── test_complete_flows.py  # End-to-end scenarios
└── conftest.py                  # Shared fixtures
```

---

## 🎯 Testing Checklist

Before committing code, verify:

- [ ] All tests pass (`poe test`)
- [ ] Coverage requirements met (`poe test-cov-fail`)
- [ ] Critical paths at 100% (`poe test-critical`)
- [ ] Frontend tests pass (`cd frontend && npm test`)
- [ ] No flaky tests (run 3x to verify)
- [ ] Test names are descriptive
- [ ] Edge cases covered
- [ ] Happy path + error path tested
- [ ] Visibility/security tested (if applicable)

---

## 📖 Related Documentation

- **[Contributing Guide](../about/contributing.md)** - Development workflow and standards
- **[Patterns Guide](patterns.md)** - Production patterns and anti-patterns
- **[API Reference](../reference/api.md)** - Complete API documentation

---

**Last Updated:** October 8, 2025
**Coverage Target:** 75%+ overall, 100% on critical paths
**Test Philosophy:** Fast, isolated, deterministic

---

**"Test agents like you test microservices: isolated units, integrated workflows, and end-to-end validation."**
