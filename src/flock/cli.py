"""Typer-based CLI for blackboard agents."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

# Lazy import: only import examples when CLI commands are invoked
# This prevents polluting type_registry on every package import
from flock.service import BlackboardHTTPService


app = typer.Typer(help="Blackboard Agents CLI")
console = Console()


@app.command()
def demo(
    topic: str = typer.Option("AI agents collaborating", help="Idea topic"),
    genre: str = typer.Option("comedy", help="Idea genre"),
) -> None:
    """Run the demo pipeline locally and stream results to the console."""

    from flock.examples import Idea, create_demo_orchestrator

    orchestrator, agents = create_demo_orchestrator()
    idea = Idea(topic=topic, genre=genre)

    async def _run_demo() -> None:
        await orchestrator.arun(agents["movie"], idea)
        await orchestrator.run_until_idle()
        table = Table(title="Published Artifacts")
        table.add_column("Type")
        table.add_column("Payload", overflow="fold")
        for artifact in await orchestrator.store.list():
            table.add_row(artifact.type, repr(artifact.payload))
        console.print(table)

    asyncio.run(_run_demo())


@app.command()
def list_agents() -> None:
    """List registered agents for the demo orchestrator."""

    from flock.examples import create_demo_orchestrator

    orchestrator, _agents = create_demo_orchestrator()
    table = Table(title="Agents")
    table.add_column("Name")
    table.add_column("Description")
    for agent in orchestrator.agents:
        table.add_row(agent.name, agent.description or "")
    console.print(table)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the HTTP control plane bound to the demo orchestrator."""

    from flock.examples import create_demo_orchestrator

    orchestrator, _ = create_demo_orchestrator()
    service = BlackboardHTTPService(orchestrator)
    service.run(host=host, port=port)


def main() -> None:
    app()


__all__ = ["app", "main"]
