"""Typer-based CLI for blackboard agents."""

from __future__ import annotations

import asyncio
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from typer.models import OptionInfo

# Lazy import: only import examples when CLI commands are invoked
# This prevents polluting type_registry on every package import
from flock.api.service import BlackboardHTTPService
from flock.core.store import SQLiteBlackboardStore


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
def serve(
    host: str = "127.0.0.1",
    port: int = 8344,
    sqlite_db: str | None = typer.Option(None, help="Path to SQLite blackboard store"),
) -> None:
    """Run the HTTP control plane bound to the demo orchestrator."""

    from flock.examples import create_demo_orchestrator

    if isinstance(sqlite_db, OptionInfo):  # Allow direct invocation in tests
        sqlite_db = sqlite_db.default

    store = None
    if sqlite_db is not None:
        sqlite_store = SQLiteBlackboardStore(sqlite_db)

        async def _prepare() -> SQLiteBlackboardStore:
            await sqlite_store.ensure_schema()
            return sqlite_store

        store = asyncio.run(_prepare())

    orchestrator, _ = create_demo_orchestrator(store=store)
    service = BlackboardHTTPService(orchestrator)
    service.run(host=host, port=port)


@app.command("init-sqlite-store")
def init_sqlite_store(
    db_path: str = typer.Argument(..., help="Path to SQLite blackboard database"),
) -> None:
    """Initialise the SQLite store schema."""

    store = SQLiteBlackboardStore(db_path)

    async def _init() -> None:
        await store.ensure_schema()
        await store.close()

    asyncio.run(_init())
    console.print(f"[green]Initialised SQLite blackboard at {db_path}[/green]")


@app.command("sqlite-maintenance")
def sqlite_maintenance(
    db_path: str = typer.Argument(..., help="Path to SQLite blackboard database"),
    delete_before: str | None = typer.Option(
        None, help="ISO timestamp; delete artifacts before this time"
    ),
    vacuum: bool = typer.Option(False, help="Run VACUUM after maintenance"),
) -> None:
    """Perform maintenance tasks for the SQLite store."""

    store = SQLiteBlackboardStore(db_path)

    async def _maintain() -> tuple[int, bool]:
        await store.ensure_schema()
        deleted = 0
        if delete_before is not None:
            try:
                before_dt = datetime.fromisoformat(delete_before)
            except ValueError as exc:  # pragma: no cover - Typer handles but defensive
                raise typer.BadParameter(
                    f"Invalid ISO timestamp: {delete_before}"
                ) from exc
            deleted = await store.delete_before(before_dt)
        if vacuum:
            await store.vacuum()
        await store.close()
        return deleted, vacuum

    deleted, vacuum_run = asyncio.run(_maintain())
    console.print(
        f"[yellow]Deleted {deleted} artifacts[/yellow]"
        if delete_before is not None
        else "[yellow]No deletions requested[/yellow]"
    )
    if vacuum_run:
        console.print("[yellow]VACUUM completed[/yellow]")


def main() -> None:
    app()


__all__ = ["app", "main"]
