"""
Agents Component Examples

This example demonstrates the AgentsServerComponent capabilities:
1. List all registered agents
2. Get agent details and metadata
3. View agent subscriptions
4. REST API integration
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.components.server import (
    AgentsServerComponent,
    AgentsServerComponentConfig,
)


class CodeReview(BaseModel):
    """Example artifact for code review requests."""

    file_path: str
    language: str
    code: str


class ReviewResult(BaseModel):
    """Example artifact for review results."""

    file_path: str
    issues: list[str]
    suggestions: list[str]
    approved: bool


class Documentation(BaseModel):
    """Example artifact for documentation."""

    topic: str
    content: str


async def main():
    """Demonstrate Agents component usage."""
    print("🤖 Agents Component Examples\n")
    print("=" * 60)

    # Example 1: Basic Agents component
    print("\n1️⃣  Basic Agents Component")
    print("-" * 60)

    flock = Flock("openai/gpt-4o")

    agents_component = AgentsServerComponent(
        config=AgentsServerComponentConfig(
            prefix="/api/v1",
            tags=["Agents"],
        )
    )

    print("✅ Agents component created")
    print("   Endpoints:")
    print(f"   - GET {agents_component.config.prefix}/agents")
    print(f"   - GET {agents_component.config.prefix}/agents/{{name}}")

    # Example 2: Create multiple agents
    print("\n2️⃣  Creating Multiple Agents")
    print("-" * 60)

    # Code reviewer agent
    code_reviewer = (
        flock.agent("code_reviewer")
        .description("Reviews code for quality and best practices")
        .consumes(CodeReview)
        .publishes(ReviewResult)
        .instruction(
            "Analyze the code and provide detailed feedback on:\n"
            "1. Code quality and style\n"
            "2. Potential bugs or issues\n"
            "3. Best practice recommendations\n"
            "4. Performance considerations"
        )
    )

    print(f"✅ Agent created: {code_reviewer.name}")
    print("   Consumes: CodeReview")
    print("   Publishes: ReviewResult")

    # Documentation writer agent
    doc_writer = (
        flock.agent("doc_writer")
        .description("Generates comprehensive documentation")
        .consumes(ReviewResult)
        .publishes(Documentation)
        .instruction(
            "Based on the review results, create clear documentation that:\n"
            "1. Explains the code's purpose\n"
            "2. Documents usage examples\n"
            "3. Lists any important considerations\n"
            "4. Provides API reference if applicable"
        )
    )

    print(f"✅ Agent created: {doc_writer.name}")
    print("   Consumes: ReviewResult")
    print("   Publishes: Documentation")

    # Quality gate agent
    quality_gate = (
        flock.agent("quality_gate")
        .description("Ensures code meets quality standards before approval")
        .consumes(ReviewResult)
        .publishes(ReviewResult)
        .instruction(
            "Review the code analysis and:\n"
            "1. Check if there are critical issues\n"
            "2. Verify best practices are followed\n"
            "3. Update approval status based on quality threshold\n"
            "4. Add final quality assessment"
        )
    )

    print(f"✅ Agent created: {quality_gate.name}")
    print("   Consumes: ReviewResult")
    print("   Publishes: ReviewResult")

    # Example 3: Full server setup
    print("\n3️⃣  Full Server Setup")
    print("-" * 60)

    print("\n🚀 Starting server with Agents component...")
    print("   Server will run on http://127.0.0.1:8344")
    print("\n   Available endpoints:")
    print("   - GET http://127.0.0.1:8344/api/v1/agents")
    print("   - GET http://127.0.0.1:8344/api/v1/agents/code_reviewer")
    print("   - GET http://127.0.0.1:8344/api/v1/agents/doc_writer")
    print("   - GET http://127.0.0.1:8344/api/v1/agents/quality_gate")
    print("\n   Press Ctrl+C to stop the server")

    # Start server (non-blocking for demo)
    await flock.serve(
        components=[agents_component],
        host="127.0.0.1",
        port=8344,
        blocking=False,
    )

    # Wait for server to start
    await asyncio.sleep(2)
    print("\n✅ Server is running!")

    # Example 4: Test agent workflow
    print("\n4️⃣  Testing Agent Workflow")
    print("-" * 60)

    test_review = CodeReview(
        file_path="src/utils.py",
        language="python",
        code="""
def calculate_total(items):
    total = 0
    for item in items:
        total += item['price'] * item['quantity']
    return total
""",
    )

    print("\n📤 Publishing code review request...")
    print(f"   File: {test_review.file_path}")
    print(f"   Language: {test_review.language}")

    await flock.publish(test_review)
    await flock.run_until_idle()

    print("\n✅ Workflow completed!")
    print("   Chain: CodeReview → code_reviewer → ReviewResult → quality_gate → ReviewResult")
    print("                                      → doc_writer → Documentation")

    # Example 5: Query agents via API
    print("\n5️⃣  Query Agents via REST API")
    print("-" * 60)

    print("\n   You can now query agents using curl:")
    print("\n   # List all agents:")
    print("   curl http://127.0.0.1:8344/api/v1/agents")
    print("\n   # Get specific agent details:")
    print("   curl http://127.0.0.1:8344/api/v1/agents/code_reviewer")
    print("\n   # Get agent subscriptions:")
    print("   curl http://127.0.0.1:8344/api/v1/agents/code_reviewer | jq '.subscriptions'")
    print("\n   # Get agent statistics:")
    print("   curl http://127.0.0.1:8344/api/v1/agents/code_reviewer | jq '.stats'")

    # Keep server running
    print("\n⏳ Keeping server running for 60 seconds...")
    print("   Try the curl commands above!")
    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
