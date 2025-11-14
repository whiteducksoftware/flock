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
from flock.engines import BAMLAdapter, DSPyEngine
from flock.registry import flock_type


@flock_type
class ProjectIdea(BaseModel):
    name: str = Field(description="Project name")
    vision: str = Field(description="High-level project vision")


@flock_type
class Milestone(BaseModel):
    id: str = Field(description="Unique identifier for the milestone")
    title: str = Field(description="Title of the milestone")
    description: str = Field(description="Detailed description of the milestone")
    order: int = Field(description="Milestone order in the roadmap")
    risk: str = Field(
        description="risk level: low, medium, high",
        default="medium",
    )


@flock_type
class UserStory(BaseModel):
    milestone_title: str = Field(description="Title of the parent milestone")
    milestone_id: str = Field(description="ID of the parent milestone")
    description: str = Field(description="Detailed description of the user story")
    as_a : str = Field(description="Role of the user")
    i_want: str = Field(description="What the user wants to achieve")
    so_that: str = Field(description="Reason/benefit for the user")
    acceptance_criterias: list[str] = Field(
        description="List of acceptance criteria", min_length=3
    )
    estimate: int = Field(
        description="Story points (1-13)",
        ge=1,
        le=13,
    )


flock = Flock("azure/gpt-5")


project_planner = (
    flock.agent("project_planner")
    .description(
        "Break a project idea into milestones. "
        "Simple projects should have fewer milestones, complex projects more. "
        "Mark higher-risk milestones so downstream agents can prioritise them."
        "Should always start with a 'milestone 0' for setup, scaffolding and initial configuration of the project and environment."
    )
    .consumes(ProjectIdea)
    .publishes(
        Milestone,
        fan_out=(3, 10),  # Engine decides 3–10 milestones based on project complexity
    )
    .with_engines(
            DSPyEngine(
                adapter=BAMLAdapter(),  # Better structured output parsing
            )
    ).max_concurrency(1)
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
    .with_engines(
            DSPyEngine(
                adapter=BAMLAdapter(),  # Better structured output parsing
            )
    ).max_concurrency(1)
)


async def main():
    project = ProjectIdea(
        name="4connect",
        vision="Implement the game 4connect as a web application.",
    )

    # project = ProjectIdea(
    #     name="Outlook-GPT",
    #     vision=(
    #         "Design and implement a modern AI-first email client."
    #     ),
    # )

    await flock.publish(project)
    await flock.run_until_idle()

    # Inspect published milestones and user stories
    all_artifacts = await flock.store.list()
    milestone_artifacts = [a for a in all_artifacts if "Milestone" in a.type]
    story_artifacts = [a for a in all_artifacts if "UserStory" in a.type]

    print(f"\nTotal Milestones: {len(milestone_artifacts)}")
    for a in milestone_artifacts:
        m = Milestone(**a.payload)
        print(f"- [M{m.order}] {m.title} (risk={m.risk})")

    print(f"\nTotal UserStories: {len(story_artifacts)}")
    for a in story_artifacts[:20]:  # print first few stories
        s = UserStory(**a.payload)
        print(
            f"- [{s.milestone_title}] As {s.as_a} I want {s.i_want} "
            f"so that {s.so_that} (estimate={s.estimate})"
        )


if __name__ == "__main__":
    asyncio.run(main())
