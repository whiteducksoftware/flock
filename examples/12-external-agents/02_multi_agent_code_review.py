"""
External Agents: Multi-Agent Code Review with Claude Code + Codex

A code review pipeline using two external agents in parallel:
- Claude Code reviews for correctness and security
- Codex reviews for performance and style

Both agents receive the same PRDiff artifact, work independently, and
their results are merged by an internal summarizer agent.

KEY CONCEPTS:
- Multiple external agents triggered by the same artifact type
- Two different adapters (claude_code, codex) in one orchestrator
- Serial execution per agent, but different agents run concurrently
- Internal agent consumes results from both external agents
- Session resume for iterative review workflows

REQUIREMENTS:
- Claude Code CLI installed: npm install -g @anthropic-ai/claude-code
- Codex CLI installed: npm install -g @openai/codex
- ANTHROPIC_API_KEY set in environment
- OPENAI_API_KEY set in environment

PATTERN: Fan-out -> External Agents (parallel) -> Fan-in
USE CASE: Multi-perspective code review, parallel analysis with
          different AI models, consensus-building pipelines
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
from flock.integrations.external.adapters.codex import CodexRuntime
from flock.integrations.external.scheduler import ExternalAgentScheduler
from flock.registry import flock_type


# ============================================================================
# CONFIGURATION
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode
WORKING_DIR = str(Path.cwd())  # Where both agents run


# ============================================================================
# PREFLIGHT: Verify both CLIs are available
# ============================================================================
def preflight_check() -> None:
    """Verify both CLIs are installed and API keys are set."""
    import shutil

    errors: list[str] = []

    if not shutil.which("claude"):
        errors.append(
            "Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
        )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        errors.append("ANTHROPIC_API_KEY not set in environment.")

    if not shutil.which("codex"):
        errors.append(
            "Codex CLI not found. Install: npm install -g @openai/codex"
        )
    if not os.environ.get("OPENAI_API_KEY"):
        errors.append("OPENAI_API_KEY not set in environment.")

    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        sys.exit(1)

    print("Both CLIs found, API keys set.")


# ============================================================================
# TYPE REGISTRATION
# ============================================================================
@flock_type
class PRDiff(BaseModel):
    """A pull request diff to be reviewed."""

    repo: str = Field(description="Repository name")
    pr_number: int = Field(description="Pull request number")
    title: str = Field(description="PR title")
    diff: str = Field(description="The actual diff content")
    author: str = Field(description="PR author")


@flock_type
class SecurityReview(BaseModel):
    """Security and correctness review from Claude Code."""

    verdict: str = Field(description="approved | changes_requested | needs_discussion")
    security_issues: list[str] = Field(default_factory=list)
    correctness_issues: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    reviewer: str = Field(default="claude-code")


@flock_type
class PerformanceReview(BaseModel):
    """Performance and style review from Codex."""

    verdict: str = Field(description="approved | changes_requested | needs_discussion")
    performance_issues: list[str] = Field(default_factory=list)
    style_issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    reviewer: str = Field(default="codex")


@flock_type
class ReviewSummary(BaseModel):
    """Merged summary of all reviews."""

    pr_number: int
    overall_verdict: str = Field(description="Final verdict considering all reviews")
    key_findings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


# ============================================================================
# AGENT SETUP
# ============================================================================
preflight_check()

flock = Flock("code-review", model="openai/gpt-4.1", use_dashboard=USE_DASHBOARD)

# --- Infrastructure ---
token_store = InMemoryTokenStore()
changelog = ChangelogStreamComponent(token_store=token_store)
auth = AuthenticationComponent()

# Scheduler with BOTH adapters registered
scheduler = ExternalAgentScheduler()
scheduler.configure(
    stream_dispatcher=changelog.dispatcher if changelog._dispatcher else None,
    adapters={
        "claude_code": ClaudeCodeRuntime(),
        "codex": CodexRuntime(),
    },
)
scheduler.set_token_store(token_store)

flock.add_orchestrator_component(scheduler)
flock.add_server_component(changelog)
flock.add_server_component(auth)

# --- External Agent 1: Claude Code (security + correctness) ---
(
    flock.agent("security-reviewer")
    .kind("external")
    .adapter("claude_code")
    .working_dir(WORKING_DIR)
    .spawn_timeout(300.0)
    .consumes(PRDiff)
    .publishes(SecurityReview)
    .session_mode("resume")  # Resume conversation for follow-up reviews
    .done()
)

# --- External Agent 2: Codex (performance + style) ---
(
    flock.agent("performance-reviewer")
    .kind("external")
    .adapter("codex")
    .working_dir(WORKING_DIR)
    .spawn_timeout(300.0)
    .consumes(PRDiff)
    .publishes(PerformanceReview)
    .session_mode("new")  # Fresh session each time
    .done()
)

# --- Internal Agent: Merge reviews into a summary ---
# This agent fires when EITHER review arrives. In a production setup,
# you'd use a JoinSpec to wait for both reviews before summarizing.
(
    flock.agent("review-merger")
    .consumes(SecurityReview, PerformanceReview)
    .produces(ReviewSummary)
    .instruction(
        "You are merging code review results from two independent reviewers. "
        "Synthesize their findings into a single summary with an overall verdict. "
        "If either reviewer requests changes, the overall verdict should be "
        "'changes_requested'. List the most important findings and recommended actions."
    )
    .done()
)


# ============================================================================
# RUN: Publish a PR diff and watch both reviewers work
# ============================================================================
async def main() -> None:
    print("\n--- Publishing PR for multi-agent review ---\n")

    pr = PRDiff(
        repo="my-app",
        pr_number=42,
        title="feat: add user authentication with JWT tokens",
        diff="""
diff --git a/auth.py b/auth.py
new file mode 100644
--- /dev/null
+++ b/auth.py
@@ -0,0 +1,35 @@
+import jwt
+import hashlib
+from datetime import datetime, timedelta
+
+SECRET_KEY = "my-secret-key-change-in-production"
+
+def hash_password(password: str) -> str:
+    return hashlib.md5(password.encode()).hexdigest()
+
+def create_token(user_id: int) -> str:
+    payload = {
+        "user_id": user_id,
+        "exp": datetime.utcnow() + timedelta(hours=24),
+    }
+    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
+
+def verify_token(token: str) -> dict:
+    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
+
+def login(username: str, password: str) -> str:
+    # SQL query to check credentials
+    query = f"SELECT * FROM users WHERE username='{username}' AND password='{hash_password(password)}'"
+    user = db.execute(query).fetchone()
+    if user:
+        return create_token(user["id"])
+    raise ValueError("Invalid credentials")
""".strip(),
        author="junior-dev",
    )

    await flock.run_async(initial_data=pr)

    print("\n--- Review workflow complete ---")
    print(
        "Flow: PRDiff -> security-reviewer (Claude Code) + performance-reviewer (Codex)"
    )
    print("      -> SecurityReview + PerformanceReview -> review-merger -> ReviewSummary")


if __name__ == "__main__":
    asyncio.run(main())
