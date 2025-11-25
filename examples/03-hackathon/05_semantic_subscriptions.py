"""
Hackathon Track 05: Semantic Subscriptions

🎓 LEARNING OBJECTIVE:
Learn how to route artifacts based on MEANING, not just keywords.
Semantic matching uses AI embeddings to understand content similarity.

KEY CONCEPTS:
- Semantic matching (semantic_match parameter)
- AI-powered routing based on meaning
- Similarity thresholds
- Multi-criteria semantic filtering

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
# STEP 1: Define Types
# ============================================================================

@flock_type
class CustomerInquiry(BaseModel):
    """A customer inquiry that needs routing to the right team."""
    message: str = Field(description="The customer's question or issue")
    customer_id: str = Field(description="Customer identifier")


@flock_type
class TechnicalResponse(BaseModel):
    """Response from technical support team."""
    customer_id: str
    response: str = Field(description="Technical support response")
    troubleshooting_steps: list[str]


@flock_type
class BillingResponse(BaseModel):
    """Response from billing team."""
    customer_id: str
    response: str = Field(description="Billing support response")
    refund_issued: bool = False


@flock_type
class SecurityResponse(BaseModel):
    """Response from security team."""
    customer_id: str
    response: str = Field(description="Security team response")
    threat_level: str
    action_taken: str


# ============================================================================
# STEP 2: Create the Orchestrator
# ============================================================================

flock = Flock()


# ============================================================================
# STEP 3: Define Agents with Semantic Matching
# ============================================================================
# Semantic matching routes artifacts based on MEANING, not keywords.
#
# Example: "SQL injection vulnerability" matches "security breach"
#          even though they share no keywords!
#
# Syntax: .consumes(Type, semantic_match="query text")
#         .consumes(Type, semantic_match="query", semantic_threshold=0.6)
#
# The semantic_match is a query that describes what you're looking for.
# The system uses embeddings to find semantically similar content.
# ============================================================================

# Technical Support - Matches technical issues
tech_support = (
    flock.agent("tech_support")
    .description("Handles technical problems and troubleshooting.")
    .consumes(
        CustomerInquiry,
        semantic_match="technical issue error bug problem device login"
    )
    .publishes(TechnicalResponse)
)

# Billing Support - Matches payment and billing issues
billing_support = (
    flock.agent("billing_support")
    .description("Handles payment, billing, and refund requests.")
    .consumes(
        CustomerInquiry,
        semantic_match="payment charge refund billing subscription cost money"
    )
    .publishes(BillingResponse)
)

# Security Team - Matches security-related issues
security_team = (
    flock.agent("security_team")
    .description("Handles security vulnerabilities and threats.")
    .consumes(
        CustomerInquiry,
        semantic_match="security vulnerability exploit breach attack unauthorized access"
    )
    .publishes(SecurityResponse)
)

# General Support - Catches everything else (no semantic filter)
general_support = (
    flock.agent("general_support")
    .description("Handles general inquiries and questions.")
    .consumes(CustomerInquiry)  # No semantic_match = matches everything
    .publishes(TechnicalResponse)
)


# ============================================================================
# STEP 4: Run with Various Inquiries
# ============================================================================

async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("=" * 70)
    print("🧠 SEMANTIC SUBSCRIPTIONS EXAMPLE - Intelligent Ticket Routing")
    print("=" * 70)
    print()
    
    # Create inquiries that test semantic matching
    inquiries = [
        CustomerInquiry(
            customer_id="C001",
            message="I found a SQL injection vulnerability in the login form"
        ),
        CustomerInquiry(
            customer_id="C002",
            message="I was charged twice for my monthly subscription"
        ),
        CustomerInquiry(
            customer_id="C003",
            message="The app crashes when I try to export my data"
        ),
        CustomerInquiry(
            customer_id="C004",
            message="How do I change my profile picture?"
        ),
        CustomerInquiry(
            customer_id="C005",
            message="Someone accessed my account without permission"
        ),
    ]
    
    print("📝 Customer Inquiries:")
    for inquiry in inquiries:
        print(f"   [{inquiry.customer_id}] {inquiry.message[:60]}...")
    print()
    print("⏳ Routing inquiries using semantic matching...")
    print("   (Matching by MEANING, not keywords!)")
    print()
    
    # Publish all inquiries
    await flock.publish_many(inquiries)
    
    # Run until completion
    await flock.run_until_idle()
    
    # Check routing results
    tech_responses = await flock.store.get_by_type(TechnicalResponse)
    billing_responses = await flock.store.get_by_type(BillingResponse)
    security_responses = await flock.store.get_by_type(SecurityResponse)
    
    print("=" * 70)
    print("📊 SEMANTIC ROUTING RESULTS")
    print("=" * 70)
    
    print(f"\n🔧 Technical Support: {len(tech_responses)} inquiries")
    for response in tech_responses:
        print(f"   • Customer {response.customer_id}")
        print(f"     Steps: {len(response.troubleshooting_steps)}")
    
    print(f"\n💳 Billing Support: {len(billing_responses)} inquiries")
    for response in billing_responses:
        print(f"   • Customer {response.customer_id}")
        print(f"     Refund: {'Yes' if response.refund_issued else 'No'}")
    
    print(f"\n🔒 Security Team: {len(security_responses)} inquiries")
    for response in security_responses:
        print(f"   • Customer {response.customer_id}")
        print(f"     Threat Level: {response.threat_level}")
    
    print()
    print("=" * 70)
    print("💡 Key Insights:")
    print("   - 'SQL injection' → Security (semantic match, not keyword!)")
    print("   - 'charged twice' → Billing (understands payment context)")
    print("   - 'app crashes' → Technical (understands technical problem)")
    print("   - 'change profile' → General (no semantic match)")
    print("   - 'unauthorized access' → Security (understands security threat)")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8344 to see semantic routing in action!")
    print()
    print("💡 Try sending inquiries and watch them route by meaning!")
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# 🎓 NOW IT'S YOUR TURN!
# ============================================================================
# 
# EXPERIMENT 1: Adjust Semantic Threshold
# ----------------------------------------
# Make matching stricter or looser:
#   tech_support = (
#       flock.agent("tech_support")
#       .consumes(
#           CustomerInquiry,
#           semantic_match="technical issue",
#           semantic_threshold=0.7  # Stricter (default is ~0.4)
#       )
#       .publishes(TechnicalResponse)
#   )
#
# What happens with threshold=0.9? What about threshold=0.2?
#
#
# EXPERIMENT 2: Multiple Semantic Queries (AND Logic)
# -----------------------------------------------------
# Require MULTIPLE semantic matches:
#   critical_security = (
#       flock.agent("critical_security")
#       .consumes(
#           CustomerInquiry,
#           semantic_match=[
#               "security vulnerability",
#               "critical threat",
#               "immediate action"
#           ]
#       )
#       .publishes(SecurityResponse)
#   )
#
# All three queries must match! How many inquiries pass?
#
#
# EXPERIMENT 3: Combine Semantic + Conditional
# ---------------------------------------------
# Use BOTH semantic matching AND where clauses:
#   urgent_tech = (
#       flock.agent("urgent_tech")
#       .consumes(
#           CustomerInquiry,
#           semantic_match="technical issue",
#           where=lambda i: "urgent" in i.message.lower() or "critical" in i.message.lower()
#       )
#       .publishes(TechnicalResponse)
#   )
#
# This agent only processes urgent technical issues!
#
#
# EXPERIMENT 4: Domain-Specific Routing
# --------------------------------------
# Create specialized agents for different domains:
#   @flock_type
#   class SupportTicket(BaseModel):
#       title: str
#       description: str
#       category: str
#
#   api_support = (
#       flock.agent("api_support")
#       .consumes(SupportTicket, semantic_match="API endpoint integration authentication")
#       .publishes(TechnicalResponse)
#   )
#
#   database_support = (
#       flock.agent("database_support")
#       .consumes(SupportTicket, semantic_match="database query performance connection")
#       .publishes(TechnicalResponse)
#   )
#
#   ui_support = (
#       flock.agent("ui_support")
#       .consumes(SupportTicket, semantic_match="user interface design layout button")
#       .publishes(TechnicalResponse)
#   )
#
# Create tickets and see them route to the right specialist!
#
#
# EXPERIMENT 5: Semantic vs Keyword Comparison
# ---------------------------------------------
# Create two agents - one semantic, one keyword-based:
#   semantic_agent = (
#       flock.agent("semantic_agent")
#       .consumes(CustomerInquiry, semantic_match="payment issue")
#       .publishes(BillingResponse)
#   )
#
#   keyword_agent = (
#       flock.agent("keyword_agent")
#       .consumes(CustomerInquiry, where=lambda i: "payment" in i.message.lower())
#       .publishes(BillingResponse)
#   )
#
# Test with: "I was billed incorrectly" - which agent catches it?
# Test with: "My payment failed" - which agent catches it?
# What's the difference?
#
#
# CHALLENGE: Build an Intelligent Content Router
# ------------------------------------------------
# Create a content routing system that:
#   1. Takes blog posts/articles
#   2. Routes to specialized editors based on topic:
#      - Tech editor (semantic: "programming code software development")
#      - Business editor (semantic: "strategy marketing revenue growth")
#      - Design editor (semantic: "design UI UX visual aesthetics")
#   3. Each editor adds domain-specific improvements
#   4. Routes back to general editor for final review
#
# How do you prevent double-processing? Use tags or visibility?
#
# ============================================================================

