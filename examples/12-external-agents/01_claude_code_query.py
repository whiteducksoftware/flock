"""
External Agents: Claude Code Query-Answer

A simple pattern where an internal agent publishes a coding question and
Claude Code (running as an external subprocess) answers it.  The answer
flows back through the blackboard as an artifact.

PATTERN: Question -> Claude Code (external) -> Answer -> Summarizer (internal)

REQUIREMENTS:
- Claude Code CLI installed and authenticated (npm install -g @anthropic-ai/claude-code)
  Uses your logged-in subscription — no API key needed.

All infrastructure (scheduler, adapters, event routing) is auto-wired
by Flock when it detects agents with kind("external").
"""

import asyncio
import shutil
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


# --- Preflight ---

def check_claude_code() -> None:
    if not shutil.which("claude"):
        print("ERROR: Claude Code CLI not found.")
        print("Install it with: npm install -g @anthropic-ai/claude-code")
        sys.exit(1)
    print("Claude Code CLI found.")


# --- Types ---

@flock_type
class CodingQuestion(BaseModel):
    question: str = Field(description="The coding question or task")
    language: str = Field(default="python", description="Programming language context")
    context: str = Field(default="", description="Additional context")


@flock_type
class CodingAnswer(BaseModel):
    answer: str = Field(description="The answer or solution")
    code: str = Field(default="", description="Code snippet if applicable")
    confidence: str = Field(default="high", description="Confidence level")


@flock_type
class AnswerSummary(BaseModel):
    summary: str = Field(description="2-3 sentence summary of the answer")
    approach: str = Field(default="", description="The approach or technique used")


# --- Setup ---

check_claude_code()

flock = Flock()

# External agent: Claude Code answers coding questions
(flock.agent("code-answerer")
    .kind("external")
    .adapter("claude_code")
    .working_dir(str(Path.cwd()))
    .spawn_timeout(120.0)
    .consumes(CodingQuestion)
    .publishes(CodingAnswer)
    .session_mode("new"))

# Internal agent: summarizes the answer
(flock.agent("summarizer")
    .consumes(CodingAnswer)
    .publishes(AnswerSummary)
    .description(
        "You received a coding answer from Claude Code. "
        "Summarize it in 2-3 sentences highlighting the key insight. "
        "If there's a code snippet, mention the approach used."
    ))


# --- Run ---

async def main() -> None:
    print("\n--- Publishing a coding question ---\n")

    question = CodingQuestion(
        question="What's is your version number",
        language="python",
        context="Testing Flock's integration with Claude Code as an external agent.",
    )

    await flock.serve(blocking=False)
    await flock.publish(question)
    await flock.run_until_idle()

    print("\n--- Workflow complete ---")
    print("Flow: CodingQuestion -> code-answerer (Claude Code) -> CodingAnswer -> summarizer")

    import logging
    logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)
    await flock.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
