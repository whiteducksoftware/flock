"""
External Agents: Claude Code as a Flock Agent

Use Claude Code as a first-class Flock agent. The adapter handles process
spawning, I/O serialization, and output parsing internally — you just wire
it into the blackboard like any other agent.

🔧 SETUP:
    1) Install Claude Code: npm install -g @anthropic-ai/claude-code
    2) export ANTHROPIC_API_KEY=your-key

Run:
    uv run python examples/12-external-agents/01_claude_code_agent.py
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


@flock_type
class CodingQuestion(BaseModel):
    question: str = Field(description="A question about code or software engineering")
    context: str = Field(default="", description="Optional code or context to reference")


@flock_type
class CodingAnswer(BaseModel):
    answer: str = Field(description="Detailed answer to the question")
    code_snippets: list[str] = Field(
        default_factory=list, description="Relevant code examples"
    )


# ============================================================================
# That's it. Same .agent() builder, two new methods: .kind() and .adapter()
# ============================================================================
flock = Flock()

answerer = (
    flock.agent("code-answerer")
    .kind("external")
    .adapter("claude_code")
    .consumes(CodingQuestion)
    .publishes(CodingAnswer)
)


async def main():
    question = CodingQuestion(
        question="What's the most robust way to handle database connection pooling in async Python?",
        context="We're using asyncpg with FastAPI",
    )

    await flock.publish(question)
    await flock.run_until_idle()

    answers = await flock.store.get_by_type(CodingAnswer)
    if answers:
        a = answers[0]
        print(f"💡 {a.answer[:300]}...")
        if a.code_snippets:
            print(f"📝 {len(a.code_snippets)} code example(s) included")

    print("\n✅ Claude Code answered via the blackboard — same API as any Flock agent.")


if __name__ == "__main__":
    asyncio.run(main())
