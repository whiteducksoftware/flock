"""
🔒 Example 01: Basic Visibility - Context Provider Security Boundary

This example demonstrates the fundamental security boundary provided by Context Providers.
You'll see how visibility controls prevent agents from accessing data they shouldn't see.

Concepts:
- PublicVisibility: Everyone can see
- PrivateVisibility: Only specific agents
- Context Provider security boundary
- Automatic visibility enforcement

Run: uv run examples/08-context-provider/01_basic_visibility.py
"""

import asyncio
import sys
from pydantic import BaseModel, Field

from flock import Flock
from flock.visibility import PublicVisibility, PrivateVisibility

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


# Define our data models
class Message(BaseModel):
    """A message with content."""

    content: str
    classification: str  # "public" or "classified"


class Report(BaseModel):
    """A report summarizing what an agent saw."""

    agent_name: str
    messages_seen: int = Field(description="Number of messages the agent saw, including context")
    message_contents: list[str] = Field(description="Contents of the messages the agent saw, including context")


async def main():
    """Demonstrate basic visibility filtering."""
    print("🔒 CONTEXT PROVIDER SECURITY DEMO")
    print("=" * 60)
    print()

    # Create orchestrator
    flock = Flock()

    # Create a shared correlation ID for this conversation
    from uuid import uuid4
    conversation_id = uuid4()

    # Create two agents: one regular, one with clearance
    public_agent = (
        flock.agent("public_agent")
        .description("A regular agent without security clearance")
        .consumes(Message)
        .publishes(Report)
    )

    classified_agent = (
        flock.agent("classified_agent")
        .description("An agent with security clearance")
        .consumes(Message)
        .publishes(Report)
    )

    # Publish some messages - mix of public and classified
    print("📤 Publishing messages...")
    print()

    # Public message - everyone can see
    await flock.publish(
        Message(content="Hello world!", classification="public"),
        visibility=PublicVisibility(),
        correlation_id=conversation_id,
    )
    print("✅ Published PUBLIC message: 'Hello world!'")
    await flock.run_until_idle()

    # Classified message - only classified_agent can see
    await flock.publish(
        Message(content="Secret operation at midnight", classification="classified"),
        visibility=PrivateVisibility(agents={"classified_agent"}),
        correlation_id=conversation_id,
    )
    print("🔒 Published CLASSIFIED message: 'Secret operation at midnight'")
    print("   (Only visible to: classified_agent)")

    # Another public message
    await flock.publish(
        Message(content="Weather is nice today", classification="public"),
        visibility=PublicVisibility(),
        correlation_id=conversation_id,
    )
    print("✅ Published PUBLIC message: 'Weather is nice today'")

    # Another classified message
    await flock.publish(
        Message(content="Launch codes: alpha-bravo-charlie", classification="classified"),
        visibility=PrivateVisibility(agents={"classified_agent"}),
        correlation_id=conversation_id,
    )
    print("🔒 Published CLASSIFIED message: 'Launch codes: alpha-bravo-charlie'")
    print("   (Only visible to: classified_agent)")
    print()

    # Wait for agents to process
    print("⏳ Agents processing messages...")
    await flock.run_until_idle()
    print()

    # Retrieve reports from blackboard
    print("📊 RESULTS:")
    print("=" * 60)
    print()

    all_artifacts = await flock.store.list()
    reports = [a for a in all_artifacts if "Report" in a.type]

    for report_artifact in reports:
        report = Report(**report_artifact.payload)
        print(f"👤 Agent: {report.agent_name}")
        print(f"   Messages seen: {report.messages_seen}")
        print(f"   Contents:")
        for content in report.message_contents:
            classification = "PUBLIC" if "secret" not in content.lower() and "launch" not in content.lower() else "CLASSIFIED"
            emoji = "✅" if classification == "PUBLIC" else "🔒"
            print(f"     {emoji} {content}")
        print()

    print()
    print("🎯 KEY TAKEAWAYS:")
    print("=" * 60)
    print("1. Context Provider enforces visibility automatically")
    print("2. public_agent only saw PUBLIC messages (2 messages)")
    print("3. classified_agent saw ALL messages (4 messages)")
    print("4. Agents cannot bypass this security boundary")
    print("5. No explicit filtering code needed - it's built-in!")


if __name__ == "__main__":
    asyncio.run(main())
