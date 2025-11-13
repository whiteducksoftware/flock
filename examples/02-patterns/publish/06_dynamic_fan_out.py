"""
Dynamic Fan-Out: Software Project Planner

This example demonstrates dynamic fan-out at two levels:
- ProjectIdea → dynamic fan-out into Milestones
- Each Milestone → dynamic fan-out into UserStories

Semantics:
- fan_out=(min, max) lets the engine choose how many artifacts to generate
- min/max apply to the RAW engine output list
- where/validate are applied AFTER range checks
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


@flock_type
class ProjectIdea(BaseModel):
    name: str = Field(description="Project name")
    vision: str = Field(description="High-level project vision")
    complexity: str = Field(
        description="rough size/complexity: small, medium, large",
        default="medium",
    )


@flock_type
class Milestone(BaseModel):
    title: str
    description: str
    order: int = Field(description="Milestone order in the roadmap")
    risk: str = Field(
        description="risk level: low, medium, high",
        default="medium",
    )


@flock_type
class UserStory(BaseModel):
    milestone_title: str = Field(description="Title of the parent milestone")
    as_a: str
    i_want: str
    so_that: str
    estimate: int = Field(
        description="Story points (1-13)",
        ge=1,
        le=13,
    )


flock = Flock()


project_planner = (
    flock.agent("project_planner")
    .description(
        "Break a project idea into milestones. "
        "Simple projects should have fewer milestones, complex projects more. "
        "Mark higher-risk milestones so downstream agents can prioritise them."
    )
    .consumes(ProjectIdea)
    .publishes(
        Milestone,
        fan_out=(3, 8),  # Engine decides 3–8 milestones based on project complexity
    )
)


milestone_planner = (
    flock.agent("milestone_planner")
    .description(
        "For each milestone, generate user stories that break the work into deliverable units. "
        "Larger milestones should spawn more stories; filter out oversized stories."
    )
    .consumes(Milestone)
    .publishes(
        UserStory,
        fan_out=(2, 10),  # Engine decides 2–10 stories per milestone
    )
)


async def main():
    small_project = ProjectIdea(
        name="Documentation Cleanup",
        vision="Refresh the existing documentation site and fix obvious issues.",
        complexity="small",
    )

    large_project = ProjectIdea(
        name="New AI-Powered Onboarding",
        vision=(
            "Design and implement an AI-assisted onboarding experience that helps new "
            "users explore core features, suggests next steps, and tracks adoption."
        ),
        complexity="large",
    )

    print("\n=== Small Project (expected fewer milestones & stories) ===")
    await flock.publish(small_project)
    await flock.run_until_idle()

    print("\n=== Large Project (expected more milestones & stories) ===")
    await flock.publish(large_project)
    await flock.run_until_idle()

    # Inspect published milestones and user stories
    all_artifacts = await flock.store.list()
    milestone_artifacts = [a for a in all_artifacts if "Milestone" in a.type]
    story_artifacts = [a for a in all_artifacts if "UserStory" in a.type]

    print(f"\nTotal Milestones after filtering: {len(milestone_artifacts)}")
    for a in milestone_artifacts:
        m = Milestone(**a.payload)
        print(f"- [M{m.order}] {m.title} (risk={m.risk})")

    print(f"\nTotal UserStories after filtering: {len(story_artifacts)}")
    for a in story_artifacts[:20]:  # print first few stories
        s = UserStory(**a.payload)
        print(
            f"- [{s.milestone_title}] As {s.as_a} I want {s.i_want} "
            f"so that {s.so_that} (estimate={s.estimate})"
        )


if __name__ == "__main__":
    asyncio.run(main())

