"""
Scenario 4 — Shared Skill Library Across Multiple Agents

Demonstrates:
  - Glob patterns in .with_skills()
  - Multiple agents selecting subsets of a shared library
  - runtime=True opt-in for large libraries
  - Default discovery (no args to .with_skills())
"""
from __future__ import annotations

from pydantic import BaseModel

from flock import Flock


class RawInvoice(BaseModel):
    pdf_bytes: bytes


class InvoiceExtracted(BaseModel):
    total_due: float
    due_date: str


class CodeDiff(BaseModel):
    diff: str
    repo: str


class SecurityFindings(BaseModel):
    findings: list[dict]
    severity_max: str


class UserQuery(BaseModel):
    text: str


class Response(BaseModel):
    text: str


async def main() -> None:
    flock = Flock()

    # -- Agent 1: Finance pipeline ------------------------------------------
    # Uses a specific subset of the shared library via glob + explicit path.
    # Compile-time path (default) — skills are small prose documents.
    invoice_agent = (
        flock.agent("invoice-processor")
        .consumes(RawInvoice)
        .publishes(InvoiceExtracted)
        .with_skills(
            "~/.flock/skills/finance/*",                    # glob: all finance skills
            "~/.flock/skills/methodology/accounting-rules", # one explicit methodology skill
        )
    )

    # -- Agent 2: Security reviewer -----------------------------------------
    # 50+ skills in the security library — too big for compile-time token budget.
    # Caller opts into MAF-style runtime tool path with runtime=True.
    security_agent = (
        flock.agent("security-reviewer")
        .consumes(CodeDiff)
        .publishes(SecurityFindings)
        .with_skills(
            "~/.flock/skills/security/*",
            runtime=True,  # MAF-style load_skill/read_skill_resource/run_skill_script tools
        )
    )

    # -- Agent 3: General-purpose assistant ---------------------------------
    # Uses the default discovery precedence:
    #   ./skills/  →  ~/.flock/skills/  →  ./.claude/skills/
    generalist = (
        flock.agent("assistant")
        .consumes(UserQuery)
        .publishes(Response)
        .with_skills()  # no args — default discovery
    )

    # All three agents share the same ~/.flock/skills/ library.
    # Agent 1 compiles a few skills in. Agent 2 uses the tool-injection path
    # for its 50+ skill library. Agent 3 discovers everything available.


# Key surface properties demonstrated:
#   1. .with_skills() accepts: dir paths, file paths, glob patterns, Skill objects
#   2. One knob (runtime=True) picks MAF-style tool injection when compile-time
#      doesn't fit
#   3. .with_skills() with no args = use default discovery precedence
#   4. Multiple agents on the same flock instance can use overlapping or
#      disjoint subsets of the shared library
#   5. Same SKILL.md can be compiled (agent 1) or tool-injected (agent 2) —
#      skill author doesn't care
