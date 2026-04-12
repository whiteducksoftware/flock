"""
External Agents: Claude Code Query-Answer

A simple pattern where an internal agent publishes a coding question and
Claude Code (running as an external subprocess) answers it.  The answer
flows back through the blackboard as an artifact.

KEY CONCEPTS:
- kind("external") marks an agent as a subprocess-based agent
- adapter("claude_code") selects the Claude Code CLI adapter
- ExternalAgentScheduler bridges changelog events to subprocess spawns
- ChangelogStreamComponent provides the real-time event stream
- Token auth lets the external agent publish results back

REQUIREMENTS:
- Claude Code CLI installed: npm install -g @anthropic-ai/claude-code
  (must be authenticated — run `claude` once to log in)

PATTERN: Query -> External Agent -> Answer
USE CASE: Offload complex coding tasks to Claude Code while keeping
          the orchestration and result aggregation in Flock
"""

import asyncio
import shutil
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from flock import Flock
from flock.auth.token_store import InMemoryTokenStore
from flock.components.server.auth.auth_component import AuthenticationComponent
from flock.components.server.changelog.changelog_component import (
    ChangelogStreamComponent,
)
from flock.integrations.external.adapters.claude_code import ClaudeCodeRuntime
from flock.integrations.external.scheduler import ExternalAgentScheduler
from flock.registry import flock_type


# ============================================================================
# CONFIGURATION
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode
WORKING_DIR = str(Path.cwd())


# ============================================================================
# PREFLIGHT: Verify Claude Code is available
# ============================================================================
def check_claude_code() -> None:
    """Verify the claude CLI is installed."""
    if not shutil.which("claude"):
        print("ERROR: Claude Code CLI not found.")
        print("Install it with: npm install -g @anthropic-ai/claude-code")
        sys.exit(1)
    print("Claude Code CLI found.")


# ============================================================================
# TYPE REGISTRATION: Define artifact types
# ============================================================================
@flock_type
class CodingQuestion(BaseModel):
    """A coding question to be answered by Claude Code."""

    question: str = Field(description="The coding question or task")
    language: str = Field(default="python", description="Programming language context")
    context: str = Field(default="", description="Additional context for the question")


@flock_type
class CodingAnswer(BaseModel):
    """An answer from Claude Code."""

    answer: str = Field(description="The answer or solution")
    code: str = Field(default="", description="Code snippet if applicable")
    confidence: str = Field(
        default="high", description="Confidence level: high, medium, low"
    )


@flock_type
class AnswerSummary(BaseModel):
    """A concise summary of the coding answer."""

    summary: str = Field(description="2-3 sentence summary of the answer")
    approach: str = Field(default="", description="The approach or technique used")


# ============================================================================
# SETUP
# ============================================================================
check_claude_code()

flock = Flock()

# --- Infrastructure components ---

# Token store for external agent auth
token_store = InMemoryTokenStore()

# Changelog stream — delivers events to subscribers in real-time.
# The dispatcher is created during serve() startup and auto-wired
# into both the ArtifactManager and ExternalAgentScheduler.
changelog = ChangelogStreamComponent(token_store=token_store)
auth = AuthenticationComponent()

# External agent scheduler — adapters are registered here.
# The StreamDispatcher is auto-wired by ChangelogStreamComponent on startup.
scheduler = ExternalAgentScheduler()
scheduler._adapters = {"claude_code": ClaudeCodeRuntime()}
scheduler.set_token_store(token_store)

# Register components
flock.add_component(scheduler)
flock.add_server_component(changelog)
flock.add_server_component(auth)

# --- Agents ---

# External agent: Claude Code answers coding questions
(flock.agent("code-answerer")
    .kind("external")
    .adapter("claude_code")
    .working_dir(WORKING_DIR)
    .spawn_timeout(120.0)
    .consumes(CodingQuestion)
    .publishes(CodingAnswer)
    .session_mode("new"))

# Internal agent: summarizes the answer for the user
(flock.agent("summarizer")
    .consumes(CodingAnswer)
    .publishes(AnswerSummary)
    .description(
        "You received a coding answer from Claude Code. "
        "Summarize it in 2-3 sentences highlighting the key insight. "
        "If there's a code snippet, mention the approach used."
    ))


# ============================================================================
# RUN
# ============================================================================
async def main() -> None:
    print("\n--- Publishing a coding question ---\n")

    question = CodingQuestion(
        question="What's the most efficient way to find duplicates in a list in Python?",
        language="python",
        context="Looking for O(n) solution, not O(n^2)",
    )

    # Start server in background (needed for REST API + changelog stream)
    await flock.serve(dashboard=USE_DASHBOARD, blocking=False)
    await flock.publish(question)
    await flock.run_until_idle()

    print("\n--- Workflow complete ---")
    print("Flow: CodingQuestion -> code-answerer (Claude Code) -> CodingAnswer -> summarizer")

    # Clean shutdown — suppress uvicorn's noisy CancelledError log
    import logging
    logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)
    await flock.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
