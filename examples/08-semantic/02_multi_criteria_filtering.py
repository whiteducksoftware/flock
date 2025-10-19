"""
Semantic Subscriptions: Multi-Criteria Semantic Filtering

This example demonstrates advanced semantic filtering with:
- Multiple text predicates (AND logic)
- Combination of semantic + structural filters
- Field-specific semantic matching
- Custom similarity thresholds

🎯 Key Concepts:
- Multiple text predicates require ALL to match
- Combining semantic filters with where clauses
- Field extraction for targeted semantic matching
- Adjustable similarity thresholds

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
# 🎛️  TYPE REGISTRATION: Document and alert types
# ============================================================================
@flock_type
class Document(BaseModel):
    """A compliance document."""

    title: str = Field(description="Document title")
    abstract: str = Field(description="Document summary")
    content: str = Field(description="Full document content")
    status: str = Field(description="draft, review, or published")
    department: str = Field(description="Originating department")


@flock_type
class ComplianceAlert(BaseModel):
    """Alert for compliance-related documents."""

    document_title: str
    alert_type: str
    priority: str


@flock_type
class SecurityReview(BaseModel):
    """Security review request."""

    document_title: str
    risk_level: str


@flock_type
class AuditReport(BaseModel):
    """Audit trail report."""

    document_title: str
    findings: list[str]


# ============================================================================
# 🎛️  SETUP: Create agents with advanced semantic filters
# ============================================================================
flock = Flock()

# Agent 1: STRICT security + compliance filter
# Requires: BOTH "security" AND "compliance" topics + published status
# This catches only documents about security measures AND regulatory compliance
security_compliance = (
    flock.agent("security_compliance_officer")
    .consumes(
        Document,
        semantic_match=[
            "security measures protection",
            "regulatory compliance standards",
        ],
        where=lambda d: d.status == "published",
    )
    .publishes(ComplianceAlert)
)

# Agent 2: High-threshold privacy filter with field extraction
# Only matches "abstract" field, requires high similarity (0.7)
# This is VERY selective - only strongly privacy-related abstracts
privacy_officer = (
    flock.agent("privacy_officer")
    .consumes(
        Document,
        semantic_match={
            "query": "privacy data protection GDPR",
            "threshold": 0.7,
            "field": "abstract",
        },
        where=lambda d: d.status == "published",
    )
    .publishes(SecurityReview)
)

# Agent 3: Broad audit filter (low threshold)
# Lower threshold (0.3) catches loosely related audit content
audit_trail = (
    flock.agent("audit_trail")
    .consumes(
        Document,
        semantic_match={"query": "audit review inspection", "threshold": 0.3},
        where=lambda d: d.department in ["legal", "compliance", "finance"],
    )
    .publishes(AuditReport)
)

# Agent 4: Catch-all for published docs (no semantic filter)
general_archiver = (
    flock.agent("general_archiver")
    .consumes(Document, where=lambda d: d.status == "published")
    .publishes(AuditReport)
)


# ============================================================================
# 🎛️  RUN: Test multi-criteria filtering
# ============================================================================
async def main_cli():
    """CLI mode: Demonstrate advanced semantic filtering"""
    print("\n🎯 Multi-Criteria Semantic Filtering Demo\n")
    print("=" * 70)

    test_documents = [
        # Document 1: Should match security_compliance (both topics + published)
        (
            Document(
                title="Cybersecurity Compliance Framework",
                abstract="A comprehensive guide to security measures and regulatory compliance",
                content="This document outlines security protocols that meet compliance standards...",
                status="published",
                department="security",
            ),
            "Expected: Security+Compliance Officer (both topics match)",
        ),
        # Document 2: Should match privacy_officer (high similarity in abstract)
        (
            Document(
                title="GDPR Data Protection Guidelines",
                abstract="Complete privacy and data protection procedures for GDPR compliance",
                content="Detailed procedures for handling personal data...",
                status="published",
                department="legal",
            ),
            "Expected: Privacy Officer (high similarity in abstract field)",
        ),
        # Document 3: Should match audit_trail (audit-related, low threshold)
        (
            Document(
                title="Quarterly Financial Inspection Report",
                abstract="Results from Q3 financial audit",
                content="Audit findings and recommendations...",
                status="published",
                department="finance",
            ),
            "Expected: Audit Trail (loose semantic match with low threshold)",
        ),
        # Document 4: Draft - only general_archiver (doesn't match 'published' filters)
        (
            Document(
                title="Draft Security Policy",
                abstract="Preliminary security policy draft",
                content="Draft content...",
                status="draft",
                department="security",
            ),
            "Expected: None (draft status excluded by filters)",
        ),
        # Document 5: Security only (not compliance) - won't match security_compliance
        (
            Document(
                title="Network Security Procedures",
                abstract="Internal network security guidelines",
                content="How to secure our network infrastructure...",
                status="published",
                department="IT",
            ),
            "Expected: General Archiver only (security but no compliance topic)",
        ),
    ]

    for idx, (doc, expected) in enumerate(test_documents, 1):
        print(f"\n📄 Document {idx}: {doc.title}")
        print(f"   Status: {doc.status}")
        print(f"   Department: {doc.department}")
        print(f"   Abstract: {doc.abstract[:60]}...")
        print(f"   {expected}")
        print("   Processing...")

        await flock.publish(doc)
        await flock.run_until_idle()

    print("\n" + "=" * 70)
    print("✅ Multi-criteria filtering complete!")
    print("\n💡 Key Takeaways:")
    print("   ✓ Multiple text predicates = ALL must match (AND logic)")
    print("   ✓ semantic_match=['topic1', 'topic2'] requires BOTH topics present")
    print("   ✓ threshold controls strictness (0.7 = strict, 0.3 = loose)")
    print("   ✓ field='abstract' matches only that field, not full content")
    print("   ✓ Combine semantic + structural (where clause) for precision")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("\n🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8000 to explore multi-criteria filtering!")
    print("\n💡 Try creating documents with different:")
    print("   - Topic combinations (security + compliance)")
    print("   - Status values (draft vs published)")
    print("   - Abstract content (privacy-focused)")
    print("\n   Watch how agents with different criteria respond!\n")

    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
