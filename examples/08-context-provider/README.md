# 🔒 Context Provider Examples - Security & Filtering

Secure your multi-agent systems with Context Providers—the security boundary that controls what agents can see. From basic visibility to production-ready password filtering, these examples show you how to build secure, intelligent data access patterns.

## 🎯 Why Context Providers?

Context Providers solve critical security and performance challenges in multi-agent systems:

- **🔐 Security First** - Enforce visibility boundaries agents cannot bypass
- **🎯 Smart Filtering** - Give each agent exactly the context they need
- **⚡ Performance** - Reduce token usage by filtering irrelevant data
- **🛡️ Audit Trail** - Track what data agents access
- **🔧 Customizable** - Build providers for your specific needs

## 🎓 Learning Path

The examples progress from fundamental concepts to production-ready code you can steal!

### 🔰 Beginner Track (Examples 01-02)

#### 01 - Basic Visibility 🔒
Your first Context Provider! See how visibility controls work automatically.

```bash
uv run examples/08-context-provider/01_basic_visibility.py
```

**Concepts:**
- `PublicVisibility` vs `PrivateVisibility`
- Automatic security boundary enforcement
- Agents see only what they're allowed to see
- No explicit filtering code needed!

**Real-world use case:** Classified information systems where agents have different clearance levels

---

#### 02 - Global Provider 🌍
Configure a provider for ALL agents at once.

```bash
uv run examples/08-context-provider/02_global_provider.py
```

**Concepts:**
- `FilteredContextProvider` with `FilterConfig`
- Tag-based filtering (`tags={"urgent"}`)
- Global configuration via `Flock(context_provider=...)`
- Consistent filtering policy across all agents

**Real-world use case:** Organization-wide security policy enforcement

---

### 🛠️ Intermediate Track (Examples 03-04)

#### 03 - Per-Agent Overrides 🎯
Different agents, different context, different rules!

```bash
uv run examples/08-context-provider/03_per_agent_provider.py
```

**Concepts:**
- Per-agent provider configuration
- Provider priority: `per-agent > global > default`
- `agent.context_provider = my_provider`
- Specialized filtering for different agent roles

**Real-world use case:** Logging system where error analysts see errors only, while platform engineers see everything

---

#### 04 - Custom Filtering 🎨
Master FilterConfig for sophisticated context control.

```bash
uv run examples/08-context-provider/04_custom_filtering.py
```

**Concepts:**
- Multiple `FilterConfig` criteria
- Combining tags, types, and sources
- AND/OR filtering logic
- Declarative vs imperative filtering

**Real-world use case:** Event monitoring system with severity-based routing and source validation

---

### 🚀 Expert Track - Production Code

#### 05 - Password Redactor 🎉 **GRAND FINALE**
Production-ready password filtering you can STEAL!

```bash
uv run examples/08-context-provider/05_password_redactor.py
```

**⭐ SPECIAL: This is production-ready code you can copy into your projects!**

**Concepts:**
- Custom `ContextProvider` implementation
- Automatic password/secret detection
- Pattern-based redaction (passwords, API keys, tokens, credit cards)
- Configurable patterns and redaction style
- Audit logging

**Features:**
- ✅ Detects 8+ sensitive data types (passwords, API keys, JWT, credit cards, SSN, etc.)
- ✅ Configurable redaction text
- ✅ Custom pattern support
- ✅ Logging and audit trails
- ✅ Production-tested patterns
- ✅ Recursive dict/list redaction

**What it catches:**
```python
# Passwords
"password": "MySecretPass123"      → "password": "[REDACTED]"

# API Keys
sk-1234567890abcdef1234567890       → [REDACTED]
AKIAIOSFODNN7EXAMPLE                → [REDACTED]

# Tokens
Bearer eyJhbGciOiJIUzI1NiIs...      → [REDACTED]

# Credit Cards
4532-1234-5678-9010                 → [REDACTED]

# And more!
```

**Copy into your project:**
```python
# Just copy the PasswordRedactorProvider class!
from examples.context_provider import PasswordRedactorProvider

provider = PasswordRedactorProvider()
flock = Flock("openai/gpt-4o-mini", context_provider=provider)
```

**Real-world use case:** ANY production system handling user data, credentials, or sensitive information!

---

## 🎯 Quick Reference

### Run All Examples
```bash
# Beginner - Understand the basics
uv run examples/08-context-provider/01_basic_visibility.py
uv run examples/08-context-provider/02_global_provider.py

# Intermediate - Master configuration
uv run examples/08-context-provider/03_per_agent_provider.py
uv run examples/08-context-provider/04_custom_filtering.py

# Expert - Production patterns
uv run examples/08-context-provider/05_password_redactor.py  # ⭐ COPY THIS!
```

## 🔑 Key Concepts

### Context Provider Protocol

Every Context Provider implements this simple interface:

```python
from flock.context_provider import ContextProvider, ContextRequest

class MyProvider(ContextProvider):
    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        # 1. Query artifacts from store
        artifacts = await request.store.query_artifacts(...)

        # 2. CRITICAL: Filter by visibility (mandatory!)
        visible = [a for a in artifacts
                   if a.visibility.allows(request.agent_identity)]

        # 3. Apply your custom logic
        filtered = self.my_custom_filtering(visible)

        # 4. Return context
        return [{"type": a.type, "payload": a.payload, ...}
                for a in filtered]
```

### Provider Priority

When multiple providers are configured:

```
Per-Agent Provider  >  Global Provider  >  DefaultContextProvider
      (highest)            (medium)              (fallback)
```

### FilterConfig Options

```python
FilterConfig(
    tags={"urgent", "high"},           # Match any of these tags
    type_names={"Event", "Alert"},     # Match these types
    produced_by=["trusted-agent"],     # From these agents
    correlation_id="workflow-123"      # In this workflow
)
```

Criteria are combined with **AND** logic.
Multiple values within a criterion use **OR** logic.

## 💡 Common Patterns

### Pattern 1: Security Levels
```python
# Clearance-based filtering
top_secret_provider = FilteredContextProvider(
    FilterConfig(tags={"top-secret", "classified"})
)

classified_agent.context_provider = top_secret_provider
```

### Pattern 2: Role-Based Access
```python
# Different agents see different data
error_provider = FilteredContextProvider(FilterConfig(tags={"ERROR"}))
warn_provider = FilteredContextProvider(FilterConfig(tags={"WARN", "ERROR"}))
all_provider = FilteredContextProvider(FilterConfig(tags={"DEBUG", "INFO", "WARN", "ERROR"}))

junior_agent.context_provider = error_provider    # Errors only
senior_agent.context_provider = warn_provider     # Warnings + Errors
admin_agent.context_provider = all_provider       # Everything
```

### Pattern 3: Data Redaction
```python
# Redact sensitive data
from examples.context_provider import PasswordRedactorProvider

provider = PasswordRedactorProvider(
    redaction_text="[SECURITY_REDACTED]",
    custom_patterns={
        "internal_id": r"ID-\d{6}",
        "project_code": r"PROJ-[A-Z]{3}-\d{4}"
    }
)

flock = Flock("openai/gpt-4o-mini", context_provider=provider)
```

### Pattern 4: Composite Filtering
```python
# Combine multiple concerns
class AuditedRedactorProvider(ContextProvider):
    def __init__(self):
        self.redactor = PasswordRedactorProvider()
        self.filter = FilterConfig(tags={"audit-approved"})

    async def __call__(self, request):
        # First filter by approval
        filtered_request = request.with_filter(self.filter)

        # Then redact
        return await self.redactor(filtered_request)
```

## 🔍 Debugging Tips

### Enable Redaction Logging
```python
provider = PasswordRedactorProvider(log_redactions=True)
# Outputs: 🔒 PasswordRedactorProvider: Redacted 3 artifacts for agent 'my_agent'
```

### Test Your Filters
```python
# Print what each agent sees
async def debug_agent_context(flock, agent):
    all_artifacts = await flock.store.list()
    print(f"Agent {agent.name}:")

    # Simulate what provider returns
    request = ContextRequest(
        agent=agent,
        correlation_id=None,
        store=flock.store,
        agent_identity=agent.identity
    )

    context = await agent.context_provider(request)
    print(f"  Sees {len(context)} artifacts")
    for item in context:
        print(f"    - {item['type']}: {item['payload']}")
```

### Verify Security Boundaries
```python
# Ensure agents can't bypass filtering
try:
    # This should FAIL (no ctx.board access)
    artifacts = await ctx.board.list()
except AttributeError:
    print("✅ Security boundary enforced!")
```

## 📊 Performance Considerations

### Artifact Limits
```python
# Limit artifacts to reduce token usage
provider = FilteredContextProvider(
    FilterConfig(tags={"important"}),
    limit=50  # Only return 50 most recent
)
```

### Targeted Queries
```python
# Use specific filters instead of post-filtering
# GOOD: Query with filter
FilterConfig(type_names={"Event"}, tags={"high"})

# BAD: Query all, filter later
all_artifacts = await store.list()
filtered = [a for a in all_artifacts if a.type == "Event"]
```

## 🎯 Real-World Use Cases

### Healthcare: Patient Data Privacy
```python
# Only show patient data to authorized medical staff
provider = FilteredContextProvider(
    FilterConfig(tags={"authorized", "medical"})
)
doctor_agent.context_provider = provider
```

### Finance: Transaction Security
```python
# Redact credit cards and account numbers
provider = PasswordRedactorProvider(
    custom_patterns={
        "account_number": r"\b\d{8,12}\b",
        "routing_number": r"\b\d{9}\b"
    }
)
```

### DevOps: Log Filtering
```python
# Critical alerts for on-call engineers
critical_provider = FilteredContextProvider(
    FilterConfig(tags={"CRITICAL", "ALERT"})
)

# All logs for platform team
all_logs_provider = FilteredContextProvider(
    FilterConfig(tags={"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"})
)
```

### Compliance: Audit Trails
```python
class AuditProvider(ContextProvider):
    async def __call__(self, request):
        # Log every context fetch
        logger.info(f"Agent {request.agent.name} accessed context")

        # Apply standard filtering
        context = await DefaultContextProvider()(request)

        # Record audit event
        await audit_store.record(agent=request.agent.name, items=len(context))

        return context
```

## 🎁 Steal This Code!

The `PasswordRedactorProvider` in example 05 is **production-ready**!

### Installation
```bash
# Copy the class
cp examples/08-context-provider/05_password_redactor.py src/your_project/security/

# Or import directly
from examples.context_provider import PasswordRedactorProvider
```

### Quick Start
```python
# Basic usage
provider = PasswordRedactorProvider()
flock = Flock("openai/gpt-4o-mini", context_provider=provider)

# With customization
provider = PasswordRedactorProvider(
    redaction_text="[SECURITY_FILTERED]",
    redact_emails=True,
    custom_patterns={
        "employee_id": r"EMP-\d{6}",
        "bitcoin": r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b"
    },
    log_redactions=True
)
```

### Extend It
```python
class MyRedactorProvider(PasswordRedactorProvider):
    def __init__(self):
        super().__init__()
        # Add your company's patterns
        self.custom_patterns.update({
            "internal_ip": re.compile(r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"),
            "employee_email": re.compile(r"\b\w+@mycompany\.com\b")
        })
```

## 🎓 Next Steps

After completing these examples:

1. **Build Your Own Provider** - Implement domain-specific filtering
2. **Try Production Patterns** - Use PasswordRedactorProvider in real projects
3. **Explore Advanced Security** - Check `12_secret_agents.py` in `01-cli/`
4. **Master Visibility** - Read `docs/visibility.md` for deep dive

## 📚 Related Resources

- **00-patterns/** - Publishing pattern reference
- **01-cli/12_secret_agents.py** - Visibility in multi-agent systems
- **AGENTS.md** - Complete development guide
- **Security Research** - `.flock/flock-research/context-provider/`

## 🔐 Security Best Practices

1. **Always enforce visibility** - Never skip visibility filtering
2. **Test your patterns** - Ensure redaction works on real data
3. **Log security events** - Track what gets redacted
4. **Limit by default** - Start restrictive, loosen as needed
5. **Audit regularly** - Review what agents access

## 💬 Questions?

- **"Can agents bypass Context Providers?"** → No! It's a security boundary enforced by the orchestrator.
- **"What if I need complex filtering?"** → Implement a custom `ContextProvider` (see example 05).
- **"Performance impact?"** → Minimal - filtering happens before context serialization.
- **"Can I combine multiple providers?"** → Yes! Create a composite provider that chains logic.

---

**Happy filtering! 🦆**

*Remember: Security is not just about what you build—it's about what you prevent agents from accessing. Context Providers give you that control.*
