# AGENTS.md

**Welcome, AI coding agent!** 👋

This is Flock Flow, a production-grade blackboard-first AI agent orchestration framework. This guide gets you up to speed quickly on the current project state and development patterns.

**Current Version:** Backend: 0.5.0b63 • Frontend: 0.1.4
**Architecture:** Hybrid Python/TypeScript with real-time dashboard
**Package Manager:** UV (NOT pip!)
**Status:** Production-ready with comprehensive monitoring

---

## 🎯 Project Snapshot

### What Is Flock Flow?

A blackboard architecture framework where specialized AI agents collaborate through a shared typed workspace—no direct coupling, no rigid workflows, just emergent intelligence.

**Core Pattern:** Blackboard Architecture (like Hearsay-II from 1970s, but for modern LLMs)

**Key Differentiator:** The only framework treating blackboard orchestration as a first-class citizen with built-in visibility controls, real-time monitoring, and enterprise-grade safety features.

### Architecture in 30 Seconds

```
┌─────────────────────────────────────────────┐
│         Blackboard (Typed Artifacts)        │
│  ┌──────┐ → ┌──────┐ → ┌──────┐ → ┌──────┐│
│  │ Idea │   │Movie │   │Script│   │Review││
│  └──────┘   └──────┘   └──────┘   └──────┘│
└─────────────────────────────────────────────┘
      ↑           ↑           ↑           ↑
  Agent A     Agent B     Agent C     Agent D
  (produce)   (consume    (consume    (consume
              & produce)  & produce)  & produce)
```

**Key Concepts:**
- **Artifacts:** Typed data (Pydantic models) published to blackboard
- **Subscriptions:** Declarative rules for when agents react
- **Visibility:** Built-in access control (Public/Private/Tenant/Label-based/Time-based)
- **Components:** Pluggable utilities (metrics, budgets, guards) + engines (DSPy, custom)
- **Real-time Dashboard:** React/TypeScript interface for live monitoring

---

## 🚀 Quick Setup

### Prerequisites

- **Python 3.10+** (we use modern async features)
- **UV package manager** (faster than pip, handles virtual envs)
- **Node.js 18+** (22+ recommended) for dashboard frontend
- **OpenAI API key** (for running examples)

### Installation

```bash
# Clone repo
git clone https://github.com/yourusername/flock-flow.git
cd flock-flow

# Install Python dependencies (UV creates venv automatically)
poe install  # Equivalent to: uv sync --dev --all-groups --all-extras

# Set up environment
export OPENAI_API_KEY="sk-..."
export DEFAULT_MODEL="openai/gpt-4.1"

# Verify installation
uv run python -c "from flock import Flock; print('✅ Ready!')"
```

### Run Examples

```bash
# CLI examples (with detailed output)
uv run python examples/01-cli/01_declarative_pizza.py
uv run python examples/01-cli/02_input_and_output.py
uv run python examples/01-cli/03_code_detective.py

# Dashboard examples (with visualization)
uv run python examples/02-dashboard/01_declarative_pizza.py
uv run python examples/02-dashboard/02_input_and_output.py
uv run python examples/02-dashboard/03_code_detective.py
```

---

## 📚 Detailed Guides

For deep dives into specific topics, see:

- **[Architecture & Blackboard](docs/guides/blackboard.md)** - Core pattern, structure, and behavior
- **[Development Workflow](docs/about/contributing.md)** - Testing, quality, versioning, pre-commit
- **[Frontend/Dashboard](docs/guides/dashboard.md)** - Dashboard usage and development
- **[Configuration & Dependencies](docs/reference/configuration.md)** - Environment and setup
- **[Patterns & Common Tasks](docs/guides/patterns.md)** - Recipes, performance, security

---

## 🚨 CRITICAL PATTERNS (Learn from Our Experience)

### ⚡ invoke() vs run_until_idle() - Execution Control (no double-run by default)

**This pattern cost us hours of debugging - learn from our pain!**

#### The Goal
Choose between isolated agent execution and event-driven cascades.

#### How it works
`invoke()` behavior depends on `publish_outputs`:

```python
# Isolated: execute agent only (no cascade)
await orchestrator.invoke(agent, input_artifact, publish_outputs=False)

# Cascading: execute and publish outputs, then run downstream agents
await orchestrator.invoke(agent, input_artifact, publish_outputs=True)
await orchestrator.run_until_idle()  # processes downstream agents
```

Notes:
- By default, agents have `prevent_self_trigger=True`, so an agent will not re-run on its own outputs when you call `run_until_idle()`. Downstream agents that subscribe to the output types will run.

#### When to Use Which Pattern

**✅ USE `publish_outputs=False` for:**
- Unit testing specific agent behavior
- Testing component hooks in isolation
- Direct execution without cascade
- Most test scenarios

```python
# ✅ CORRECT: Test component execution order
await orchestrator.invoke(agent, input_artifact, publish_outputs=False)
assert component_order == ["A", "B", "C"]
```

**✅ USE `publish_outputs=True` + `run_until_idle()` for:**
- Integration testing agent cascades
- Testing multi-agent workflows
- End-to-end scenario validation
- Event-driven behavior testing

```python
# ✅ CORRECT: Test agent cascade
await orchestrator.invoke(agent_a, input_artifact, publish_outputs=True)
await orchestrator.run_until_idle()  # Process agent_b, agent_c...
assert len(output_artifacts) == 3
```

#### Quick Reference

| Scenario | invoke() call | run_until_idle() | Result |
|----------|---------------|------------------|--------|
| Unit test | `invoke(..., publish_outputs=False)` | No | Single execution |
| Integration test | `invoke(..., publish_outputs=True)` | Yes | Cascade to downstream agents |
| Common mistake | `invoke(..., publish_outputs=True)` | Yes | Not a double-run; downstream agents run |

Rule of thumb: start with `publish_outputs=False` for unit tests; enable publication only when you want cascades.

---

### ⚡ Batching Pattern: publish() + run_until_idle() Separation = Parallel Power

**Why `run_until_idle()` is separate from `publish()` - it's not a bug, it's a feature!**

#### Sequential vs Parallel Execution

**❌ If `run_until_idle()` was built into `publish()`:**
```python
# Hypothetical auto-run design
await flock.publish(review1)  # Publishes AND waits for completion
await flock.publish(review2)  # Publishes AND waits for completion
await flock.publish(review3)  # Publishes AND waits for completion

# Result: SEQUENTIAL processing (3x time)
```

**✅ With current design (separated):**
```python
# Queue up multiple artifacts
await flock.publish(review1)  # Schedules agents
await flock.publish(review2)  # Schedules agents
await flock.publish(review3)  # Schedules agents

# Now trigger execution
await flock.run_until_idle()  # All independent agents run in PARALLEL!

# Result: PARALLEL processing (~1x time if agents are independent)
```

#### Best Practices

**✅ DO: Batch when possible**
```python
# Good: Batch-publish customer reviews
for review in customer_reviews:
    await flock.publish(review)
await flock.run_until_idle()
```

**✅ DO: Use for multi-type workflows**
```python
# Good: Publish different types, let agents run in parallel
await flock.publish(XRayImage(...))
await flock.publish(LabResults(...))
await flock.publish(PatientHistory(...))
await flock.run_until_idle()  # Radiologist, lab_tech, historian run concurrently
```

**⚠️ CAREFUL: Separate workflows with traced_run()**
```python
# Better: Separate workflows explicitly
async with flock.traced_run("review_workflow"):
    await flock.publish(review_workflow_input)
    await flock.run_until_idle()

async with flock.traced_run("order_workflow"):
    await flock.publish(order_workflow_input)
    await flock.run_until_idle()
```

#### Key Takeaway

The separation of `publish()` and `run_until_idle()` gives you **control over execution timing and batching**. This enables:
- ⚡ **Parallel execution** when agents are independent
- 🎛️ **Fine-grained control** over when execution happens
- 📊 **Better performance** for bulk operations
- 🔍 **Clearer workflow boundaries** with `traced_run()`

**This is not a bug or oversight - it's a fundamental design choice that enables patterns other frameworks can't easily support.**

---

### 🗄️ Persistent Blackboard History (SQLite Store)

**Production teams asked for auditability—now the blackboard can keep a full historical trail.**

#### Why this matters
- **Durable artifacts**: Everything on the blackboard (payloads, tags, visibility, correlation IDs) is stored on disk for replay, compliance, and debugging.
- **Faster postmortems**: Query `/api/v1/artifacts` with filters (`type`, `produced_by`, `tags`, `visibility`, time windows) to reconstruct agent cascades after the fact.
- **Operational dashboards**: The new **Historical Blackboard** module preloads persisted pages, exposes consumption metadata, and shows retention banners so operators know how far back they can scroll.
- **Retention policies**: CLI helpers make maintenance routine—`flock sqlite-maintenance my.db --delete-before 2025-01-01T00:00:00Z --vacuum` prunes old artifacts and compacts the store.

#### Quick start
```python
from flock import Flock
from flock.store import SQLiteBlackboardStore

store = SQLiteBlackboardStore(".flock/history.db")
await store.ensure_schema()

flock = Flock("openai/gpt-4.1", store=store)
await flock.publish(MyDreamPizza(pizza_idea="fermented garlic delight"))
await flock.run_until_idle()
```

Kick the tyres with `examples/02-the-blackboard/01_persistent_pizza.py`, then launch `examples/03-the-dashboard/04_persistent_pizza_dashboard.py` to inspect the retained history alongside live WebSocket updates.

> **Heads-up:** The interface now returns `ArtifactEnvelope` objects when `embed_meta=True`. Future backends (Postgres, BigQuery, etc.) can implement the same contract to plug straight into the runtime and dashboard.

---

### 🔒 Test Isolation and Mock Cleanup - The Contamination Trap

**We fixed 32 failing tests caused by test contamination - here's what we learned:**

#### The Problem
Tests were modifying class-level properties with PropertyMock that persisted across test boundaries:

```python
# ❌ WRONG: Contaminates other tests
def test_something(orchestrator):
    type(orchestrator).agents = PropertyMock(return_value=[mock_agent])
    # No cleanup - mock persists!
```

#### The Solution
Always use fixture cleanup with yield pattern:

```python
# ✅ CORRECT: Proper cleanup
@pytest.fixture
def dashboard_service_with_mocks(orchestrator):
    original_agents = getattr(type(orchestrator), "agents", None)
    type(orchestrator).agents = PropertyMock(return_value=[mock_agent])
    try:
        yield service
    finally:
        # Restore original or delete if it didn't exist
        if original_agents is not None:
            type(orchestrator).agents = original_agents
        elif hasattr(type(orchestrator), "agents"):
            delattr(type(orchestrator), "agents")
```

#### Best Practices for Test Isolation

1. **Create Helper Functions for Complex Mocks**
2. **Use Fixture Cleanup Pattern** (store original, try/finally, restore)
3. **Test in Isolation First** (run files individually to check contamination)
4. **Common Contamination Sources**: PropertyMock on class attributes, module-level patches, shared mutable state, async event loops, Rich/logging state pollution

---

### 📦 Version Bumping - Don't Break PyPI Releases!

**⚠️ CRITICAL FOR ALL CODE CHANGES:** Always increment version numbers when making changes that will be committed and pushed. Forgetting this breaks the PyPI publishing workflow!

#### Why This Matters

The automated PyPI release pipeline checks if the version in `pyproject.toml` has been incremented. If you push code changes without bumping the version:
- ❌ PyPI publish workflow fails
- ❌ Users can't get your fixes/features via `pip install`
- ❌ Other developers get confused about which version has which features

#### What to Bump

**Backend version (REQUIRED for backend code changes):**
```toml
# pyproject.toml
[project]
version = "0.5.0b56"  # Increment this! e.g., "0.5.0b57"
```

**Frontend version (REQUIRED for dashboard/UI changes):**
```json
// src/flock/frontend/package.json
{
  "version": "0.1.2"  // Increment this! e.g., "0.1.3"
}
```

#### When to Bump

**✅ ALWAYS bump backend version for:**
- Any Python code changes in `src/flock/`
- Bug fixes, features, refactors
- Commits that modify backend behavior

Docs-only changes (in `docs/`, `README.md`) do not require a version bump.

**✅ ALWAYS bump frontend version for:**
- Dashboard UI changes
- React/TypeScript component updates
- CSS/styling changes
- Any changes in `src/flock/frontend/`

#### Versioning Pattern

We use **semantic versioning with beta tags**:
- `0.5.0b56` → `0.5.0b57` for regular changes (increment beta number)
- `0.1.2` → `0.1.3` for frontend changes (increment patch)

#### How to Bump

```bash
# 1. Make your code changes
# 2. Bump versions BEFORE committing
# Edit pyproject.toml: version = "0.5.0b57"
# Edit package.json: "version": "0.1.3"

# 3. Commit version bumps with your changes OR as separate commit
git add pyproject.toml src/flock/frontend/package.json
git commit -m "chore: bump version to 0.5.0b57"

# 4. Push (pre-commit hook will verify versions were bumped)
git push
```

#### Pre-commit Hook Protection

The repository has a pre-commit hook that **checks if versions were bumped**. If you forget, it will warn you:

```bash
check if version bump needed.............................................Failed
- hook id: version-check

❌ No version changes detected in modified Python/frontend files
```

#### Quick Checklist for PRs

Before creating a PR, verify:
- [ ] Backend version bumped in `pyproject.toml` (if any Python changes)
- [ ] Frontend version bumped in `package.json` (if any UI changes)
- [ ] Version bump committed (separate commit is fine)
- [ ] Pre-commit hooks pass
- [ ] **PR targets `0.5.0b` branch (NOT `main`!)** ⚠️

#### ⚠️ CRITICAL: PR Base Branch

**ALL pull requests MUST target the `0.5.0b` branch, NOT `main`!**

```bash
# ✅ CORRECT: PR into 0.5.0b branch
gh pr create --base 0.5.0b --title "..." --body "..."

# ❌ WRONG: PR into main branch
gh pr create --base main --title "..." --body "..."
```

**Why this matters:**
- The `0.5.0b` branch is the active development branch for the 0.5.0 beta release
- PRs into `main` bypass the beta testing process
- Features need to be validated in beta before reaching `main`

**If you accidentally create a PR against `main`:**
1. Close the incorrect PR: `gh pr close <number>`
2. Recreate against `0.5.0b`: `gh pr create --base 0.5.0b ...`

**Remember: It's better to increment versions too often than too rarely. Each meaningful change should get a version bump!**

---

## 🔍 Observability & Debugging with OpenTelemetry + DuckDB

Flock includes **production-grade distributed tracing** that captures every operation with full input/output data—enabling both human and AI-assisted debugging.

---

## 🤖 FOR AI AGENTS: Tracing is Your PRIMARY Debugging Tool

**⚠️ CRITICAL FOR AI AGENTS:** When debugging or testing Flock applications, **ALWAYS start with tracing**. The trace database contains the complete execution history with full input/output capture—this is your source of truth.

### Why Tracing First?

**Traditional debugging (logs, print statements):**
- ❌ Requires code changes
- ❌ Missing context (what happened before/after)
- ❌ No timing information
- ❌ Incomplete input/output data

**Tracing-first debugging:**
- ✅ **Zero code changes** - just query the database
- ✅ **Complete execution history** - every operation captured
- ✅ **Full I/O data** - exact inputs that caused issues
- ✅ **Timing analysis** - identify bottlenecks instantly
- ✅ **Parent-child relationships** - understand call hierarchy
- ✅ **Correlation IDs** - track requests across agents

### AI Agent Debugging Workflow (Step-by-Step)

**When a user reports an issue or asks you to debug/test:**

#### Step 1: Enable Tracing (if not already enabled)
```bash
# Check if tracing is enabled
cat .env | grep FLOCK_AUTO_TRACE

# If not enabled, add to .env:
FLOCK_AUTO_TRACE=true
FLOCK_TRACE_FILE=true

# Or export temporarily:
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
```

#### Step 2: Run the Code to Capture Trace
```bash
# Run the problematic script/test
uv run python examples/path/to/script.py

# Or run specific test
uv run pytest tests/test_file.py::test_name -v
```

#### Step 3: Query Trace Database for Overview
```python
import duckdb

conn = duckdb.connect('.flock/traces.duckdb', read_only=True)

# Get recent traces
traces = conn.execute("""
    SELECT
        trace_id,
        COUNT(*) as span_count,
        MIN(start_time) as trace_start,
        (MAX(end_time) - MIN(start_time)) / 1000000.0 as total_duration_ms,
        SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as error_count
    FROM spans
    GROUP BY trace_id
    ORDER BY trace_start DESC
    LIMIT 10
""").fetchall()

for trace in traces:
    print(f"Trace: {trace[0][:16]}... | Spans: {trace[1]} | Duration: {trace[3]:.2f}ms | Errors: {trace[4]}")
```

#### Step 4: Analyze Specific Trace
```python
# Get the most recent trace (or the one with errors)
latest_trace_id = traces[0][0]

# Get execution flow with hierarchy
flow = conn.execute("""
    SELECT
        span_id,
        parent_id,
        name,
        service,
        duration_ms,
        status_code,
        status_description,
        json_extract(attributes, '$.correlation_id') as correlation_id
    FROM spans
    WHERE trace_id = ?
    ORDER BY start_time ASC
""", [latest_trace_id]).fetchall()

# Print hierarchical execution
for span in flow:
    indent = '  ' if span[1] else ''  # Indent children
    status_icon = '✅' if span[5] == 'OK' else '❌'
    print(f"{status_icon} {indent}{span[2]} ({span[3]}) - {span[4]:.2f}ms")
    if span[6]:  # Error description
        print(f"   ERROR: {span[6]}")
```

#### Step 5: Examine Input/Output Data
```python
# Get input that caused an error
error_details = conn.execute("""
    SELECT
        name,
        status_description,
        json_extract(attributes, '$.input.artifacts') as input_artifacts,
        json_extract(attributes, '$.output.value') as output_value,
        attributes
    FROM spans
    WHERE trace_id = ?
    AND status_code = 'ERROR'
""", [latest_trace_id]).fetchall()

# Inspect the exact input that caused failure
import json
for error in error_details:
    print(f"\n❌ ERROR in {error[0]}")
    print(f"Message: {error[1]}")
    print(f"Input: {error[2]}")
    print(f"Output: {error[3]}")
```

#### Step 6: Identify Root Cause
```python
# Common root cause queries:

# 1. Find the slowest operation in the trace
slowest = conn.execute("""
    SELECT name, service, duration_ms
    FROM spans
    WHERE trace_id = ?
    ORDER BY duration_ms DESC
    LIMIT 1
""", [latest_trace_id]).fetchone()
print(f"Bottleneck: {slowest[0]} ({slowest[1]}) took {slowest[2]:.2f}ms")

# 2. Check if agent was triggered correctly
agent_triggers = conn.execute("""
    SELECT
        name,
        json_extract(attributes, '$.input.artifacts') as consumed_artifacts
    FROM spans
    WHERE trace_id = ?
    AND name LIKE 'Agent.execute'
""", [latest_trace_id]).fetchall()

# 3. Verify artifact types produced
artifacts_produced = conn.execute("""
    SELECT DISTINCT
        service as agent,
        json_extract(attributes, '$.output.type') as artifact_type
    FROM spans
    WHERE trace_id = ?
    AND attributes->>'output.type' IS NOT NULL
""", [latest_trace_id]).fetchall()
```

#### Step 7: Report Findings & Fix
```python
# Close connection
conn.close()

# Now you have:
# - Exact execution flow
# - Input data that caused the issue
# - Timing information (bottlenecks)
# - Error messages and stack traces
# - Artifact flow between agents

# Report to user with specific findings
print("""
DIAGNOSIS COMPLETE:

Issue: <describe the problem>
Root Cause: <specific operation/input that failed>
Evidence:
  - Trace ID: {trace_id}
  - Failed at: {operation_name}
  - Input: {input_data}
  - Duration: {duration}ms

Recommendation: <how to fix>
""")
```

### Essential Queries for AI Agents

**Keep these queries ready for common debugging tasks:**

#### 1. Find Most Recent Workflow Execution
```python
latest_workflow = conn.execute("""
    SELECT trace_id,
           COUNT(*) as operations,
           (MAX(end_time) - MIN(start_time)) / 1000000.0 as duration_ms
    FROM spans
    GROUP BY trace_id
    ORDER BY MIN(start_time) DESC
    LIMIT 1
""").fetchone()
```

#### 2. Check Agent Lifecycle Execution
```python
# Verify all lifecycle hooks fired correctly
lifecycle = conn.execute("""
    SELECT name, duration_ms, status_code
    FROM spans
    WHERE trace_id = ?
    AND service LIKE '%Component'
    OR service LIKE '%Engine'
    ORDER BY start_time ASC
""", [trace_id]).fetchall()

# Expected order: on_initialize → on_pre_consume → on_pre_evaluate →
#                 evaluate → on_post_evaluate → on_post_publish → on_terminate
```

#### 3. Validate Artifact Flow
```python
# Track artifact transformations
artifact_flow = conn.execute("""
    SELECT
        name,
        service,
        json_extract(attributes, '$.input.artifacts[0].type') as input_type,
        json_extract(attributes, '$.output.type') as output_type
    FROM spans
    WHERE trace_id = ?
    AND (attributes->>'input.artifacts' IS NOT NULL
         OR attributes->>'output.type' IS NOT NULL)
    ORDER BY start_time ASC
""", [trace_id]).fetchall()

# Verify expected transformations: InputType → Agent → OutputType
```

#### 4. Detect Performance Issues
```python
# Find operations that took >1 second
slow_ops = conn.execute("""
    SELECT
        name,
        service,
        duration_ms,
        json_extract(attributes, '$.input.artifacts[0].payload') as input_payload
    FROM spans
    WHERE trace_id = ?
    AND duration_ms > 1000
    ORDER BY duration_ms DESC
""", [trace_id]).fetchall()

# Check if large payloads are causing slowness
for op in slow_ops:
    if op[3]:
        payload_size = len(str(op[3]))
        print(f"{op[0]}: {op[2]:.0f}ms (payload: {payload_size} bytes)")
```

#### 5. Debug Test Failures
```python
# When a test fails, find what actually happened vs expected
test_execution = conn.execute("""
    SELECT
        name,
        status_code,
        status_description,
        json_extract(attributes, '$.input.artifacts') as input,
        json_extract(attributes, '$.output.value') as output
    FROM spans
    WHERE trace_id = ?
    ORDER BY start_time ASC
""", [trace_id]).fetchall()

# Compare actual output with test expectations
```

### Common Debugging Scenarios for AI Agents

#### Scenario A: "Test is failing but I don't know why"
```bash
# Step 1: Run test with tracing
FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true uv run pytest tests/test_file.py::test_name -v

# Step 2: Query for test execution
uv run python -c "
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)

# Find most recent trace
trace = conn.execute('''
    SELECT trace_id FROM spans
    GROUP BY trace_id
    ORDER BY MIN(start_time) DESC LIMIT 1
''').fetchone()[0]

# Get all operations
ops = conn.execute('''
    SELECT name, status_code, duration_ms
    FROM spans WHERE trace_id = ?
    ORDER BY start_time
''', [trace]).fetchall()

for op in ops:
    status = '✅' if op[1] == 'OK' else '❌'
    print(f'{status} {op[0]}: {op[2]:.2f}ms')
"
```

#### Scenario B: "Agent not producing expected output"
```python
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)

# Find what the agent actually produced
trace_id = '<latest_trace_id>'
output = conn.execute("""
    SELECT
        service as agent_name,
        json_extract(attributes, '$.output.type') as output_type,
        json_extract(attributes, '$.output.value') as output_value
    FROM spans
    WHERE trace_id = ?
    AND name = 'Agent.execute'
""", [trace_id]).fetchone()

print(f"Agent: {output[0]}")
print(f"Output Type: {output[1]}")
print(f"Output Value: {output[2]}")

# Compare with expected output type in test
```

#### Scenario C: "Agent not being triggered"
```python
# Check if artifact was published and if agent subscribed
trace_id = '<latest_trace_id>'

published = conn.execute("""
    SELECT json_extract(attributes, '$.output.type') as artifact_type
    FROM spans
    WHERE trace_id = ?
    AND name = 'Flock.publish'
""", [trace_id]).fetchone()

print(f"Published artifact type: {published[0]}")

# Check if any agent consumed it
consumers = conn.execute("""
    SELECT service, json_extract(attributes, '$.input.artifacts[0].type') as consumed_type
    FROM spans
    WHERE trace_id = ?
    AND name = 'Agent.execute'
""", [trace_id]).fetchall()

if not consumers:
    print("❌ No agents consumed this artifact!")
    print("Check agent subscription rules (consumes clause)")
else:
    for consumer in consumers:
        print(f"✅ {consumer[0]} consumed {consumer[1]}")
```

#### Scenario D: "Performance regression"
```python
# Compare execution times across traces
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)

# Get last 10 executions of same operation
perf_history = conn.execute("""
    SELECT
        trace_id,
        start_time,
        duration_ms
    FROM spans
    WHERE name = 'DSPyEngine.evaluate'  -- or any operation
    ORDER BY start_time DESC
    LIMIT 10
""").fetchall()

# Calculate average and detect outliers
durations = [p[2] for p in perf_history]
avg = sum(durations) / len(durations)
latest = durations[0]

print(f"Latest: {latest:.2f}ms")
print(f"Average: {avg:.2f}ms")
print(f"Change: {((latest / avg - 1) * 100):+.1f}%")

if latest > avg * 1.5:
    print("⚠️ Performance regression detected!")
```

### Best Practices for AI Agents

**✅ DO:**
- **Always enable tracing** before running code to debug
- **Start with overview queries** (get all traces, find latest)
- **Work from general to specific** (trace → spans → attributes → I/O)
- **Use read-only connections** (`read_only=True`)
- **Close connections** when done
- **Clear old traces** periodically: `Flock.clear_traces()`
- **Use correlation IDs** to track related operations

**❌ DON'T:**
- Don't modify code just to add logging - query traces instead
- Don't guess at execution flow - trace database has the truth
- Don't skip trace analysis for "obvious" bugs - verify with data
- Don't forget to check `status_description` for error details
- Don't ignore timing data - it reveals bottlenecks

### Tracing-First Testing Workflow

When writing or debugging tests:

1. **Run test with tracing enabled**
   ```bash
   FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true uv run pytest tests/test_file.py -v
   ```

2. **Query trace to see what actually happened**
   ```python
   # Get test execution trace
   trace_id = conn.execute("SELECT trace_id FROM spans GROUP BY trace_id ORDER BY MIN(start_time) DESC LIMIT 1").fetchone()[0]
   ```

3. **Verify assertions match reality**
   ```python
   # What did the agent actually produce?
   actual = conn.execute("SELECT json_extract(attributes, '$.output.value') FROM spans WHERE trace_id = ? AND name = 'Agent.execute'", [trace_id]).fetchone()

   # Does it match test expectations?
   expected = "BugDiagnosis artifact with severity='Critical'"
   ```

4. **Debug failures with exact I/O data**
   ```python
   # Get the exact input that caused test failure
   failure_input = conn.execute("""
       SELECT json_extract(attributes, '$.input.artifacts')
       FROM spans WHERE trace_id = ? AND status_code = 'ERROR'
   """, [trace_id]).fetchone()
   ```

### Quick Start: Enable Tracing

```bash
# Enable auto-tracing (add to .env or export)
FLOCK_AUTO_TRACE=true      # Enable tracing for all operations
FLOCK_TRACE_FILE=true      # Store traces in DuckDB

# Run your application
python examples/showcase/01_declarative_pizza.py

# Traces stored in: .flock/traces.duckdb
```

### 🆕 Unified Tracing with traced_run()

**New in v0.5.0**: Wrap entire workflows in a single parent trace for better observability!

```python
# ✅ Unified trace
async with flock.traced_run("pizza_workflow"):
    await flock.publish(pizza_idea)
    await flock.run_until_idle()
```

**Result**: Single trace with proper hierarchy

### 🗑️ Clearing Traces

Clear trace database for fresh debug sessions:

```python
# Clear all traces
result = Flock.clear_traces()
print(f"Deleted {result['deleted_count']} spans")
```

📖 **Full tracing documentation**: [docs/UNIFIED_TRACING.md](docs/UNIFIED_TRACING.md)

---

## ❓ FAQ for AI Agents

### Q: How do I debug or test Flock code?

**⚠️ ALWAYS START WITH TRACING!**

Quick debugging workflow:
```bash
# 1. Enable tracing
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true

# 2. Run the code
uv run python examples/path/to/script.py

# 3. Query trace database
uv run python -c "
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)

# Get latest trace
trace = conn.execute('''
    SELECT trace_id, COUNT(*) as spans,
           (MAX(end_time)-MIN(start_time))/1000000.0 as duration_ms
    FROM spans GROUP BY trace_id
    ORDER BY MIN(start_time) DESC LIMIT 1
''').fetchone()

print(f'Trace: {trace[0][:32]}...')
print(f'Spans: {trace[1]}, Duration: {trace[2]:.2f}ms')

# Get execution flow
flow = conn.execute('''
    SELECT name, duration_ms, status_code
    FROM spans WHERE trace_id = ?
    ORDER BY start_time
''', [trace[0]]).fetchall()

for op in flow:
    status = '✅' if op[2] == 'OK' else '❌'
    print(f'{status} {op[0]}: {op[1]:.2f}ms')
"
```

📖 **Complete guide:** [🤖 FOR AI AGENTS: Tracing is Your PRIMARY Debugging Tool](#-for-ai-agents-tracing-is-your-primary-debugging-tool) (scroll up in this file)

### Q: Where should I save new files?

**⚠️ CRITICAL: NEVER save files to the project root directory!**

Always use the appropriate subdirectory:
- **Tests**: `/tests` - All test files only
- **Source Code**: `/src/flock` - Production code only
- **Documentation**: `/docs` - Documentation only
- **Examples**: `/examples` - Example scripts only
- **Frontend**: `src/flock/frontend/src` - React components and frontend code

**Never create files in the root directory** - it should only contain configuration files like `pyproject.toml`, `README.md`, etc.

### Q: How do I add a new dependency?

```bash
# Python
uv add package-name

# Frontend
cd frontend && npm install package-name
```

📖 **Full guide:** [Dependencies Guide](docs/ai-agents/dependencies.md)

### Q: How do I run a specific test?

```bash
# Backend
uv run pytest tests/test_file.py::test_name -v

# Frontend
cd frontend && npm test -- test_name
```

### Q: How do I start the dashboard?

```python
await orchestrator.serve(dashboard=True)
```

📖 **Full guide:** [Frontend Guide](docs/ai-agents/frontend.md)

### Q: How do I test UI features and debug dashboard issues?

**Use playwright-mcp with dashboard examples for comprehensive manual UI testing.**

#### Step-by-Step Testing Workflow

**1. Start the Dashboard Example**
```bash
# Run in background to keep testing
uv run python examples/03-the-dashboard/01_declarative_pizza.py
```

Wait for these success indicators in the output:
- `[Dashboard] Production build completed`
- `INFO: Uvicorn running on http://127.0.0.1:8344`
- `[Dashboard] Browser launched successfully`

**2. Navigate and Verify Initial Load**
```python
# Use playwright-mcp tools
mcp__playwright__browser_navigate(url="http://localhost:8344")
```

**✅ What to verify:**
- Page title: "🦆🐓 Flock 🐤🐧"
- WebSocket status (top right): **"Connected"** (green)
- Two view buttons: "Agent View" (active) and "Blackboard View"
- Control buttons: Publish, Agent Details, Filters, Settings

**3. Test Agent View**

Take a snapshot to see the agent graph:
```python
mcp__playwright__browser_snapshot()
```

**✅ What to verify in Agent View:**
- Agent nodes displayed (e.g., `pizza_master`)
- Each node shows:
  - Agent name and status (should be "idle" initially)
  - Input types with count (e.g., ↓ 0 __main__.MyDreamPizza)
  - Output types with count (e.g., ↑ 0 __main__.Pizza)
- React Flow controls (zoom in/out, fit view, mini-map)

**4. Open Agent Details Panel**
```python
# Click the Agent Details button
mcp__playwright__browser_click(element="Agent Details button", ref="<ref>")
```

**✅ What to verify:**
- Panel opens showing agent name
- Three tabs: "Live Output", "Message History", "Run Status"
- Shows "Idle - no output" initially

**5. Test Publishing an Artifact**

```python
# Step 1: Select artifact type
mcp__playwright__browser_select_option(
    element="Artifact Type dropdown",
    ref="<ref>",
    values=["__main__.MyDreamPizza"]
)
```

**✅ What to verify after selecting type:**
- Form dynamically generates input fields based on artifact schema
- For MyDreamPizza: Should show "Pizza Idea" textbox

```python
# Step 2: Fill in the input
mcp__playwright__browser_type(
    element="Pizza Idea textbox",
    ref="<ref>",
    text="a spicy Hawaiian pizza with jalapeños and pineapple"
)

# Step 3: Publish
mcp__playwright__browser_click(
    element="Publish Artifact button",
    ref="<ref>"
)
```

**✅ What to verify after publishing:**
- Agent status changes: "idle" → "running" → "idle"
- Input count increases: ↓ 0 → ↓ 1
- Output count increases: ↑ 0 → ↑ 1
- **External node appears** on the graph (shows who published the artifact)
- Edge connects external → pizza_master

**6. Monitor Live Execution**

**✅ What to verify in Agent Details panel:**
- Event counter increases (e.g., "316 events")
- Live streaming output appears token-by-token
- Console shows WebSocket messages: `[WebSocket] Streaming output: {...}`
- Final output shows complete structured data
- "--- End of output ---" marker when complete

**7. Test Blackboard View**
```python
# Switch to Blackboard View
mcp__playwright__browser_click(
    element="Blackboard View button",
    ref="<ref>"
)
```

**✅ What to verify in Blackboard View:**
- **Input artifact node** showing:
  - Type: `__main__.MyDreamPizza`
  - Producer: "by: external"
  - Timestamp
  - Full JSON payload (expandable)
- **Output artifact node** showing:
  - Type: `__main__.Pizza`
  - Producer: "by: pizza_master"
  - Timestamp
  - Complete structured data with all fields
- **Edge** connecting input → output artifacts
- Data is fully browsable (can expand/collapse nested objects)

**8. Take Screenshots for Verification**
```python
# Capture key states for visual verification
mcp__playwright__browser_take_screenshot(filename="dashboard-test.png")
```

#### Common Issues and Troubleshooting

**Issue: Dashboard doesn't load**
- Check: Backend server started? Look for "Uvicorn running" message
- Check: Frontend build completed? Look for "Production build completed"
- Solution: Wait 5-10 seconds after starting for build to complete

**Issue: WebSocket shows "Disconnected"**
- Check: Console for WebSocket errors
- Check: Server logs for WebSocket connection messages
- Solution: Refresh page, verify server is running

**Issue: No live output during agent execution**
- Check: Agent Details panel is open
- Check: "Live Output" tab is active
- Check: Console shows `[WebSocket] Streaming output` messages
- Solution: Verify WebSocket connection status

**Issue: Artifacts not appearing in Blackboard View**
- Check: Did agent execution complete? (status back to "idle")
- Check: Output count increased? (↑ 1)
- Solution: Switch back to Agent View to verify execution, then return to Blackboard View

#### Why Manual Testing with Playwright-MCP?

- ✅ **Live testing** - Real dashboard with actual agents executing
- ✅ **Visual verification** - See exactly what users see
- ✅ **WebSocket testing** - Verify real-time streaming works correctly
- ✅ **Full workflow** - Test complete user journey from publish → execute → view results
- ✅ **Screenshot capture** - Document UI state for debugging/documentation
- ✅ **Interactive debugging** - Click, type, inspect like a real user

📖 **Dashboard examples:** [`examples/02-dashboard/`](examples/02-dashboard/)

---

#### Advanced Dashboard Testing: Multi-Agent Cascades & Conditional Consumption

**Test with:** `examples/03-the-dashboard/02-dashboard-edge-cases.py`

This example demonstrates advanced features not visible in simple single-agent workflows.

**1. Use Auto Layout for Complex Graphs**

When testing with 3+ agents, use the context menu to organize the graph:

```python
# After navigating to dashboard
# Right-click on the canvas (not on a node)
mcp__playwright__browser_click(element="Canvas area", ref="<ref>", button="right")

# Click Auto Layout from context menu
mcp__playwright__browser_click(element="Auto Layout button", ref="<ref>")
```

**✅ What to verify:**
- Agents arranged in clean vertical or horizontal hierarchy
- No overlapping nodes
- Edges clearly visible between agents

**2. Test Conditional Consumption (Lambda Filters)**

This example has agents with `where` clauses that filter which artifacts they consume:

```python
# In the code:
chapter_agent.consumes(Review, where=lambda r: r.score >= 9)  # Only high scores
book_idea_agent.consumes(Review, where=lambda r: r.score <= 8)  # Only low scores (feedback loop)
```

**✅ What to verify after publishing Idea:**
- **Edge labels show filtered counts**: e.g., `__main__.Review(1)` means "1 Review consumed out of 3 total"
- **Input counts reflect actual consumption**: chapter_agent shows ↓ 1 Review (not ↓ 3)
- **Feedback loops work**: book_idea_agent consumes both Idea AND Review artifacts

**3. Monitor Multi-Agent Cascade Execution**

Expected workflow for edge cases example:
```
1. Publish Idea artifact
2. book_idea_agent: ↓ 1 Idea → ↑ 3 BookHook (produces multiple outputs!)
3. reviewer_agent: ↓ 3 BookHook → ↑ 3 Review (processes each hook)
4. chapter_agent: ↓ 1 Review → ↑ 1 BookOutline (filtered: only score >= 9)
5. book_idea_agent: ↓ 2 Review → ↑ 0 BookHook (feedback loop for low scores)
```

**✅ What to verify during cascade:**
- Agent statuses transition: idle → running → idle
- Counters update in real-time as each agent completes
- External node persists showing initial publisher
- Edges appear/update showing data flow

**4. Handle Large Artifact Counts**

**⚠️ IMPORTANT**: When page has 8+ artifacts, `browser_snapshot()` exceeds 25K token limit and fails.

**Solution**: Use `browser_take_screenshot()` for visual verification instead:

```python
# ❌ This will fail with many artifacts
mcp__playwright__browser_snapshot()

# ✅ Use screenshots instead
mcp__playwright__browser_take_screenshot(filename="cascade-state.png")
```

**5. Verify Final State in Blackboard View**

```python
# Switch to Blackboard View
mcp__playwright__browser_click(element="Blackboard View button", ref="<ref>")

# Take screenshot (snapshot will fail with many artifacts)
mcp__playwright__browser_take_screenshot(filename="blackboard-artifacts.png")
```

**✅ What to verify:**
- All produced artifacts visible as nodes
- **1 Idea** → **3 BookHooks** → **3 Reviews** → **1 BookOutline**
- Edges show complete transformation chain
- Final artifact (BookOutline) contains expected structured data
- Timestamps show execution order

#### Expected Execution Time

**Simple example (01_declarative_pizza.py)**: ~5 seconds (1 agent, 1 artifact)
**Edge cases (02-dashboard-edge-cases.py)**: ~60 seconds (3 agents, 8 artifacts, feedback loop)

Plan your testing time accordingly!

#### Key Dashboard Features Learned

**Auto Layout** ⭐
- Access via right-click context menu
- Automatically organizes complex agent graphs
- Essential for 3+ agent workflows

**Filtered Edge Labels** ⭐
- Shows actual consumed count vs total available
- Format: `ArtifactType(consumed_count)`
- Makes conditional consumption transparent

**Feedback Loops** ⭐
- Agents can consume multiple artifact types
- Low-scoring Reviews loop back to book_idea_agent
- Counts accumulate correctly across iterations

**Real-time Updates** ⭐
- Status changes: idle → running → idle
- Counters increment as artifacts produced/consumed
- WebSocket delivers updates without page refresh

📖 **Dashboard examples:** [`examples/02-dashboard/`](examples/02-dashboard/)

---

### Q: How do I use unified tracing?

```python
# Wrap workflows in a single trace
async with flock.traced_run("workflow_name"):
    await flock.publish(data)
    await flock.run_until_idle()

# Clear traces for fresh debug session
result = Flock.clear_traces()
```

📖 **Full guide:** [docs/UNIFIED_TRACING.md](docs/UNIFIED_TRACING.md)

### Q: Where should I add new tests?

Add to existing test file if relevant, or create new file following naming convention `test_<module>.py` for backend, `<name>.test.tsx` for frontend.

### Q: What Python version features can I use?

Python 3.10+, so you can use:
- `match`/`case` statements
- `TaskGroup` for parallel execution
- Improved type hints (`list[str]` not `List[str]`)

### Q: How do I debug WebSocket issues?

Check browser console for WebSocket logs, use Network tab to inspect connection, and verify backend WebSocket server is running on correct port.

---

## 🎯 Quick Reference

### Essential Commands

```bash
# Setup
poe install          # Install all dependencies

# Development
poe build           # Build project
poe lint            # Lint code
poe format          # Format code

# Testing
poe test            # Run tests
poe test-cov        # Run with coverage
poe test-critical   # Run critical path tests

# Frontend
cd frontend
npm run dev         # Start dev server
npm test            # Run frontend tests
npm run build       # Build for production

# UI Testing (with playwright-mcp)
uv run python examples/03-the-dashboard/01_declarative_pizza.py  # Start dashboard
# Then use playwright-mcp to interact with UI for manual testing
```

### Code Snippets

**Create orchestrator:**
```python
from flock.orchestrator import Flock
orchestrator = Flock("openai/gpt-4o")
```

**Define agent:**
```python
agent = (
    orchestrator.agent("name")
    .description("What it does")
    .consumes(InputType)
    .publishes(OutputType)
)
```

**Run agent:**
```python
await orchestrator.arun(agent, input_data)
```

**Unified tracing:**
```python
# Wrap workflow in single trace
async with flock.traced_run("workflow_name"):
    await flock.publish(data)
    await flock.run_until_idle()

# Clear traces
Flock.clear_traces()
```

**Start dashboard:**
```python
await orchestrator.serve(dashboard=True)
```

---

## 📞 Getting Help

### Documentation

**AI Agent Guides (this repo):**
- **[Architecture Guide](docs/ai-agents/architecture.md)** - Core architecture, project structure, code style
- **[Development Workflow](docs/ai-agents/development.md)** - Testing, quality standards, versioning
- **[Frontend Guide](docs/ai-agents/frontend.md)** - Dashboard usage, frontend development
- **[Dependencies Guide](docs/ai-agents/dependencies.md)** - Package management, UV commands
- **[Common Tasks](docs/ai-agents/common-tasks.md)** - Adding agents/components, performance

**Additional Documentation:**
- **Contributing Guide:** [`CONTRIBUTING.md`](CONTRIBUTING.md) - Complete contribution workflow
- **Versioning Guide:** [`docs/VERSIONING.md`](docs/VERSIONING.md) - Smart version bumping
- **Pre-commit Hooks:** [`docs/PRE_COMMIT_HOOKS.md`](docs/PRE_COMMIT_HOOKS.md) - Quality automation
- **Unified Tracing:** [`docs/UNIFIED_TRACING.md`](docs/UNIFIED_TRACING.md) - Workflow tracing & trace management
- **Examples:** [`examples/`](examples/) - Working code examples
- **Analysis Documents:** [`docs/patterns/`](docs/patterns/)

---

**Welcome to the team! Let's build the future of AI agent orchestration together.** 🚀

---

*Last updated: October 13, 2025*
*This file follows the modern AGENTS.md format for AI coding agents.*
