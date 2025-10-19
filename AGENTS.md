# AGENTS.md

**Welcome, AI coding agent!** 👋

This is Flock, a production-grade blackboard-first AI agent orchestration framework. This guide gets you up to speed quickly on the current project state and development patterns.

**Current Version:** Backend: 0.5.0b63 • Frontend: 0.1.4
**Architecture:** Hybrid Python/TypeScript with real-time dashboard
**Package Manager:** UV (NOT pip!)
**Status:** Production-ready with comprehensive monitoring

---

## 🎯 Project Snapshot

### What Is Flock?

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
- **Subscriptions:** Declarative rules for when agents react (type matching, predicates, semantic matching)
- **Visibility:** Built-in access control (Public/Private/Tenant/Label-based/Time-based)
- **Fan-Out Publishing:** Produce multiple artifacts from single agent execution with filtering/validation
- **Semantic Matching:** AI-powered artifact routing based on meaning, not just keywords
- **Components:** Three levels of extensibility:
  - **Orchestrator Components:** Global lifecycle hooks (monitoring, metrics, coordination)
  - **Agent Components:** Per-agent behavior (quality gates, retry logic, validation)
  - **Engines:** Custom processing logic (DSPy, regex, deterministic rules)
- **Real-time Dashboard:** React/TypeScript interface for live monitoring

---

## 🚀 Quick Setup

### Prerequisites

- **Python 3.12+** (we use modern async features)
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

# Engine + component playgrounds
uv run python examples/05-engines/emoji_mood_engine.py
uv run python examples/05-engines/potion_batch_engine.py
uv run python examples/06-agent-components/plot_twist_component.py
uv run python examples/06-agent-components/cheer_meter_component.py
uv run python examples/07-orchestrator-components/quest_tracker_component.py
uv run python examples/07-orchestrator-components/kitchen_monitor_component.py
```

---

## 📚 Detailed Guides

For deep dives into specific topics, see:

**Core Architecture:**
- **[Architecture Overview](docs/architecture.md)** - Complete system design, module organization, and Phase 1-7 refactoring ⭐ **UPDATED**
- **[Architecture & Blackboard](docs/guides/blackboard.md)** - Core pattern, structure, and behavior
- **[Agent Guide](docs/guides/agents.md)** - Complete agent development reference
- **[Context Providers](docs/guides/context-providers.md)** - Smart filtering & security boundaries for agent context ⭐ **NEW in 0.5**

**Code Patterns & Standards:**
- **[Error Handling Patterns](docs/patterns/error_handling.md)** - Production-ready error handling guide ⭐ **NEW**
- **[Async Patterns](docs/patterns/async_patterns.md)** - Async/await best practices and common pitfalls ⭐ **NEW**

**Components & Extensibility:**
- **[Agent Components](docs/guides/components.md)** - Extend agent behavior with lifecycle hooks
- **[Orchestrator Components](docs/guides/orchestrator-components.md)** - Extend orchestrator behavior with lifecycle hooks (NEW!)

**Logic Operations (Advanced Subscriptions):**
- **[Predicates](docs/guides/predicates.md)** - Conditional consumption with `where=` filters
- **[Join Operations](docs/guides/join-operations.md)** - Correlate related artifacts with JoinSpec
- **[Batch Processing](docs/guides/batch-processing.md)** - Efficient bulk operations with BatchSpec
- **[Semantic Subscriptions](docs/guides/semantic-subscriptions.md)** - AI-powered artifact matching by meaning ⭐ **NEW in 0.5.2**
- **[Semantic Routing Tutorial](docs/tutorials/semantic-routing.md)** - Step-by-step guide to intelligent ticket routing ⭐ **NEW in 0.5.2**

**Publishing Patterns:**
- **[Fan-Out Publishing](docs/guides/fan-out.md)** - Generate multiple outputs with filtering/validation ⭐ **NEW in 0.5**

**Development & Operations:**
- **[Development Workflow](docs/guides/testing.md)** - Testing, quality, versioning, pre-commit
- **[Frontend/Dashboard](docs/guides/dashboard.md)** - Dashboard usage and development
- **[Configuration & Dependencies](CONTRIBUTING.md)** - Environment and setup
- **[Patterns & Common Tasks](docs/guides/patterns.md)** - Recipes, performance, security
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

### 🔐 Context Providers - Smart Filtering & Security Boundaries

**Context Providers are the intelligent filter layer between agents and the blackboard—controlling what each agent sees, reducing token costs by 90%+, and automatically redacting sensitive data.**

**⚠️ IMPORTANT FOR AI AGENTS:** Context Providers implement the security architecture described in [docs/architecture.md](docs/architecture.md) and follow error handling patterns from [docs/patterns/error_handling.md](docs/patterns/error_handling.md). Read these documents to understand the design principles.

#### Why Context Providers Matter

**The Problem:**
- Agents seeing ALL artifacts wastes tokens (costs)
- No way to filter sensitive data before agents see it
- Performance degrades as blackboard grows
- Security vulnerabilities if agents bypass visibility

**The Solution:**
Context Providers enforce a security boundary that:
- ✅ **Reduces token costs** - Agents see only relevant artifacts (90%+ savings)
- ✅ **Protects sensitive data** - Auto-redact passwords, API keys, credit cards
- ✅ **Improves performance** - Less context = faster agent execution
- ✅ **Enforces security** - Agents cannot bypass provider filtering (architecturally impossible!)

**Understanding the Three-Layer Model:**

Flock uses three complementary filtering layers:

1. **Visibility** (security boundary) - Controls BOTH which agents trigger AND which artifacts they see in context
2. **Subscription Filters** (routing logic) - Controls WHEN agents trigger (e.g., `.consumes(Task, tags={"urgent"})`)
3. **Context Providers** (context shaping) - Controls WHAT agents see in their historical context

These layers work together to provide fine-grained control over agent execution and data access. Context Providers are the third layer—they filter what agents see in context but do NOT control triggering.

#### Quick Start: Global Filtering

**Filter all agents to see only urgent items:**

```python
from flock import Flock
from flock.context_provider import FilteredContextProvider
from flock.store import FilterConfig

# Create provider that filters by tags
urgent_only = FilteredContextProvider(
    FilterConfig(tags={"urgent", "high"}),
    limit=50  # Max 50 artifacts
)

# Apply to ALL agents
flock = Flock("openai/gpt-4.1", context_provider=urgent_only)

# Publish with tags
await flock.publish(Task(...), tags={"urgent"})  # ✅ Agents see this
await flock.publish(Task(...), tags={"low"})     # ❌ Agents don't see this
```

#### Per-Agent Filtering (Role-Based)

**Different agents see different context:**

```python
# Global: Errors only
error_provider = FilteredContextProvider(FilterConfig(tags={"ERROR"}))
flock = Flock("openai/gpt-4.1", context_provider=error_provider)

# Junior engineer: Errors only (uses global)
junior = flock.agent("junior").consumes(LogEntry).publishes(Report).agent

# Senior engineer: Errors + Warnings (override global)
warn_provider = FilteredContextProvider(FilterConfig(tags={"ERROR", "WARN"}))
senior = flock.agent("senior").consumes(LogEntry).publishes(Analysis).agent
senior.context_provider = warn_provider  # 🎯 Per-agent override!

# Platform team: Everything (override global)
all_provider = FilteredContextProvider(FilterConfig(tags={"DEBUG", "INFO", "WARN", "ERROR"}))
platform = flock.agent("platform").consumes(LogEntry).publishes(Report).agent
platform.context_provider = all_provider
```

**Provider Priority:**
```
Per-Agent Provider  >  Global Provider  >  DefaultContextProvider
     (highest)            (medium)              (fallback)
```

#### Production-Ready: Password Redaction

**Automatically redact sensitive data from agent context:**

```python
from examples.context_provider import PasswordRedactorProvider

# Create provider with built-in patterns
provider = PasswordRedactorProvider(
    redaction_text="[REDACTED]",
    redact_emails=True,
    log_redactions=True  # Audit trail
)

flock = Flock("openai/gpt-4.1", context_provider=provider)

# Publish data with secrets
await flock.publish(UserData(
    password="MySecret123",           # → [REDACTED]
    api_key="sk-1234567890abcdef",    # → [REDACTED]
    email="user@example.com"          # → [REDACTED]
))

# Agents see redacted version automatically!
```

**What gets redacted:**
- 🔒 Passwords and secrets
- 🔑 API keys (OpenAI, AWS, GitHub, GitLab, Stripe, Google)
- 🎫 Bearer tokens and JWT
- 💳 Credit card numbers (Visa, MC, Amex, Discover)
- 🆔 Social Security Numbers
- 🔐 Private keys (RSA, EC, OpenSSH)
- 📧 Email addresses (optional)

#### FilterConfig API Reference

**Declarative filtering with multiple criteria:**

```python
from flock.store import FilterConfig

# Combine multiple filters (AND logic)
config = FilterConfig(
    tags={"ERROR", "CRITICAL"},           # OR logic: any of these tags
    type_names={"SystemEvent", "Alert"},  # OR logic: any of these types
    produced_by=["monitor", "watchdog"],  # OR logic: from any of these agents
    correlation_id="incident-123"         # Exact match
)

provider = FilteredContextProvider(config, limit=100)
```

**Criteria are combined with AND logic:**
- Must have (ERROR OR CRITICAL) tag
- AND must be (SystemEvent OR Alert) type
- AND must be from (monitor OR watchdog) agent
- AND must have correlation_id "incident-123"

#### Custom Context Providers

**Build your own filtering logic:**

```python
from flock.context_provider import BaseContextProvider, ContextRequest
from flock.artifacts import Artifact

class TimeBoundProvider(BaseContextProvider):
    """Only show artifacts from last 1 hour.

    Security is enforced automatically by BaseContextProvider!
    """

    async def get_artifacts(self, request: ContextRequest) -> list[Artifact]:
        cutoff = datetime.now() - timedelta(hours=1)

        # Query all artifacts
        artifacts, _ = await request.store.query_artifacts(limit=1000)

        # Apply time-based filtering
        recent = [a for a in artifacts if a.created_at >= cutoff]

        return recent

        # ✨ BaseContextProvider automatically:
        # - Filters by visibility (MANDATORY, cannot bypass!)
        # - Excludes requested IDs
        # - Serializes to standard format

# Usage
provider = TimeBoundProvider()
flock = Flock("openai/gpt-4.1", context_provider=provider)
```

**Why this is better:**
- ✅ **75% less code** - 5 lines vs 20+ lines
- ✅ **Impossible to bypass security** - visibility enforced by base class
- ✅ **Consistent serialization** - automatic standard format
- ✅ **Focus on business logic** - not infrastructure

#### Real-World Use Cases

**Healthcare (HIPAA Compliance):**
```python
# Redact PHI (Protected Health Information)
from examples.context_provider import PasswordRedactorProvider

phi_provider = PasswordRedactorProvider(
    custom_patterns={
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "mrn": r"MRN[:\s]*\d{6,10}",
        "dob": r"\b\d{2}/\d{2}/\d{4}\b",
    }
)

flock = Flock("openai/gpt-4.1", context_provider=phi_provider)
```

**DevOps (Log Filtering):**
```python
# Error engineers see only errors
error_provider = FilteredContextProvider(FilterConfig(tags={"ERROR", "CRITICAL"}))
error_agent.context_provider = error_provider

# Platform team sees everything
all_provider = FilteredContextProvider(FilterConfig(tags={"DEBUG", "INFO", "WARN", "ERROR"}))
platform_agent.context_provider = all_provider
```

**Multi-Tenant SaaS (Customer Isolation):**
```python
# Each tenant gets isolated context
tenant_a_provider = FilteredContextProvider(FilterConfig(correlation_id=f"tenant_{customer_a.id}"))
tenant_a_agent.context_provider = tenant_a_provider

tenant_b_provider = FilteredContextProvider(FilterConfig(correlation_id=f"tenant_{customer_b.id}"))
tenant_b_agent.context_provider = tenant_b_provider
```

#### Performance Impact

**Token Cost Reduction:**

```python
# ❌ Before (no filtering): Agent sees 1000 artifacts = 200,000 tokens
# Cost: $0.006 per agent call

# ✅ After (smart filtering): Agent sees 10 relevant artifacts = 2,000 tokens
# Cost: $0.00006 per agent call

# 💰 99% cost reduction!

provider = FilteredContextProvider(FilterConfig(tags={"urgent"}), limit=10)
```

#### Security Best Practices

**✅ DO:**
- Always enforce visibility (NEVER skip)
- Use `FilteredContextProvider` for common patterns
- Test redaction patterns with real data
- Log security events for audit trails
- Limit by default (start restrictive)

**❌ DON'T:**
- Don't skip visibility filtering (security boundary!)
- Don't leak sensitive data in nested objects
- Don't cache redacted data without re-applying redaction
- Don't trust agent input (agents are untrusted)
- Don't expose infrastructure details

#### Learn More

**📚 Complete Guide:** [docs/guides/context-providers.md](docs/guides/context-providers.md) - Architecture, security model, advanced patterns

**💡 Examples:** [examples/08-context-provider/](examples/08-context-provider/) - 5 progressive examples from beginner to expert

**🎁 Production Code:** [examples/08-context-provider/05_password_redactor.py](examples/08-context-provider/05_password_redactor.py) - Copy-paste ready password filtering

#### Quick Reference

```python
# Global filtering
flock = Flock("openai/gpt-4.1", context_provider=FilteredContextProvider(FilterConfig(tags={"urgent"})))

# Per-agent override
agent.context_provider = FilteredContextProvider(FilterConfig(tags={"ERROR", "WARN"}))

# Password redaction
from examples.context_provider import PasswordRedactorProvider
flock = Flock("openai/gpt-4.1", context_provider=PasswordRedactorProvider())

# Custom provider
class MyProvider(ContextProvider):
    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # Query + filter by visibility (MANDATORY) + your logic
        pass
```

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
- [ ] **PR targets `main` branch** ✅

#### ⚠️ CRITICAL: PR Base Branch

**ALL pull requests MUST target the `main` branch!**

```bash
# ✅ CORRECT: PR into main branch
gh pr create --base main --title "..." --body "..."

# ❌ WRONG: PR into other branches without discussion
gh pr create --base some-other-branch --title "..." --body "..."
```

**Why this matters:**
- The `main` branch is the active development branch
- All features should be validated through PR review before merging
- Keeps the project history clean and linear

**If you accidentally create a PR against the wrong branch:**
1. Close the incorrect PR: `gh pr close <number>`
2. Recreate against `main`: `gh pr create --base main ...`

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
- **Source Code**: `/src/flock` - Production code following refactored module structure:
  - `/src/flock/core/` - Core orchestration and agents (Phase 2)
  - `/src/flock/orchestrator/` - Orchestrator modules (Phase 3 + 5A)
  - `/src/flock/agent/` - Agent modules (Phase 4)
  - `/src/flock/components/` - Component library
  - `/src/flock/engines/` - Engine implementations
  - `/src/flock/utils/` - Utility modules (Phase 1)
- **Documentation**: `/docs` - Documentation only
  - `/docs/patterns/` - Code patterns and best practices
  - `/docs/guides/` - User guides and tutorials
  - `/docs/refactor/` - Refactoring documentation (Phase 1-7)
- **Examples**: `/examples` - Example scripts only
- **Frontend**: `src/flock/frontend/src` - React components and frontend code

**Never create files in the root directory** - it should only contain configuration files like `pyproject.toml`, `README.md`, etc.

**📐 See [Architecture Overview](docs/architecture.md) for complete module organization details.**

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

Python 3.12+, so you can use:
- `match`/`case` statements
- `TaskGroup` for parallel execution (see [docs/patterns/async_patterns.md](docs/patterns/async_patterns.md))
- Improved type hints (`list[str]` not `List[str]`)
- Exception groups with `except*` (see [docs/patterns/error_handling.md](docs/patterns/error_handling.md))

**⚠️ CRITICAL:** Follow error handling and async patterns documented in `/docs/patterns/` - these are REQUIRED for all new code.

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
from flock import Flock  # ✅ Correct import (refactored in Phase 3)
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

**Semantic subscriptions (AI-powered routing):**
```python
# Simple semantic matching (default threshold 0.4)
security_agent = (
    orchestrator.agent("security")
    .consumes(SupportTicket, semantic_match="security vulnerability")
    .publishes(SecurityAlert)
)

# With custom threshold
strict_agent = (
    orchestrator.agent("strict")
    .consumes(Task, semantic_match="urgent priority", semantic_threshold=0.7)
    .publishes(Response)
)

# Multiple predicates (AND logic)
billing_agent = (
    orchestrator.agent("billing")
    .consumes(Ticket, semantic_match=["billing payment", "refund request"])
    .publishes(BillingResponse)
)
```

**Run agent:**
```python
await orchestrator.arun(agent, input_data)
```

**Fan-out publishing (multiple outputs):**
```python
# Single-type fan-out: Generate 10 outputs per execution
agent = (
    orchestrator.agent("generator")
    .consumes(InputType)
    .publishes(OutputType, fan_out=10)
)

# Multi-output fan-out: Generate 3 of EACH type = 9 total artifacts in ONE LLM call!
multi_master = (
    orchestrator.agent("multi_master")
    .consumes(Idea)
    .publishes(Movie, MovieScript, MovieCampaign, fan_out=3)
)
# Result: 3 Movies + 3 MovieScripts + 3 MovieCampaigns = 9 artifacts
# 89% cost savings vs 9 separate calls + perfect context alignment!

# With filtering (reduce noise)
agent.publishes(OutputType, fan_out=20, where=lambda o: o.score >= 8.0)

# With validation (enforce quality)
agent.publishes(
    OutputType,
    fan_out=10,
    validate=lambda o: o.field in ["valid", "values"]
)

# With dynamic visibility (per-artifact access control)
agent.publishes(
    OutputType,
    fan_out=5,
    visibility=lambda o: PrivateVisibility(agents=[o.recipient])
)
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
- **[Architecture Overview](docs/architecture.md)** - Complete system design, module organization, Phase 1-7 refactoring ⭐ **MUST READ**
- **[Error Handling Patterns](docs/patterns/error_handling.md)** - Production error handling guide ⭐ **REQUIRED**
- **[Async Patterns](docs/patterns/async_patterns.md)** - Async/await best practices ⭐ **REQUIRED**
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

*Last updated: October 19, 2025*
*This file follows the modern AGENTS.md format for AI coding agents.*
*Reflects Phase 1-7 refactoring with updated module organization and patterns.*
