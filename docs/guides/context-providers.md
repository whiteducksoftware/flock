# Context Providers

Flock's **Context Provider system** is the intelligent filter layer that controls what context each agent receives from the [blackboard](blackboard.md)—enabling smart filtering, sensitive data redaction, and massive token cost reduction.

**Think of it like a personalized news feed:** not every agent needs to see every artifact. Security analysts see errors, performance engineers see metrics, and sensitive data gets automatically redacted before agents ever see it.

**Unlike traditional blackboard architectures**, Flock gives you **surgical control** over agent context with zero code in your agents.

---

## What is a Context Provider?

A **Context Provider** is a security and filtering boundary that sits between agents and the blackboard store, controlling what artifacts agents can access.

- **Smart Filtering** - Give each agent exactly the context they need
- **Security Boundary** - Enforce visibility rules that agents cannot bypass
- **Data Redaction** - Automatically remove sensitive information
- **Performance Optimization** - Reduce token costs by 90%+ with targeted context
- **Zero Agent Code** - Filtering logic lives in infrastructure, not business logic

**Key principle:** Agents are **untrusted business logic**. Context Providers are the **trusted security boundary** between agents and infrastructure.

---

## The Security Problem

Before Context Providers, Flock had three critical security vulnerabilities:

### Vulnerability #1: READ Bypass

```python
# ❌ BEFORE: Agents could bypass visibility
async def __call__(self, ctx: Context, inputs: list[dict]) -> list[dict]:
    # Agent bypasses visibility filtering!
    all_artifacts = await ctx.board.list()  # Sees EVERYTHING
    secrets = [a for a in all_artifacts if "password" in str(a)]
```

**Problem:** Agents had direct `ctx.board` access, allowing them to bypass visibility controls.

### Vulnerability #2: WRITE Bypass

```python
# ❌ BEFORE: Agents could bypass validation
async def __call__(self, ctx: Context, inputs: list[dict]) -> list[dict]:
    # Agent publishes invalid data directly!
    await ctx.board.publish(invalid_artifact)  # No validation!
```

**Problem:** Agents could publish directly to the board, bypassing schema validation and security checks.

### Vulnerability #3: GOD MODE

```python
# ❌ BEFORE: Agents had unlimited infrastructure access
async def __call__(self, ctx: Context, inputs: list[dict]) -> list[dict]:
    # Agent modifies orchestrator state!
    await ctx.orchestrator.stop()  # Nuclear option
    ctx.orchestrator._agents = {}  # Delete all agents
```

**Problem:** Agents had full `ctx.orchestrator` access with no restrictions.

---

## The Solution: Context Provider Architecture

```mermaid
graph TB
    subgraph "🏗️ Orchestrator (Trusted)"
        Orch[Orchestrator]
        EvalContext[Evaluate Context<br/>using Provider]
    end

    subgraph "🔐 Security Boundary"
        Provider[Context Provider<br/>Smart Filter + Security]
        Visibility[Visibility Enforcement]
        Redaction[Sensitive Data Redaction]
        Filtering[Tag/Type/Source Filtering]
    end

    subgraph "🗄️ Infrastructure (Trusted)"
        Store[Blackboard Store]
        Artifacts[(All Artifacts)]
    end

    subgraph "🤖 Engine (Untrusted)"
        Engine[Engine Business Logic]
        NoProvider[❌ No ctx.provider]
        NoStore[❌ No ctx.store]
        NoBoard[❌ No ctx.board]
        NoOrch[❌ No ctx.orchestrator]
        ReadOnly[✅ ctx.artifacts (read-only)]
    end

    Orch -->|1. Calls Provider| EvalContext
    EvalContext -->|Uses| Provider
    Provider -->|Query| Store
    Store --> Artifacts

    Provider --> Visibility
    Provider --> Redaction
    Provider --> Filtering

    Visibility -->|Pre-filtered| Orch
    Redaction -->|Safe Data| Orch
    Filtering -->|Relevant Only| Orch

    Orch -->|2. Creates Context<br/>with artifacts| Engine
    Engine -->|Reads| ReadOnly

    style Orch fill:#10b981,stroke:#333,stroke-width:3px,color:#fff
    style Provider fill:#10b981,stroke:#333,stroke-width:3px,color:#fff
    style Store fill:#3b82f6,stroke:#333,stroke-width:2px,color:#fff
    style Engine fill:#ef4444,stroke:#333,stroke-width:2px,color:#fff
    style Visibility fill:#8b5cf6,stroke:#333,stroke-width:2px,color:#fff
    style Redaction fill:#f59e0b,stroke:#333,stroke-width:2px,color:#fff
    style Filtering fill:#06b6d4,stroke:#333,stroke-width:2px,color:#fff
```

**Phase 8 Architecture (Current):**

The orchestrator evaluates context using the configured provider **BEFORE** creating Context. Engines receive only pre-filtered artifacts via `ctx.artifacts` and **cannot query for additional data**. This ensures engines are pure functions: `input + ctx.artifacts → output`.

**Execution Flow:**
1. **Orchestrator** uses Context Provider to fetch and filter artifacts
2. **Context Provider** enforces visibility, applies filtering, redacts sensitive data
3. **Orchestrator** creates Context with pre-filtered `artifacts` list (no capabilities!)
4. **Engine** reads `ctx.artifacts` (pre-filtered data only)

**Key Security Properties:**
- ✅ **No Direct Board Access** - Engines can't access `ctx.board`
- ✅ **No Direct Publishing** - Orchestrator validates and publishes
- ✅ **No Orchestrator Access** - Engines can't access `ctx.orchestrator`
- ✅ **No Provider Access** - Engines can't access `ctx.provider` (orchestrator uses it)
- ✅ **No Store Access** - Engines can't access `ctx.store` (orchestrator uses it)
- ✅ **Visibility Enforced** - Context Provider MUST filter by visibility
- ✅ **Custom Filtering** - Tag, type, source, correlation filtering
- ✅ **Data Redaction** - Remove sensitive data automatically
- ✅ **Pure Functions** - Engines are `(input, pre-filtered context) → output`

---

## 🔒 Security by Design: BaseContextProvider

**The game-changer:** In Flock, it's **architecturally impossible** to create a context provider that forgets to check visibility.

Every built-in context provider (and your custom ones should too) inherits from `BaseContextProvider`, which **automatically enforces** visibility filtering before your code even runs. You literally cannot bypass this—it's baked into the architecture.

### The Old Way (Error-Prone)

```python
# ❌ Other frameworks: Security is your responsibility
class MyProvider:
    async def __call__(self, request):
        # Query artifacts
        artifacts = await store.query_artifacts(...)

        # OOPS! Forgot to check visibility!
        return [serialize(a) for a in artifacts]  # 🔥 Security vulnerability!
```

**Problem:** Easy to forget visibility filtering = accidental data leaks.

### The New Way (Bulletproof)

```python
# ✅ Flock: Security is enforced automatically
from flock.context_provider import BaseContextProvider

class MyProvider(BaseContextProvider):
    async def get_artifacts(self, request):
        # Just query and return artifacts
        artifacts, _ = await request.store.query_artifacts(...)
        return artifacts

        # ✨ BaseContextProvider automatically:
        # 1. Filters by visibility (you cannot bypass this!)
        # 2. Excludes requested IDs
        # 3. Serializes to consistent format
```

**Result:** You focus on query logic. Security is guaranteed by the base class.

### Architecture Pattern

```python
class BaseContextProvider(ABC):
    """Enforces MANDATORY visibility filtering."""

    @abstractmethod
    async def get_artifacts(self, request):
        """Subclasses implement: query/filter logic."""
        pass

    async def __call__(self, request):
        """Base class enforces: security, serialization."""
        # 1. Get artifacts from subclass
        artifacts = await self.get_artifacts(request)

        # 2. MANDATORY visibility filtering (CANNOT BE BYPASSED!)
        visible_artifacts = [
            artifact for artifact in artifacts
            if artifact.visibility.allows(request.agent_identity)
        ]

        # 3. Exclude specific IDs (if requested)
        if request.exclude_ids:
            visible_artifacts = [a for a in visible_artifacts if a.id not in request.exclude_ids]

        # 4. Serialize to consistent format
        return [serialize(artifact) for artifact in visible_artifacts]
```

### All Built-In Providers Inherit BaseContextProvider

Every context provider in Flock inherits this security guarantee:

```python
# All enforce visibility automatically!
class DefaultContextProvider(BaseContextProvider): ...
class CorrelatedContextProvider(BaseContextProvider): ...
class RecentContextProvider(BaseContextProvider): ...
class TimeWindowContextProvider(BaseContextProvider): ...
class EmptyContextProvider(BaseContextProvider): ...
class FilteredContextProvider(BaseContextProvider): ...
```

**What this means:**
- ✅ **Impossible to bypass** - Visibility filtering is architectural, not optional
- ✅ **~75% less code** - Providers go from ~80 lines to ~10-20 lines
- ✅ **Consistent behavior** - All providers serialize the same way
- ✅ **Pit of success** - Developers literally cannot forget security
- ✅ **Future-proof** - Security updates apply to all providers automatically

### Custom Provider Template

**The right way to create custom providers:**

```python
from flock.context_provider import BaseContextProvider, ContextRequest
from flock.artifacts import Artifact

class MyCustomProvider(BaseContextProvider):
    """My custom filtering logic with automatic security."""

    async def get_artifacts(self, request: ContextRequest) -> list[Artifact]:
        # 1. Query artifacts with your custom logic
        artifacts, _ = await request.store.query_artifacts(
            # Your filter criteria here
            limit=100
        )

        # 2. Apply any custom filtering (e.g., time-based, priority, etc.)
        filtered = [a for a in artifacts if self.my_custom_logic(a)]

        # 3. Return artifacts (BaseContextProvider handles the rest!)
        return filtered

        # ✨ BaseContextProvider automatically:
        # - Filters by visibility (MANDATORY, cannot bypass!)
        # - Excludes requested IDs
        # - Serializes to standard format

    def my_custom_logic(self, artifact):
        # Your custom filtering logic here
        return True
```

**Benefits:**
- 🔒 Security is enforced automatically
- 📉 Write 1/5th the code (10 lines vs 50+)
- ✅ Consistent with all built-in providers
- 🎯 Focus on business logic, not infrastructure

**This is why Flock's security is different:** It's not something you remember to add. It's something you **cannot forget**. When you're building HIPAA-compliant healthcare systems or SOC2-certified SaaS platforms, "impossible to bypass even by accident" is the only acceptable standard.

---

## Provider Priority Hierarchy

When multiple providers are configured, Flock uses this priority:

```
Per-Agent Provider  >  Global Provider  >  DefaultContextProvider
     (highest)            (medium)              (fallback)
```

**Example:**

```python
# Global provider for all agents
global_provider = FilteredContextProvider(FilterConfig(tags={"ERROR"}))
flock = Flock("openai/gpt-4.1", context_provider=global_provider)

# Per-agent override (takes priority!)
warn_agent = flock.agent("warn_analyzer").consumes(Log).publishes(Analysis).agent
warn_agent.context_provider = FilteredContextProvider(FilterConfig(tags={"WARN", "ERROR"}))
```

**Resolution:**
- `warn_agent` uses its per-agent provider (WARN + ERROR)
- Other agents use global provider (ERROR only)
- If no providers configured, fallback to `DefaultContextProvider` (visibility-only)

---

## Built-In Provider Types

### 1. DefaultContextProvider

**What it does:** Shows ALL artifacts on blackboard (visibility filtering only).

**EXPLICIT IS BETTER THAN IMPLICIT:** No magic correlation filtering! For workflow isolation, use `CorrelatedContextProvider` explicitly.

```python
from flock.context_provider import DefaultContextProvider

# Show agents everything they're allowed to see
provider = DefaultContextProvider()
flock = Flock("openai/gpt-4.1", context_provider=provider)
```

**Use when:**
- You want full blackboard visibility
- No additional filtering needed
- Agents decide what's relevant from all visible artifacts

**Performance:** Returns all artifacts (can be expensive with large boards)

---

### 2. CorrelatedContextProvider

**What it does:** Workflow isolation - only show artifacts from the agent's specific workflow (correlation_id).

```python
from flock.context_provider import CorrelatedContextProvider

# Agents only see their workflow artifacts
provider = CorrelatedContextProvider()
flock = Flock("openai/gpt-4.1", context_provider=provider)
```

**Use when:**
- Multi-tenant SaaS with workflow-based isolation
- Each workflow should be independent
- Prevent cross-workflow data leakage

**Performance:** Efficient - filters by correlation_id at query time

---

### 3. RecentContextProvider

**What it does:** Token cost control - show only the N most recent artifacts (sorted by timestamp).

```python
from flock.context_provider import RecentContextProvider

# Only show last 50 artifacts
provider = RecentContextProvider(limit=50)
flock = Flock("openai/gpt-4.1", context_provider=provider)
```

**Use when:**
- High-volume systems with many artifacts
- Recent data is more relevant than old data
- Token cost control is critical

**Performance:** ⭐ 90%+ token savings on large blackboards!

---

### 4. TimeWindowContextProvider

**What it does:** Time-based filtering - show only artifacts from the last X hours.

```python
from flock.context_provider import TimeWindowContextProvider

# Only show artifacts from last hour
provider = TimeWindowContextProvider(hours=1)
flock = Flock("openai/gpt-4.1", context_provider=provider)
```

**Use when:**
- Real-time monitoring systems
- Event-driven architectures
- Old data becomes irrelevant quickly

**Performance:** Automatic cleanup - no manual pruning needed!

---

### 5. EmptyContextProvider

**What it does:** Stateless agents - returns NO historical context at all.

```python
from flock.context_provider import EmptyContextProvider

# Agent is purely functional (input → output)
provider = EmptyContextProvider()
translator.context_provider = provider  # No context needed!
```

**Use when:**
- Simple transformation agents (translation, formatting, etc.)
- No historical context needed
- Maximum token savings (zero context overhead)

**Performance:** 💯 Zero context tokens!

**Example use cases:**
- English → Spanish translator
- Markdown → HTML converter
- Image → Thumbnail generator

---

### 6. FilteredContextProvider (Declarative Filtering)

**What it does:** Declarative filtering with `FilterConfig` criteria.

```python
from flock.context_provider import FilteredContextProvider
from flock.store import FilterConfig

# Only show high-priority errors from trusted sources
provider = FilteredContextProvider(
    FilterConfig(
        tags={"ERROR", "high"},           # Match these tags (OR logic)
        type_names={"SystemError"},       # Only this type
        produced_by=["trusted_monitor"],  # Only from this agent
        correlation_id="incident-123"     # In this workflow
    ),
    limit=50  # Max 50 artifacts
)

flock = Flock("openai/gpt-4.1", context_provider=provider)
```

**FilterConfig Options:**

| Parameter | Type | Logic | Description |
|-----------|------|-------|-------------|
| `tags` | `set[str]` | OR | Match any of these tags |
| `type_names` | `set[str]` | OR | Match these artifact types |
| `produced_by` | `list[str]` | OR | From these agents |
| `correlation_id` | `str` | Exact | In this workflow |

**Criteria Combination:**
- Multiple criteria = **AND** logic (all must match)
- Multiple values within criterion = **OR** logic (any can match)

**Example:**

```python
FilterConfig(
    tags={"ERROR", "WARN"},     # (ERROR OR WARN)
    type_names={"LogEntry"}     # AND type is LogEntry
)
# Result: LogEntry artifacts with ERROR OR WARN tags
```

**Use when:**
- You know filtering criteria upfront
- Simple tag/type/source filtering
- Performance matters (query-time filtering)

---

### 3. Custom Context Providers

**What it does:** Your own logic for filtering, redaction, audit, etc.

**Important (Phase 8):** Context Providers are called by the **orchestrator**, not by engines. The orchestrator uses the provider to evaluate context, then creates Context with pre-filtered `artifacts`. Engines receive this pre-filtered data and cannot query for more.

```python
from flock.context_provider import ContextProvider, ContextRequest

class MyCustomProvider(ContextProvider):
    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # Called by ORCHESTRATOR (not engines!)
        # This runs BEFORE Context is created

        # 1. Query artifacts from store
        artifacts, _ = await request.store.query_artifacts(limit=100)

        # 2. MANDATORY: Filter by visibility
        visible = [
            a for a in artifacts
            if a.visibility.allows(request.agent_identity)
        ]

        # 3. Apply your custom logic
        filtered = self.my_custom_filtering(visible)

        # 4. Return context (orchestrator puts this in ctx.artifacts)
        return [
            {
                "type": a.type,
                "payload": a.payload,
                "produced_by": a.produced_by,
                "created_at": a.created_at,
                "id": str(a.id),
                "correlation_id": str(a.correlation_id) if a.correlation_id else None,
                "tags": list(a.tags) if a.tags else [],
            }
            for a in filtered
        ]

        # Result: Orchestrator creates Context(artifacts=<this list>)
        # Engines read: ctx.artifacts (pre-filtered, immutable)
```

**Use when:**
- Complex filtering logic
- Data transformation/redaction
- Audit logging
- Custom security policies

**See Production Example:** [PasswordRedactorProvider](../../examples/08-context-provider/05_password_redactor.py) - production-ready password and secret filtering you can steal!

---

## Creating Custom Context Providers

### The ContextProvider Protocol

Every Context Provider must implement this interface:

```python
from typing import Any
from flock.context_provider import ContextProvider, ContextRequest

class MyProvider(ContextProvider):
    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch and filter context for an agent.

        Args:
            request: Contains agent, store, correlation_id, identity

        Returns:
            List of artifact dicts with filtered/transformed data
        """
        pass
```

**ContextRequest Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `agent` | `Agent` | The requesting agent object |
| `agent_identity` | `AgentIdentity` | Identity with labels for RBAC |
| `store` | `BlackboardStore` | Blackboard store for queries |
| `correlation_id` | `UUID \| None` | Current workflow ID (if any) |

### Example: Audit Logging Provider

```python
import logging
from datetime import datetime
from flock.context_provider import ContextProvider, ContextRequest, DefaultContextProvider

logger = logging.getLogger(__name__)

class AuditProvider(ContextProvider):
    """Logs all context access for compliance."""

    def __init__(self):
        self.default_provider = DefaultContextProvider()

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # Fetch context using default provider
        context = await self.default_provider(request)

        # Log access event
        logger.info(
            f"AUDIT: Agent '{request.agent.name}' accessed {len(context)} artifacts "
            f"at {datetime.now().isoformat()}"
        )

        # Record to compliance database (example)
        await self._record_audit_event(
            agent_name=request.agent.name,
            artifact_count=len(context),
            timestamp=datetime.now()
        )

        return context

    async def _record_audit_event(self, agent_name: str, artifact_count: int, timestamp: datetime):
        # Your audit storage logic here
        pass
```

### Example: Role-Based Filtering

```python
from flock.context_provider import ContextProvider, ContextRequest

class RoleBasedProvider(ContextProvider):
    """Filter artifacts based on agent role labels."""

    def __init__(self, role_config: dict[str, set[str]]):
        """
        Args:
            role_config: Map of roles to allowed artifact types
                Example: {"analyst": {"Log", "Metric"}, "admin": {"*"}}
        """
        self.role_config = role_config

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # Extract agent role from labels
        agent_roles = {
            label.split(":")[1]
            for label in request.agent_identity.labels
            if label.startswith("role:")
        }

        # Get allowed types for roles
        allowed_types = set()
        for role in agent_roles:
            if role in self.role_config:
                types = self.role_config[role]
                if "*" in types:  # Admin wildcard
                    allowed_types = {"*"}
                    break
                allowed_types.update(types)

        # Query artifacts
        artifacts, _ = await request.store.query_artifacts(limit=100)

        # Filter by visibility (MANDATORY)
        visible = [a for a in artifacts if a.visibility.allows(request.agent_identity)]

        # Filter by role permissions
        if "*" not in allowed_types:
            filtered = [a for a in visible if any(t in a.type for t in allowed_types)]
        else:
            filtered = visible

        return [
            {
                "type": a.type,
                "payload": a.payload,
                "produced_by": a.produced_by,
                "created_at": a.created_at,
                "id": str(a.id),
                "correlation_id": str(a.correlation_id) if a.correlation_id else None,
                "tags": list(a.tags) if a.tags else [],
            }
            for a in filtered
        ]

# Usage
provider = RoleBasedProvider({
    "analyst": {"LogEntry", "Metric"},
    "engineer": {"LogEntry", "Metric", "SystemEvent"},
    "admin": {"*"}  # See everything
})

flock = Flock("openai/gpt-4.1", context_provider=provider)
```

---

## Production Example: Password Redaction

The [PasswordRedactorProvider](../../examples/08-context-provider/05_password_redactor.py) is a **production-ready** custom provider that automatically redacts sensitive data.

**What it catches:**
- 🔒 Passwords and secrets
- 🔑 API keys (OpenAI, AWS, GitHub, GitLab, Stripe, Google)
- 🎫 Bearer tokens and JWT
- 💳 Credit card numbers (Visa, MC, Amex, Discover)
- 🆔 Social Security Numbers
- 🔐 Private keys (RSA, EC, OpenSSH)
- 📧 Email addresses (optional)
- 🎨 Custom patterns (add your own!)

**Quick Start:**

```python
from examples.context_provider import PasswordRedactorProvider

# Basic usage - production defaults
provider = PasswordRedactorProvider()
flock = Flock("openai/gpt-4.1", context_provider=provider)

# With customization
provider = PasswordRedactorProvider(
    redaction_text="[SECURITY_REDACTED]",
    redact_emails=True,
    custom_patterns={
        "bitcoin": r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b",
        "employee_id": r"EMP-\d{6}"
    },
    log_redactions=True  # Audit trail
)
```

**What gets redacted:**

```python
# Input artifacts
{
    "user_data": {
        "password": "MySecretPass123",      # → [REDACTED]
        "api_key": "sk-1234567890abcdef",   # → [REDACTED]
        "email": "user@example.com"         # → [REDACTED] (if enabled)
    },
    "payment": {
        "card": "4532-1234-5678-9010",      # → [REDACTED]
        "cvv": "123"                        # Preserved (not in patterns)
    },
    "auth_header": "Bearer eyJhbGci..."     # → [REDACTED]
}

# Agents see
{
    "user_data": {
        "password": "[REDACTED]",
        "api_key": "[REDACTED]",
        "email": "[REDACTED]"
    },
    "payment": {
        "card": "[REDACTED]",
        "cvv": "123"
    },
    "auth_header": "[REDACTED]"
}
```

**💡 This is production code you can copy!** See [examples/08-context-provider/05_password_redactor.py](../../examples/08-context-provider/05_password_redactor.py) for the full implementation (391 lines).

---

## Real-World Use Cases

### Healthcare: HIPAA Compliance

**Challenge:** Protect PHI (Protected Health Information) while enabling analytics.

```python
from flock.context_provider import ContextProvider, ContextRequest

class PHIRedactorProvider(ContextProvider):
    """Redacts PHI from medical records."""

    PHI_PATTERNS = {
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "mrn": re.compile(r"MRN[:\s]*\d{6,10}"),
        "dob": re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),
        "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    }

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # Query visible artifacts
        artifacts, _ = await request.store.query_artifacts(limit=100)
        visible = [a for a in artifacts if a.visibility.allows(request.agent_identity)]

        # Redact PHI from each artifact
        redacted = []
        for artifact in visible:
            payload = self._redact_phi(artifact.payload)
            redacted.append({
                "type": artifact.type,
                "payload": payload,
                "produced_by": artifact.produced_by,
                "created_at": artifact.created_at,
                "id": str(artifact.id),
                "correlation_id": str(artifact.correlation_id) if artifact.correlation_id else None,
                "tags": list(artifact.tags) if artifact.tags else [],
            })

        return redacted

    def _redact_phi(self, payload: dict) -> dict:
        # Recursively redact PHI patterns
        redacted = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                redacted[key] = self._redact_phi(value)
            elif isinstance(value, str):
                for pattern_name, pattern in self.PHI_PATTERNS.items():
                    value = pattern.sub("[REDACTED-PHI]", value)
                redacted[key] = value
            else:
                redacted[key] = value
        return redacted

# Usage
provider = PHIRedactorProvider()
flock = Flock("openai/gpt-4.1", context_provider=provider)
```

**Benefits:**
- ✅ HIPAA compliance (no PHI exposed to agents)
- ✅ Enable AI analytics on medical records
- ✅ Automatic enforcement (agents can't bypass)

---

### Financial Services: PCI-DSS Compliance

**Challenge:** Process transactions without exposing credit card data.

```python
from flock.context_provider import FilteredContextProvider
from flock.store import FilterConfig

# Only show anonymized transaction summaries
provider = FilteredContextProvider(
    FilterConfig(
        tags={"transaction_summary", "pci_safe"},  # Only safe artifacts
        type_names={"TransactionSummary"}          # Not raw card data
    ),
    limit=100
)

# Combined with custom redaction
class PCIRedactorProvider(ContextProvider):
    """Redacts PCI data (credit cards, CVV, PII)."""

    PCI_PATTERNS = {
        "card_number": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        "cvv": re.compile(r"\bcvv[:\s]*\d{3,4}\b", re.IGNORECASE),
        "expiry": re.compile(r"\b\d{2}/\d{2,4}\b"),
    }

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # Query and redact
        artifacts, _ = await request.store.query_artifacts(limit=100)
        visible = [a for a in artifacts if a.visibility.allows(request.agent_identity)]

        return [
            {
                "type": a.type,
                "payload": self._mask_card_data(a.payload),
                # ... other fields
            }
            for a in visible
        ]

    def _mask_card_data(self, payload: dict) -> dict:
        """Replace card numbers with masked version (last 4 digits)."""
        # Example: 4532-1234-5678-9010 → ****-****-****-9010
        pass
```

---

### DevOps: Log Filtering & Secret Redaction

**Challenge:** Give engineers relevant logs without exposing secrets.

```python
# Different providers for different roles
error_provider = FilteredContextProvider(
    FilterConfig(tags={"ERROR", "CRITICAL"}),
    limit=50
)

info_provider = FilteredContextProvider(
    FilterConfig(tags={"INFO", "WARN", "ERROR"}),
    limit=100
)

all_logs_provider = FilteredContextProvider(
    FilterConfig(tags={"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"}),
    limit=200
)

# Assign by role
junior_engineer.context_provider = error_provider       # Errors only
senior_engineer.context_provider = info_provider        # Info + above
platform_team.context_provider = all_logs_provider      # Everything

# Add secret redaction globally
from examples.context_provider import PasswordRedactorProvider

global_provider = PasswordRedactorProvider(
    custom_patterns={
        "k8s_secret": r"[A-Za-z0-9+/]{40,}==?",
        "aws_key": r"AKIA[0-9A-Z]{16}",
    }
)

flock = Flock("openai/gpt-4.1", context_provider=global_provider)
```

**Benefits:**
- ✅ Reduce noise (90% fewer logs for junior engineers)
- ✅ Protect secrets (auto-redact API keys, tokens)
- ✅ Role-based access (senior engineers see more)

---

### Multi-Tenant SaaS: Customer Isolation

**Challenge:** Ensure Customer A's agents never see Customer B's data.

```python
from flock.core.visibility import TenantVisibility
from flock.context_provider import FilteredContextProvider
from flock.store import FilterConfig

# Tenant-specific provider
class TenantIsolationProvider(ContextProvider):
    """Enforces tenant isolation at context level."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # Query artifacts for this tenant only
        artifacts, _ = await request.store.query_artifacts(
            correlation_id=self.tenant_id,  # Tenant as correlation
            limit=100
        )

        # Filter by visibility (MANDATORY)
        visible = [a for a in artifacts if a.visibility.allows(request.agent_identity)]

        # Extra safety: verify tenant ID
        tenant_filtered = [
            a for a in visible
            if getattr(a, "tenant_id", None) == self.tenant_id
        ]

        return [
            {
                "type": a.type,
                "payload": a.payload,
                "produced_by": a.produced_by,
                "created_at": a.created_at,
                "id": str(a.id),
                "correlation_id": str(a.correlation_id) if a.correlation_id else None,
                "tags": list(a.tags) if a.tags else [],
            }
            for a in tenant_filtered
        ]

# Create tenant-specific orchestrators
customer_a_flock = Flock(
    "openai/gpt-4.1",
    context_provider=TenantIsolationProvider(tenant_id="customer_a")
)

customer_b_flock = Flock(
    "openai/gpt-4.1",
    context_provider=TenantIsolationProvider(tenant_id="customer_b")
)
```

---

## Performance Optimization

### Token Cost Reduction

Context Providers can reduce token costs by **90%+** through smart filtering:

**Before (No Filtering):**
```python
# Agent sees ALL 1000 artifacts on blackboard
# Cost: 1000 artifacts × 200 tokens each = 200,000 tokens
# At $0.03/1M tokens = $0.006 per agent call
```

**After (Smart Filtering):**
```python
# Agent sees ONLY 10 relevant artifacts
# Cost: 10 artifacts × 200 tokens each = 2,000 tokens
# At $0.03/1M tokens = $0.00006 per agent call

# 💰 99% cost reduction!

provider = FilteredContextProvider(
    FilterConfig(tags={"high", "urgent"}, type_names={"Alert"}),
    limit=10
)
```

### Query Performance

**Optimize provider queries:**

```python
# ❌ BAD: Query all, filter later
artifacts, _ = await request.store.query_artifacts()  # Gets everything
filtered = [a for a in artifacts if a.tags.intersection({"urgent"})]

# ✅ GOOD: Filter at query time
artifacts, _ = await request.store.query_artifacts(
    filter=FilterConfig(tags={"urgent"}),  # DB-level filtering
    limit=50  # Limit results
)
```

### Caching Strategies

**Cache frequently accessed context:**

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedProvider(ContextProvider):
    """Cache context for 60 seconds."""

    def __init__(self):
        self.cache = {}
        self.cache_ttl = timedelta(seconds=60)

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        cache_key = f"{request.agent.name}:{request.correlation_id}"

        # Check cache
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return cached_data

        # Fetch fresh data
        artifacts, _ = await request.store.query_artifacts(limit=100)
        visible = [a for a in artifacts if a.visibility.allows(request.agent_identity)]

        context = [
            {"type": a.type, "payload": a.payload, ...}
            for a in visible
        ]

        # Update cache
        self.cache[cache_key] = (context, datetime.now())

        return context
```

**⚠️ Cache Considerations:**
- Don't cache sensitive data too long
- Invalidate on artifact creation
- Use short TTLs (60s or less)

---

## Security Best Practices

### ✅ Do

- **Always enforce visibility** - NEVER skip visibility filtering
  ```python
  # ✅ MANDATORY visibility check
  visible = [a for a in artifacts if a.visibility.allows(request.agent_identity)]
  ```

- **Use FilteredContextProvider for common patterns** - Declarative is safer than imperative
  ```python
  # ✅ Declarative filtering
  FilteredContextProvider(FilterConfig(tags={"safe"}))
  ```

- **Test your redaction patterns** - Verify secrets are actually redacted
  ```python
  # ✅ Unit test pattern matching
  assert PasswordRedactorProvider().matches("sk-1234567890abcdef")
  ```

- **Log security events** - Track what gets redacted
  ```python
  # ✅ Audit redactions
  logger.info(f"Redacted {count} secrets for agent {agent_name}")
  ```

- **Limit by default** - Start restrictive, loosen as needed
  ```python
  # ✅ Conservative defaults
  FilterConfig(tags={"approved_only"}, limit=10)
  ```

- **Fail fast on missing visibility** - Don't fall back to "show everything"
  ```python
  # ✅ Explicit failure
  if not artifact.visibility:
      raise SecurityError("Artifact missing visibility control")
  ```

### ❌ Don't

- **Don't skip visibility filtering** - This is a security boundary
  ```python
  # ❌ SECURITY VULNERABILITY
  artifacts, _ = await request.store.query_artifacts()
  return artifacts  # No visibility check!
  ```

- **Don't leak sensitive data** - Check all fields, not just top-level
  ```python
  # ❌ Nested secrets not redacted
  payload = {"user": {"password": "secret123"}}  # Missed!
  ```

- **Don't cache redacted data** - Re-apply redaction on cache miss
  ```python
  # ❌ Cached data might bypass redaction
  if cache_key in cache:
      return cache[cache_key]  # Was this redacted?
  ```

- **Don't trust agent input** - Agents are untrusted, validate everything
  ```python
  # ❌ Agent could manipulate correlation_id
  # ✅ Use request.correlation_id from orchestrator
  ```

- **Don't expose infrastructure details** - Keep internals hidden
  ```python
  # ❌ Exposing store internals
  payload = {"_store_path": artifact._internal_path}
  ```

- **Don't forget to test edge cases** - Unicode, binary data, deeply nested dicts
  ```python
  # ✅ Test with real-world messy data
  test_data = {"password": "🔒secret123", "nested": {"api_key": "..."}}
  ```

---

## Debugging Context Providers

### Agent Not Seeing Expected Artifacts?

**Check provider filtering:**

```python
# Print what agent sees
request = ContextRequest(
    agent=agent,
    agent_identity=agent.identity,
    store=flock.store,
    correlation_id=None
)

context = await agent.context_provider(request)
print(f"Agent {agent.name} sees {len(context)} artifacts:")
for item in context:
    print(f"  - {item['type']}: {item['payload']}")
```

**Common issues:**
- Tags don't match `FilterConfig`
- Visibility blocks agent
- Correlation ID mismatch
- Provider limit too low

### Verify Visibility Enforcement

```python
# Test visibility filtering
from flock.core.visibility import PrivateVisibility, PublicVisibility, AgentIdentity

# Create test artifacts
public_artifact = Artifact(visibility=PublicVisibility(), ...)
private_artifact = Artifact(visibility=PrivateVisibility(agents={"allowed_agent"}), ...)

# Test agent identity
blocked_identity = AgentIdentity(name="blocked_agent", labels=set())
allowed_identity = AgentIdentity(name="allowed_agent", labels=set())

# Verify filtering
assert public_artifact.visibility.allows(blocked_identity)  # ✅ Public = everyone
assert not private_artifact.visibility.allows(blocked_identity)  # ✅ Blocked
assert private_artifact.visibility.allows(allowed_identity)  # ✅ Allowed
```

### Test Redaction Patterns

```python
# Unit test your patterns
provider = PasswordRedactorProvider()

test_payloads = [
    {"password": "MySecret123"},              # → {"password": "[REDACTED]"}
    {"api_key": "sk-1234567890abcdef"},       # → {"api_key": "[REDACTED]"}
    {"nested": {"token": "Bearer eyJ..."}},   # → {"nested": {"token": "[REDACTED]"}}
]

for payload in test_payloads:
    redacted = provider._redact_dict(payload)
    assert "[REDACTED]" in str(redacted), f"Failed to redact: {payload}"
```

### Enable Provider Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("flock.context_provider")

# Providers should log their actions
logger.debug(f"FilteredContextProvider: Filtered {len(artifacts)} → {len(filtered)}")
logger.info(f"PasswordRedactorProvider: Redacted {count} secrets")
```

---

## Advanced Patterns

### Composite Providers (Chaining Logic)

```python
class CompositeProvider(ContextProvider):
    """Chain multiple providers together."""

    def __init__(self, providers: list[ContextProvider]):
        self.providers = providers

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        context = None

        for provider in self.providers:
            if context is None:
                # First provider queries store
                context = await provider(request)
            else:
                # Subsequent providers transform context
                # (Hack: pass context as modified request)
                context = await provider.transform(context, request)

        return context

# Usage
provider = CompositeProvider([
    FilteredContextProvider(FilterConfig(tags={"approved"})),  # Filter first
    PasswordRedactorProvider(),                                # Then redact
    AuditProvider()                                            # Then log
])
```

### Conditional Filtering (Role-Based)

```python
class RoleAwareProvider(ContextProvider):
    """Different filtering based on agent role."""

    def __init__(self):
        self.role_providers = {
            "admin": FilteredContextProvider(FilterConfig(tags={"*"})),  # See all
            "engineer": FilteredContextProvider(FilterConfig(tags={"ERROR", "WARN"})),
            "analyst": FilteredContextProvider(FilterConfig(tags={"INFO", "ERROR"})),
        }
        self.default_provider = FilteredContextProvider(FilterConfig(tags={"ERROR"}))

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # Extract role from agent labels
        role = None
        for label in request.agent_identity.labels:
            if label.startswith("role:"):
                role = label.split(":")[1]
                break

        # Get role-specific provider
        provider = self.role_providers.get(role, self.default_provider)

        # Delegate to role provider
        return await provider(request)
```

### Time-Based Filtering

```python
from datetime import datetime, timedelta

class RecentOnlyProvider(ContextProvider):
    """Only show artifacts from last N hours."""

    def __init__(self, hours: int = 24):
        self.cutoff_delta = timedelta(hours=hours)

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        cutoff = datetime.now() - self.cutoff_delta

        # Query all artifacts
        artifacts, _ = await request.store.query_artifacts(limit=1000)

        # Filter by visibility (MANDATORY)
        visible = [a for a in artifacts if a.visibility.allows(request.agent_identity)]

        # Filter by timestamp
        recent = [a for a in visible if a.created_at >= cutoff]

        return [
            {
                "type": a.type,
                "payload": a.payload,
                "produced_by": a.produced_by,
                "created_at": a.created_at,
                "id": str(a.id),
                "correlation_id": str(a.correlation_id) if a.correlation_id else None,
                "tags": list(a.tags) if a.tags else [],
            }
            for a in recent
        ]

# Usage
provider = RecentOnlyProvider(hours=1)  # Last hour only
```

### Metric-Based Filtering (Priority)

```python
class PriorityProvider(ContextProvider):
    """Show highest priority artifacts first."""

    PRIORITY_MAP = {
        "CRITICAL": 1,
        "HIGH": 2,
        "MEDIUM": 3,
        "LOW": 4
    }

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # Query artifacts
        artifacts, _ = await request.store.query_artifacts(limit=1000)

        # Filter by visibility (MANDATORY)
        visible = [a for a in artifacts if a.visibility.allows(request.agent_identity)]

        # Sort by priority (tags contain priority level)
        def get_priority(artifact):
            for tag in artifact.tags:
                if tag in self.PRIORITY_MAP:
                    return self.PRIORITY_MAP[tag]
            return 999  # Lowest priority

        sorted_artifacts = sorted(visible, key=get_priority)

        # Return top 50
        return [
            {
                "type": a.type,
                "payload": a.payload,
                "produced_by": a.produced_by,
                "created_at": a.created_at,
                "id": str(a.id),
                "correlation_id": str(a.correlation_id) if a.correlation_id else None,
                "tags": list(a.tags) if a.tags else [],
            }
            for a in sorted_artifacts[:50]
        ]
```

---

## Complete Example

Here's everything together—a multi-tenant SaaS with role-based filtering and secret redaction:

```python
import asyncio
from pydantic import BaseModel
from flock import Flock
from flock.core.visibility import TenantVisibility, AgentIdentity, LabelledVisibility
from flock.context_provider import FilteredContextProvider
from flock.store import FilterConfig
from examples.context_provider import PasswordRedactorProvider

# Define artifacts
class CustomerEvent(BaseModel):
    customer_id: str
    event_type: str
    data: dict

class CustomerReport(BaseModel):
    customer_id: str
    summary: str
    metrics: dict

# Create tenant-specific orchestrators
customer_a_flock = Flock("openai/gpt-4.1")
customer_b_flock = Flock("openai/gpt-4.1")

# Customer A: Analyst with basic access
analyst_a = (
    customer_a_flock.agent("analyst_a")
    .identity(AgentIdentity(
        name="analyst_a",
        labels={"tenant:customer_a", "role:analyst"}
    ))
    .consumes(CustomerEvent)
    .publishes(
        CustomerReport,
        visibility=TenantVisibility(tenant_id="customer_a")
    )
    .agent
)

# Custom provider: Filter + Redact
analyst_a.context_provider = CompositeProvider([
    FilteredContextProvider(FilterConfig(tags={"approved"})),  # Only approved data
    PasswordRedactorProvider()                                 # Redact secrets
])

# Customer B: Admin with full access
admin_b = (
    customer_b_flock.agent("admin_b")
    .identity(AgentIdentity(
        name="admin_b",
        labels={"tenant:customer_b", "role:admin"}
    ))
    .consumes(CustomerEvent)
    .publishes(
        CustomerReport,
        visibility=TenantVisibility(tenant_id="customer_b")
    )
    .agent
)

# Admin sees more (but still redacted)
admin_b.context_provider = CompositeProvider([
    FilteredContextProvider(FilterConfig(tags={"approved", "internal"})),  # More tags
    PasswordRedactorProvider()                                             # Still redact
])

# Use it
async def main():
    # Publish customer A data
    await customer_a_flock.publish(
        CustomerEvent(
            customer_id="customer_a",
            event_type="login",
            data={"password": "secret123", "email": "user@a.com"}  # Sensitive!
        ),
        visibility=TenantVisibility(tenant_id="customer_a"),
        tags={"approved"}
    )

    # Publish customer B data
    await customer_b_flock.publish(
        CustomerEvent(
            customer_id="customer_b",
            event_type="purchase",
            data={"card": "4532-1234-5678-9010", "amount": 99.99}  # Sensitive!
        ),
        visibility=TenantVisibility(tenant_id="customer_b"),
        tags={"approved", "internal"}
    )

    # Process independently
    await customer_a_flock.run_until_idle()
    await customer_b_flock.run_until_idle()

    # Verify isolation
    reports_a = await customer_a_flock.store.get_by_type(CustomerReport)
    reports_b = await customer_b_flock.store.get_by_type(CustomerReport)

    print(f"Customer A reports: {len(reports_a)}")  # 1
    print(f"Customer B reports: {len(reports_b)}")  # 1

asyncio.run(main())
```

**What happened:**
1. ✅ Customer A and B completely isolated (tenant visibility)
2. ✅ Analyst sees only "approved" tags
3. ✅ Admin sees "approved" + "internal" tags
4. ✅ Passwords, credit cards auto-redacted (PasswordRedactorProvider)
5. ✅ No customer can see other customer's data
6. ✅ Role-based access (analyst vs admin)

**Security guarantees:**
- 🔒 Tenant isolation enforced
- 🏷️ Role-based filtering working
- 🔐 Secrets redacted automatically
- ✅ Zero-trust architecture maintained

---

## Learn By Example

We've created a comprehensive learning path with 5 progressive examples:

**📚 [examples/08-context-provider/](../../examples/08-context-provider/)**

| Example | Complexity | What You'll Learn |
|---------|-----------|-------------------|
| [01_basic_visibility.py](../../examples/08-context-provider/01_basic_visibility.py) | Beginner | PublicVisibility vs PrivateVisibility |
| [02_global_provider.py](../../examples/08-context-provider/02_global_provider.py) | Beginner | Global FilteredContextProvider configuration |
| [03_per_agent_provider.py](../../examples/08-context-provider/03_per_agent_provider.py) | Intermediate | Per-agent overrides and priority |
| [04_custom_filtering.py](../../examples/08-context-provider/04_custom_filtering.py) | Intermediate | Advanced FilterConfig with multiple criteria |
| [05_password_redactor.py](../../examples/08-context-provider/05_password_redactor.py) | Expert | **Production-ready password filtering** ⭐ |

**🎁 Grand Finale:** Example 05 is production code you can copy directly into your projects! It catches passwords, API keys, JWT tokens, credit cards, SSN, and more.

**Start here:** [examples/08-context-provider/README.md](../../examples/08-context-provider/README.md)

---

## Next Steps

- **[Visibility Guide](visibility.md)** - Understanding the visibility system Context Providers enforce
- **[Agents Guide](agents.md)** - How agents interact with Context Providers
- **[Blackboard Architecture](blackboard.md)** - The store Context Providers query
- **[Dashboard](dashboard.md)** - Visualize context filtering in action
- **[Complete Examples](../../examples/08-context-provider/)** - Progressive learning path + production code

---

**Ready to build secure, performant multi-agent systems?** Start with the [examples](../../examples/08-context-provider/) and steal the [PasswordRedactorProvider](../../examples/08-context-provider/05_password_redactor.py) for your production system! 🚀
