# 🧠 Semantic Routing: Smart Artifact Matching

**Difficulty:** ⭐⭐ Intermediate | **Time:** 20 minutes

Learn how to route artifacts to agents based on **meaning** instead of just types, using semantic subscriptions powered by local AI embeddings.

## What You'll Build

By the end of this tutorial, you'll have a smart support ticket routing system that automatically directs tickets to the right team based on semantic understanding:

- 🔒 **Security Team** - Handles vulnerabilities and exploits
- 💰 **Billing Team** - Manages payment and refund issues
- 🛠️ **Tech Support** - Catches general technical problems

All without writing complex keyword matching logic!

## Prerequisites

- Completed [Your First Agent](your-first-agent.md) tutorial
- Installed `flock-core[semantic]` extra:
  ```bash
  uv add flock-core[semantic]
  # or
  pip install flock-core[semantic]
  ```

This installs `sentence-transformers` with the `all-MiniLM-L6-v2` model (~90MB) for local semantic matching.

## Step 1: Define Your Data Models

First, let's define the support ticket and response types:

```python
from pydantic import BaseModel
from flock import Flock
from flock.registry import flock_type

@flock_type
class SupportTicket(BaseModel):
    """A customer support request."""
    message: str
    category: str | None = None

@flock_type
class SecurityAlert(BaseModel):
    """Alert for security-related tickets."""
    ticket_message: str
    severity: str

@flock_type
class BillingResponse(BaseModel):
    """Response for billing issues."""
    ticket_message: str
    action: str

@flock_type
class TechnicalResponse(BaseModel):
    """Response for technical issues."""
    ticket_message: str
    solution: str
```

**💡 Key Insight:** We're using simple data models - the intelligence comes from semantic routing, not complex schemas!

## Step 2: Create Simple Response Engines

Each team needs a basic engine to process tickets:

```python
from flock.components.agent import EngineComponent
from flock.utils.runtime import EvalInputs, EvalResult

class SecurityEngine(EngineComponent):
    """Handles security-related tickets with high priority."""

    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        ticket = SupportTicket(**inputs.artifacts[0].payload)

        alert = SecurityAlert(
            ticket_message=ticket.message,
            severity="HIGH"
        )

        return EvalResult(
            artifacts=[alert],
            state={"team": "security", "escalated": True}
        )

class BillingEngine(EngineComponent):
    """Handles billing and payment issues."""

    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        ticket = SupportTicket(**inputs.artifacts[0].payload)

        response = BillingResponse(
            ticket_message=ticket.message,
            action="REVIEW_CHARGES"
        )

        return EvalResult(
            artifacts=[response],
            state={"team": "billing"}
        )

class TechSupportEngine(EngineComponent):
    """Handles general technical issues."""

    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        ticket = SupportTicket(**inputs.artifacts[0].payload)

        response = TechnicalResponse(
            ticket_message=ticket.message,
            solution="TROUBLESHOOT"
        )

        return EvalResult(
            artifacts=[response],
            state={"team": "support"}
        )
```

**💡 Key Insight:** The engines are simple - they just process tickets. The semantic routing handles all the complexity!

## Step 3: Set Up Semantic Routing

Here's where the magic happens! Notice the `semantic_match` parameter:

```python
flock = Flock()

# Security Team - Matches security-related content semantically
security_team = (
    flock.agent("security_team")
    .consumes(
        SupportTicket,
        semantic_match="security vulnerability exploit breach"
    )
    .publishes(SecurityAlert)
    .with_engines(SecurityEngine())
)

# Billing Team - Matches payment and billing content semantically
billing_team = (
    flock.agent("billing_team")
    .consumes(
        SupportTicket,
        semantic_match="payment charge refund billing subscription"
    )
    .publishes(BillingResponse)
    .with_engines(BillingEngine())
)

# Tech Support - Matches general technical issues semantically
tech_support = (
    flock.agent("tech_support")
    .consumes(
        SupportTicket,
        semantic_match="technical issue error bug problem"
    )
    .publishes(TechnicalResponse)
    .with_engines(TechSupportEngine())
)
```

**💡 Key Insight:** The `semantic_match` parameter uses AI embeddings to understand meaning. A ticket saying "SQL injection vulnerability" will match "security vulnerability exploit" even though they share no exact words!

## Step 4: Test Your Smart Router

Let's publish some tickets and watch the semantic routing work:

```python
async def main():
    # Security ticket - will route to security team
    security_ticket = SupportTicket(
        message="Critical SQL injection vulnerability in login endpoint",
        category="bug"
    )
    await flock.publish(security_ticket)

    # Billing ticket - will route to billing team
    billing_ticket = SupportTicket(
        message="Customer charged twice for monthly subscription",
        category="billing"
    )
    await flock.publish(billing_ticket)

    # Technical ticket - will route to tech support
    tech_ticket = SupportTicket(
        message="Application crashes when uploading large files",
        category="technical"
    )
    await flock.publish(tech_ticket)

    # Process all tickets
    await flock.run_until_idle()

    print("✅ All tickets routed to appropriate teams!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**💡 Key Insight:** Each ticket automatically routes to the right team based on semantic similarity, not keyword matching!

## Step 5: Understanding the Matching Process

When a ticket is published, here's what happens:

1. **Embedding Generation**: The ticket message is converted to a 384-dimensional vector using the local AI model
2. **Similarity Computation**: The vector is compared to each agent's `semantic_match` query using cosine similarity
3. **Threshold Check**: If similarity ≥ 0.4 (default threshold), the agent processes it
4. **Multiple Matches**: A ticket can match multiple agents - each will process it independently

```
Ticket: "SQL injection vulnerability"
                ↓
    [Embedding: 384-dim vector]
                ↓
    ┌───────────┴───────────┐
    ↓                       ↓
Security Query         Billing Query
"security..."          "payment..."
similarity: 0.87       similarity: 0.12
✅ Match!              ❌ No match
```

## Step 6: Tuning the Threshold

The default threshold (0.4) works well for moderate matching. Adjust it for different needs:

```python
# Strict matching - only very similar content (threshold=0.7)
security_team_strict = (
    flock.agent("security_strict")
    .consumes(
        SupportTicket,
        semantic_match="security vulnerability",
        semantic_threshold=0.7  # Must be VERY similar
    )
    .publishes(SecurityAlert)
    .with_engines(SecurityEngine())
)

# Loose matching - broadly related content (threshold=0.25)
support_team_loose = (
    flock.agent("support_loose")
    .consumes(
        SupportTicket,
        semantic_match="technical",
        semantic_threshold=0.25  # More permissive
    )
    .publishes(TechnicalResponse)
    .with_engines(TechSupportEngine())
)
```

**Threshold Guidelines:**
- **0.7-0.9**: Very strict - nearly identical concepts only
- **0.4-0.6**: Moderate - related concepts (good default)
- **0.2-0.3**: Loose - broadly related topics

**💡 Key Insight:** Start with the default threshold (0.4) and adjust based on how many false positives/negatives you see!

## Complete Example

Here's the full working code:

```python
from pydantic import BaseModel
from flock import Flock
from flock.registry import flock_type
from flock.components.agent import EngineComponent
from flock.utils.runtime import EvalInputs, EvalResult

# Data models
@flock_type
class SupportTicket(BaseModel):
    message: str
    category: str | None = None

@flock_type
class SecurityAlert(BaseModel):
    ticket_message: str
    severity: str

@flock_type
class BillingResponse(BaseModel):
    ticket_message: str
    action: str

@flock_type
class TechnicalResponse(BaseModel):
    ticket_message: str
    solution: str

# Engines
class SecurityEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        ticket = SupportTicket(**inputs.artifacts[0].payload)
        alert = SecurityAlert(ticket_message=ticket.message, severity="HIGH")
        return EvalResult(artifacts=[alert], state={"team": "security"})

class BillingEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        ticket = SupportTicket(**inputs.artifacts[0].payload)
        response = BillingResponse(ticket_message=ticket.message, action="REVIEW_CHARGES")
        return EvalResult(artifacts=[response], state={"team": "billing"})

class TechSupportEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        ticket = SupportTicket(**inputs.artifacts[0].payload)
        response = TechnicalResponse(ticket_message=ticket.message, solution="TROUBLESHOOT")
        return EvalResult(artifacts=[response], state={"team": "support"})

# Set up flock with semantic routing
flock = Flock()

security_team = (
    flock.agent("security_team")
    .consumes(SupportTicket, semantic_match="security vulnerability exploit breach")
    .publishes(SecurityAlert)
    .with_engines(SecurityEngine())
)

billing_team = (
    flock.agent("billing_team")
    .consumes(SupportTicket, semantic_match="payment charge refund billing subscription")
    .publishes(BillingResponse)
    .with_engines(BillingEngine())
)

tech_support = (
    flock.agent("tech_support")
    .consumes(SupportTicket, semantic_match="technical issue error bug problem")
    .publishes(TechnicalResponse)
    .with_engines(TechSupportEngine())
)

# Test the routing
async def main():
    tickets = [
        SupportTicket(message="Critical SQL injection in login", category="bug"),
        SupportTicket(message="Charged twice for subscription", category="billing"),
        SupportTicket(message="App crashes on file upload", category="technical"),
    ]

    for ticket in tickets:
        await flock.publish(ticket)

    await flock.run_until_idle()
    print("✅ All tickets routed successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## What You Learned

✅ How to use `semantic_match` to route based on meaning
✅ How semantic similarity works with AI embeddings
✅ How to tune thresholds for precision/recall
✅ How to build intelligent routing without keyword logic

## Next Steps

- 📖 Read the [Semantic Subscriptions Guide](../guides/semantic-subscriptions.md) for advanced patterns
- 🔍 Try [SemanticContextProvider](../guides/semantic-subscriptions.md#semantic-context-provider) for historical context retrieval
- 🎯 Explore [multi-criteria filtering](../guides/semantic-subscriptions.md#multiple-text-predicates) with AND logic
- ⚡ Learn about [performance optimization](../guides/semantic-subscriptions.md#performance-characteristics)

## Common Questions

**Q: Does this require an API key or internet connection?**
A: No! The AI model runs locally on your machine using `sentence-transformers`.

**Q: How fast is semantic matching?**
A: ~15ms per embedding (CPU), with 10,000-entry LRU cache for instant lookups on repeated text.

**Q: Can I match specific fields instead of the whole payload?**
A: Yes! Use the dict format: `semantic_match={"query": "...", "field": "message"}`

**Q: What happens if multiple agents match?**
A: All matching agents process the artifact - that's the power of pub/sub!

**Q: Can I combine semantic matching with type and predicate filters?**
A: Absolutely! `semantic_match` works alongside `where` predicates and type filters.

---

**Ready to level up?** Check out the [Semantic Subscriptions Guide](../guides/semantic-subscriptions.md) for advanced patterns like context retrieval, multi-criteria filtering, and performance tuning! 🚀
