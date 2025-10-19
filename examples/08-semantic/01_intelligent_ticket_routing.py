"""
Semantic Subscriptions: Intelligent Ticket Routing

This example demonstrates how semantic text predicates enable intelligent routing
of support tickets to specialized teams based on MEANING, not keywords.

🎯 Key Concepts:
- Semantic text matching (semantic_match="query")
- Multi-agent routing patterns
- Automatic team assignment based on content similarity

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes

📚 Requires: uv add flock-core[semantic]
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# 🎛️  TYPE REGISTRATION: Support ticket types
# ============================================================================
@flock_type
class SupportTicket(BaseModel):
    """A customer support ticket that needs routing."""

    message: str = Field(description="The customer's issue or question")
    customer_id: str = Field(description="Customer identifier")


@flock_type
class SecurityAlert(BaseModel):
    """High-priority security team alert."""

    ticket_id: str
    threat_level: str
    action_taken: str
    details: str


@flock_type
class BillingResponse(BaseModel):
    """Response from billing team."""

    ticket_id: str
    resolution: str
    refund_issued: bool = False


@flock_type
class TechnicalResponse(BaseModel):
    """Response from technical support."""

    ticket_id: str
    solution: str
    escalated: bool = False


# ============================================================================
# 🎛️  SETUP: Create specialized teams with semantic routing
# ============================================================================
# Each agent has a semantic filter (semantic_match="...") that matches based on MEANING
# Not just keywords! "SQL injection" will match "security vulnerability"
# ============================================================================
flock = Flock()

# Security Team - Handles security-related issues
# Matches: "SQL injection", "XSS attack", "data breach", "unauthorized access"
security_team = (
    flock.agent("security_team")
    .consumes(SupportTicket, semantic_match="security vulnerability exploit breach")
    .publishes(SecurityAlert)
)

# Billing Team - Handles payment and billing issues
# Matches: "double charge", "refund request", "payment failed", "subscription issue"
billing_team = (
    flock.agent("billing_team")
    .consumes(
        SupportTicket, semantic_match="payment charge refund billing subscription"
    )
    .publishes(BillingResponse)
)

# Technical Support - General technical issues
# Matches: "can't login", "error message", "not working", "broken feature"
tech_support = (
    flock.agent("tech_support")
    .consumes(SupportTicket, semantic_match="technical issue error bug problem device")
    .publishes(TechnicalResponse)
)

# General Support - Catch-all (no semantic filter)
# Handles anything not caught by specialized teams
general_support = (
    flock.agent("general_support")
    .consumes(SupportTicket)  # No text filter = matches everything
    .publishes(TechnicalResponse)
)


# ============================================================================
# 🎛️  RUN: Publish tickets and watch semantic routing in action
# ============================================================================
async def main_cli():
    """CLI mode: Demonstrate intelligent ticket routing"""
    print("\n🎯 Semantic Ticket Routing Demo\n")
    print("=" * 60)

    # Test Case 1: Security Issue
    print("\n📋 Ticket 1: Security Issue")
    security_ticket = SupportTicket(
        message="Critical SQL injection vulnerability found in login form",
        customer_id="SEC-001",
    )
    print(f"   Message: {security_ticket.message}")
    print("   Expected Route: → Security Team")

    await flock.publish(security_ticket)
    await flock.run_until_idle(wait_for_input=True)

    # Test Case 2: Billing Issue
    print("\n📋 Ticket 2: Billing Issue")
    billing_ticket = SupportTicket(
        message="I was charged twice for my monthly subscription",
        customer_id="BILL-002",
    )
    print(f"   Message: {billing_ticket.message}")
    print("   Expected Route: → Billing Team")

    await flock.publish(billing_ticket)
    await flock.run_until_idle(wait_for_input=True)

    # Test Case 3: Technical Issue
    print("\n📋 Ticket 3: Technical Problem")
    tech_ticket = SupportTicket(
        message="Application crashes when I try to export data",
        customer_id="TECH-003",
    )
    print(f"   Message: {tech_ticket.message}")
    print("   Expected Route: → Tech Support")

    await flock.publish(tech_ticket)
    await flock.run_until_idle(wait_for_input=True)

    # Test Case 4: General Question
    print("\n📋 Ticket 4: General Inquiry")
    general_ticket = SupportTicket(
        message="How do I change my profile picture?",
        customer_id="GEN-004",
    )
    print(f"   Message: {general_ticket.message}")
    print("   Expected Route: → General Support")

    await flock.publish(general_ticket)
    await flock.run_until_idle()

    print("\n" + "=" * 60)
    print("✅ Semantic routing complete! Check results above.")
    print("\n💡 Notice how tickets route based on MEANING, not keywords!")
    print("   - 'SQL injection' → Security (no keyword 'security' needed)")
    print("   - 'charged twice' → Billing (semantic match to 'payment')")
    print("   - 'crashes' → Tech Support (semantic match to 'technical issue')")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("\n🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8000 to see semantic routing in action!")
    print("\n💡 Try sending tickets with different content and watch them")
    print("   automatically route to the right team based on meaning!\n")

    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
