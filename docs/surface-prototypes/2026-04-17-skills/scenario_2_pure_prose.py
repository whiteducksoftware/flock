"""
Scenario 2 — Pure-Prose Skill (methodology, no typed output)

Demonstrates that skills without Flock-specific frontmatter still work.
Body becomes instructions in the DSPy signature. Same .with_skills() API.

Read alongside ../example_skills/dhh-rails-style/SKILL.md.
"""
from __future__ import annotations

from pydantic import BaseModel

from flock import Flock


class RailsFeatureSpec(BaseModel):
    feature_name: str
    user_story: str
    constraints: list[str] = []


class RailsCode(BaseModel):
    migration: str | None
    models: dict[str, str]
    controllers: dict[str, str]
    views: dict[str, str]
    tests: dict[str, str]


async def main() -> None:
    flock = Flock()

    code_gen = (
        flock.agent("rails-coder")
        .consumes(RailsFeatureSpec)
        .publishes(RailsCode)
        .with_skills("./example_skills/dhh-rails-style/")
    )

    async with flock.run() as session:
        await session.publish(
            RailsFeatureSpec(
                feature_name="team-invites",
                user_story="As an admin, I can invite users to my team by email",
                constraints=["No React", "Use Turbo", "RESTful endpoints"],
            )
        )
        await session.run_until_idle()

        code = session.query(RailsCode).one()
        print(list(code.models.keys()))  # e.g. ['Team', 'Invitation']


# Key surface properties demonstrated:
#   1. Pure-prose skills require zero Flock-specific frontmatter
#   2. Skill body is merged into dspy.Signature instructions (compile-time,
#      no runtime disclosure needed)
#   3. Engine stays dspy.Predict — no tools, no ReAct loop, cheapest path
#   4. Skill author writes methodology Markdown; Flock handles the plumbing
