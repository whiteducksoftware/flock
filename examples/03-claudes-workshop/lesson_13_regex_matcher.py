"""
Lesson 13: The Regex Matcher

CONCEPTS: Custom Engines
- Replace LLM calls with deterministic logic
- Build specialized processing engines
- Zero-cost pattern matching
- Domain-specific rule engines
- Hybrid LLM + custom engine architectures

SCENARIO:
You're building a content moderation system. For simple pattern matching
(profanity, spam patterns, email extraction), you don't need an LLM—
that's expensive and slow! Custom engines let you implement deterministic
logic while still using the same agent infrastructure.

CUSTOM ENGINES provide:
- Non-LLM processing within agent framework
- Zero LLM cost for deterministic tasks
- Faster execution than API calls
- Full control over logic
- Seamless integration with LLM agents

This example shows when and how to skip the LLM.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import EngineComponent
from flock.runtime import EvalInputs, EvalResult


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================


@flock_type(name="UserMessage")
class UserMessage(BaseModel):
    message_id: str
    author: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


@flock_type(name="ModerationResult")
class ModerationResult(BaseModel):
    message_id: str
    status: str  # "approved", "flagged", "blocked"
    violations: list[str]
    extracted_emails: list[str]
    extracted_urls: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


@flock_type(name="EscalationCase")
class EscalationCase(BaseModel):
    message_id: str
    reason: str
    original_content: str
    recommendation: str


# ============================================================================
# CUSTOM ENGINE - Pattern-Based Moderation
# ============================================================================


class RegexModerationEngine(EngineComponent):
    """
    Deterministic content moderation using regex patterns.

    This engine demonstrates:
    - Zero-LLM-cost processing
    - Fast pattern matching
    - Custom business logic
    - Hybrid decision making (rules + LLM escalation)
    """

    # Profanity patterns (simple examples - real systems use comprehensive lists)
    PROFANITY_PATTERNS = [
        r"\b(badword1|badword2|offensive)\b",
        r"\b(spam|scam)\b",
    ]

    # Spam indicators
    SPAM_PATTERNS = [
        r"(?i)click here",
        r"(?i)buy now",
        r"(?i)limited time offer",
        r"(?i)act now",
        r"\$\$\$+",
    ]

    # Email extraction
    EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    # URL extraction
    URL_PATTERN = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        """
        Process user messages with deterministic rules.

        No LLM call needed - pure Python logic!
        """
        message = inputs.first_as(UserMessage)
        if not message:
            return EvalResult.empty()

        content = message.content
        violations = []
        status = "approved"

        print(f"\n🔍 Scanning message {message.message_id}")
        print(f"   From: {message.author}")
        print(f"   Content: {content[:60]}...")

        # Check profanity
        for pattern in self.PROFANITY_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"profanity_detected: {pattern}")
                print(f"   ⚠️  Profanity pattern matched: {pattern}")

        # Check spam
        spam_score = 0
        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                spam_score += 1
                violations.append(f"spam_indicator: {pattern}")
                print(f"   ⚠️  Spam indicator: {pattern}")

        # Extract emails (could indicate spam/phishing)
        emails = re.findall(self.EMAIL_PATTERN, content)
        if emails:
            print(f"   📧 Email(s) detected: {', '.join(emails)}")

        # Extract URLs (check for suspicious links)
        urls = re.findall(self.URL_PATTERN, content)
        if urls:
            print(f"   🔗 URL(s) detected: {len(urls)} link(s)")

        # Determine status
        if violations:
            if spam_score >= 2 or any("profanity" in v for v in violations):
                status = "blocked"
                print(f"   🚫 BLOCKED - Automatic rejection")
            else:
                status = "flagged"
                print(f"   🚩 FLAGGED - Needs review")
        else:
            print(f"   ✅ APPROVED - No violations detected")

        # Confidence is deterministic for rule-based systems
        confidence = 1.0 if status == "blocked" else 0.95 if status == "flagged" else 1.0

        result = ModerationResult(
            message_id=message.message_id,
            status=status,
            violations=violations,
            extracted_emails=emails,
            extracted_urls=urls,
            confidence=confidence,
        )

        print(f"   Confidence: {confidence:.2%}")

        return EvalResult.from_object(result, agent=agent)


# ============================================================================
# MAIN DEMO
# ============================================================================


async def main() -> None:
    flock = Flock()

    # Regex-based moderator (NO LLM NEEDED!)
    (
        flock.agent("pattern_moderator")
        .description("Fast pattern-based content moderation")
        .consumes(UserMessage)
        .publishes(ModerationResult)
        .with_engines(RegexModerationEngine())  # Custom engine!
    )

    # LLM-based escalation handler (ONLY for flagged content)
    (
        flock.agent("human_escalation")
        .description("Reviews flagged content that needs human judgment")
        .consumes(ModerationResult, where=lambda r: r.status == "flagged")
        .publishes(EscalationCase)
        .system_prompt(
            """You are a senior content moderator. Review flagged messages and provide:
- Detailed reasoning for why it was flagged
- Recommendation: approve, block, or escalate to legal
- Explanation for the human review team

Be thorough but fair in your assessment."""
        )
    )

    print("🛡️  Hybrid Content Moderation System")
    print("=" * 70)
    print("Architecture: Regex (fast) → LLM (only when needed)")
    print("=" * 70)

    # Test messages
    test_messages = [
        UserMessage(
            message_id="msg-001",
            author="user_alice",
            content="Hey everyone! Check out my latest blog post about Python.",
        ),
        UserMessage(
            message_id="msg-002",
            author="spammer_bob",
            content="CLICK HERE for limited time offer! Buy now! $$$$ Act now!",
        ),
        UserMessage(
            message_id="msg-003",
            author="user_charlie",
            content="Contact me at charlie@example.com for collaboration opportunities.",
        ),
        UserMessage(
            message_id="msg-004",
            author="suspicious_dave",
            content="This might be spam but I'm not sure. Click here maybe?",
        ),
        UserMessage(
            message_id="msg-005",
            author="user_eve",
            content="Great discussion! Looking forward to the next meetup.",
        ),
    ]

    # Process all messages
    for msg in test_messages:
        await flock.publish(msg)

    await flock.run_until_idle()

    # Summary report
    print("\n" + "=" * 70)
    print("📊 Moderation Summary")
    print("=" * 70)

    all_artifacts = await flock.store.list()
    moderation_results = [a for a in all_artifacts if a.type_name == "ModerationResult"]
    escalations = [a for a in all_artifacts if a.type_name == "EscalationCase"]

    approved = sum(1 for a in moderation_results if a.payload.get("status") == "approved")
    flagged = sum(1 for a in moderation_results if a.payload.get("status") == "flagged")
    blocked = sum(1 for a in moderation_results if a.payload.get("status") == "blocked")

    print(f"\nTotal messages processed: {len(moderation_results)}")
    print(f"✅ Approved: {approved}")
    print(f"🚩 Flagged for review: {flagged}")
    print(f"🚫 Blocked: {blocked}")
    print(f"📋 Escalated to humans: {len(escalations)}")

    print("\n" + "=" * 70)
    print("🎓 What Just Happened?")
    print("=" * 70)
    print("The RegexModerationEngine:")
    print("✅ Processed messages with ZERO LLM calls (instant + free)")
    print("✅ Used deterministic pattern matching")
    print("✅ Extracted structured data (emails, URLs)")
    print("✅ Made binary decisions for clear violations")
    print()
    print("The LLM escalation agent:")
    print("✅ Only processed FLAGGED content (cost-optimized)")
    print("✅ Provided nuanced analysis for edge cases")
    print("✅ Generated human-readable recommendations")
    print()
    print("🔑 Key Insight:")
    print("Custom engines handle deterministic logic WITHOUT LLM costs.")
    print("Reserve expensive LLM calls for tasks requiring judgment!")
    print()
    print("Cost comparison for this demo:")
    print(f"  With LLM for all: ~{len(test_messages) * 2} API calls")
    print(f"  With custom engine: ~{len(escalations)} API calls")
    print(f"  Savings: ~{((1 - len(escalations)/len(test_messages)) * 100):.0f}% reduction")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
