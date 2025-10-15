from __future__ import annotations


"""Artifact visibility policies."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, PrivateAttr


if TYPE_CHECKING:
    from collections.abc import Iterable


class AgentIdentity(BaseModel):
    """Minimal identity information about an agent for visibility checks."""

    name: str
    labels: set[str] = Field(default_factory=set)
    tenant_id: str | None = None


class Visibility(BaseModel):
    """Base visibility contract."""

    kind: Literal["Public", "Private", "Labelled", "Tenant", "After"]

    def allows(self, agent: AgentIdentity, *, now: datetime | None = None) -> bool:
        raise NotImplementedError


class PublicVisibility(Visibility):
    kind: Literal["Public"] = "Public"

    def allows(
        self, agent: AgentIdentity, *, now: datetime | None = None
    ) -> bool:  # pragma: no cover - trivial
        return True


class PrivateVisibility(Visibility):
    kind: Literal["Private"] = "Private"
    agents: set[str] = Field(default_factory=set)

    def allows(self, agent: AgentIdentity, *, now: datetime | None = None) -> bool:
        return agent.name in self.agents


class LabelledVisibility(Visibility):
    kind: Literal["Labelled"] = "Labelled"
    required_labels: set[str] = Field(default_factory=set)

    def allows(self, agent: AgentIdentity, *, now: datetime | None = None) -> bool:
        return self.required_labels.issubset(agent.labels)


class TenantVisibility(Visibility):
    kind: Literal["Tenant"] = "Tenant"
    tenant_id: str | None = None

    def allows(self, agent: AgentIdentity, *, now: datetime | None = None) -> bool:
        if self.tenant_id is None:
            return True
        return agent.tenant_id == self.tenant_id


class AfterVisibility(Visibility):
    kind: Literal["After"] = "After"
    ttl: timedelta = Field(default=timedelta())
    then: Visibility | None = None
    _created_at: datetime = PrivateAttr(default_factory=lambda: datetime.now(UTC))

    def allows(self, agent: AgentIdentity, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        if now - self._created_at >= self.ttl:
            if self.then:
                return self.then.allows(agent, now=now)
            return True
        return False


def ensure_visibility(value: Visibility | None) -> Visibility:
    if value is None:
        return PublicVisibility()
    return value


def only_for(*agent_names: str) -> PrivateVisibility:
    return PrivateVisibility(agents=set(agent_names))


def agents_from_names(names: Iterable[str]) -> set[str]:  # pragma: no cover - helper
    return set(names)


__all__ = [
    "AfterVisibility",
    "AgentIdentity",
    "LabelledVisibility",
    "PrivateVisibility",
    "PublicVisibility",
    "TenantVisibility",
    "Visibility",
    "ensure_visibility",
    "only_for",
]
