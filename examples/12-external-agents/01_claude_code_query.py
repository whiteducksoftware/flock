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
- ANTHROPIC_API_KEY set in environment

PATTERN: Query -> External Agent -> Answer
USE CASE: Offload complex coding tasks to Claude Code while keeping
          the orchestration and result aggregation in Flock
"""

import asyncio
import os
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
WORKING_DIR = str(Path.cwd())  # Where Claude Code runs


# ============================================================================
# PREFLIGHT: Verify Claude Code is available
# ============================================================================
def check_claude_code() -> None:
    """Verify the claude CLI is installed and ANTHROPIC_API_KEY is set."""
    import shutil

    if not shutil.which("claude"):
        print("ERROR: Claude Code CLI not found.")
        print("Install it with: npm install -g @anthropic-ai/claude-code")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set in environment.")
        sys.exit(1)
    print("Claude Code CLI found, API key set.")


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


# ============================================================================
# AGENT SETUP
# ============================================================================
check_claude_code()

flock = Flock("claude-code-query", model="openai/gpt-4.1", use_dashboard=USE_DASHBOARD)

# --- Infrastructure components ---

# Token store for external agent auth
token_store = InMemoryTokenStore()

# Changelog stream — delivers events to subscribers in real-time
changelog = ChangelogStreamComponent(token_store=token_store)

# Auth component — validates bearer tokens on REST endpoints
auth = AuthenticationComponent()

# External agent scheduler — bridges changelog events to subprocess spawns
scheduler = ExternalAgentScheduler()
scheduler.configure(
    stream_dispatcher=changelog.dispatcher if changelog._dispatcher else None,
    adapters={"claude_code": ClaudeCodeRuntime()},
)
scheduler.set_token_store(token_store)

# Register components on the orchestrator
flock.add_orchestrator_component(scheduler)
flock.add_server_component(changelog)
flock.add_server_component(auth)

# --- Agents ---

# External agent: Claude Code answers coding questions
(
    flock.agent("code-answerer")
    .kind("external")
    .adapter("claude_code")
    .working_dir(WORKING_DIR)
    .spawn_timeout(120.0)
    .consumes(CodingQuestion)
    .publishes(CodingAnswer)
    .session_mode("new")
    .done()
)

# Internal agent: summarizes the answer for the user
(
    flock.agent("summarizer")
    .consumes(CodingAnswer)
    .instruction(
        "You received a coding answer from Claude Code. "
        "Summarize it in 2-3 sentences highlighting the key insight. "
        "If there's a code snippet, mention the approach used."
    )
    .done()
)


# ============================================================================
# RUN: Publish a question and watch the cascade
# ============================================================================
async def main() -> None:
    print("\n--- Publishing a coding question ---\n")

    question = CodingQuestion(
        question="What's the most efficient way to find duplicates in a list in Python?",
        language="python",
        context="Looking for O(n) solution, not O(n^2)",
    )

    await flock.run_async(initial_data=question)

    print("\n--- Workflow complete ---")
    print("Flow: CodingQuestion -> code-answerer (Claude Code) -> CodingAnswer -> summarizer")


if __name__ == "__main__":
    asyncio.run(main())
