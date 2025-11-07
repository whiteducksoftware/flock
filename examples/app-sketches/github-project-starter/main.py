import asyncio
import os

from pydantic import BaseModel, Field

from flock import Flock
from flock.mcp import StdioServerParameters
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class Task(BaseModel):
    title: str
    repository: str = Field(
        ..., description="GitHub repository in the format 'owner/repo'"
    )
    content: str = Field(..., description="Detailed description of the task")
    implementation_steps: list[str] = Field(
        ..., description="Step-by-step implementation plan"
    )
    acceptance_criteria: list[str] = Field(
        ..., description="Acceptance criteria for the task", min_items=3
    )
    test_cases: list[str] = Field(..., description="Test cases to validate the task")


@flock_type
class Issue(BaseModel):
    title: str
    repository: str = Field(
        ..., description="GitHub repository in the format 'owner/repo'"
    )
    content: str = Field(..., description="Detailed description of the issue")
    url: str


@flock_type
class Project(BaseModel):
    title: str
    description: str


flock = Flock()


flock.add_mcp(
    name="github_tools",
    enable_tools_feature=True,
    connection_params=StdioServerParameters(
        command="docker",
        args=[
            "run",
            "-i",
            "--rm",
            "-e",
            "GITHUB_PERSONAL_ACCESS_TOKEN",
            "ghcr.io/github/github-mcp-server",
        ],
        env={
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv(
                "GITHUB_PERSONAL_ACCESS_TOKEN", ""
            ),
        },
    ),
)


(
    flock.agent("task_generator")
    .description(
        "Generates a list of tasks for a project and creates the repository on GitHub with the github mcp tools."
    )
    .with_mcps({"github_tools": {"tool_whitelist": ["create_repository"]}})
    .consumes(Project)
    .publishes(Task, fan_out=5)
)


(
    flock.agent("issue_creator")
    .description(
        "Creates a github issue for a given task in the specified repository using the github mcp tools."
    )
    .with_mcps({"github_tools": {"tool_whitelist": ["issue_write","issue_read"]}})
    .consumes(Task)
    .publishes(Issue)
    .max_concurrency(5)
)


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    project = Project(
        title="TicTacToe", description="A sleek designed web based TicTacToe game."
    )
    await flock.publish(project)
    await flock.run_until_idle()
    print("✅ TicTacToe generation complete! Check the dashboard for results.")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
