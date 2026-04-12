"""Data models for the external agent runtime protocol.

SpawnConfig / SpawnResult / AgentOutcome form the lifecycle triple:
  configure -> spawn -> monitor -> outcome

ExternalAgentConfig describes a declared external agent registration.
ExternalSessionStore tracks session IDs for resume-capable agents.
SQLiteExternalSessionStore persists sessions to the blackboard database.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    import aiosqlite


# ---------------------------------------------------------------------------
# Spawn lifecycle models
# ---------------------------------------------------------------------------


@dataclass
class SpawnConfig:
    """Everything needed to launch an external agent process."""

    prompt: str
    working_dir: Path
    env_vars: dict[str, str] = field(default_factory=dict)
    session_id: str | None = None
    session_mode: Literal["new", "resume"] = "new"
    timeout: float = 1800.0  # 30 minutes default


@dataclass
class SpawnResult:
    """Handle returned after a successful spawn."""

    pid: int
    session_id: str
    process: asyncio.subprocess.Process


@dataclass
class AgentOutcome:
    """Terminal state after an external agent finishes (or crashes)."""

    success: bool
    returncode: int
    stdout: str
    stderr: str
    session_id: str


# ---------------------------------------------------------------------------
# Agent configuration & session tracking
# ---------------------------------------------------------------------------


@dataclass
class ExternalAgentConfig:
    """Declarative configuration for one external agent binding.

    Attributes:
        adapter_name: Name of the registered ExternalAgentRuntime adapter.
        working_dir: Filesystem path the agent process runs in.
        timeout: Max wall-clock seconds before we kill the process.
        session_mode: Whether to start fresh or resume an existing session.
        concurrency: How overlapping events for the same agent are handled.
            - serial: queue events, process one at a time (default)
            - parallel: spawn concurrent processes
            - coalesce: merge pending events, only run once
        env_vars: Extra environment variables injected into the process.
        guard: Placeholder for future GuardComponent reference.
    """

    adapter_name: str
    working_dir: Path
    timeout: float = 1800.0
    session_mode: Literal["new", "resume"] = "new"
    concurrency: Literal["serial", "parallel", "coalesce"] = "serial"
    env_vars: dict[str, str] = field(default_factory=dict)
    guard: Any | None = None  # Future: GuardComponent reference


@runtime_checkable
class SessionStoreProtocol(Protocol):
    """Protocol that both in-memory and SQLite session stores satisfy.

    The scheduler calls ``get`` and ``set`` from async worker methods.
    The in-memory store is synchronous; the SQLite store is async.
    Callers that accept the SQLite variant should ``await`` the result.
    """

    def get(self, agent_name: str, artifact_type: str) -> str | None: ...
    def set(self, agent_name: str, artifact_type: str, session_id: str) -> None: ...
    def clear(self, agent_name: str | None = None) -> None: ...


class ExternalSessionStore:
    """In-memory store mapping (agent_name, artifact_type) → session_id.

    Used by the scheduler to resolve resume sessions for agents that
    maintain conversational state across invocations.
    """

    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], str] = {}

    def get(self, agent_name: str, artifact_type: str) -> str | None:
        """Look up an existing session ID."""
        return self._sessions.get((agent_name, artifact_type))

    def set(self, agent_name: str, artifact_type: str, session_id: str) -> None:
        """Store or update a session ID."""
        self._sessions[(agent_name, artifact_type)] = session_id

    def clear(self, agent_name: str | None = None) -> None:
        """Clear sessions — optionally scoped to a single agent."""
        if agent_name is None:
            self._sessions.clear()
        else:
            keys_to_drop = [k for k in self._sessions if k[0] == agent_name]
            for k in keys_to_drop:
                del self._sessions[k]

    def __len__(self) -> int:
        return len(self._sessions)

    def __repr__(self) -> str:
        return f"ExternalSessionStore({len(self._sessions)} sessions)"


class SQLiteExternalSessionStore:
    """SQLite-backed session store that persists across restarts.

    Uses the same ``aiosqlite`` connection as :class:`SQLiteBlackboardStore`
    so sessions live in the shared blackboard database.

    All public methods are async.  The scheduler already runs inside async
    workers, so awaiting here is natural.
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def get(self, agent_name: str, artifact_type: str) -> str | None:
        """Look up an existing session ID from SQLite."""
        cursor = await self._conn.execute(
            "SELECT session_id FROM external_sessions "
            "WHERE agent_name = ? AND artifact_type = ?",
            (agent_name, artifact_type),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def set(
        self, agent_name: str, artifact_type: str, session_id: str
    ) -> None:
        """Store or update a session ID (UPSERT)."""
        await self._conn.execute(
            "INSERT OR REPLACE INTO external_sessions "
            "(agent_name, artifact_type, session_id, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (agent_name, artifact_type, session_id, datetime.now(UTC).isoformat()),
        )
        await self._conn.commit()

    async def clear(self, agent_name: str | None = None) -> None:
        """Clear sessions -- optionally scoped to a single agent."""
        if agent_name is None:
            await self._conn.execute("DELETE FROM external_sessions")
        else:
            await self._conn.execute(
                "DELETE FROM external_sessions WHERE agent_name = ?",
                (agent_name,),
            )
        await self._conn.commit()

    async def count(self) -> int:
        """Return the number of stored sessions."""
        cursor = await self._conn.execute(
            "SELECT COUNT(*) FROM external_sessions"
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    def __repr__(self) -> str:
        return "SQLiteExternalSessionStore()"
