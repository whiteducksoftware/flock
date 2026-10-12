"""``flock.sink(name)``: an external system as a consumer on the blackboard."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from flock.core.artifacts import Artifact
from flock.sinks.endpoint import resolve_target
from flock.sinks.engine import SinkEngine
from flock.sinks.models import Delivered, DeliveryFailed


if TYPE_CHECKING:
    from pydantic import BaseModel

    from flock.core import Flock
    from flock.core.agent import AgentBuilder

# A sink waits on its target, not on a model: its runs never queue behind
# each other, so a delivery waiting for its turn holds no slot another needs
_CONCURRENT_DELIVERIES = 1_000_000


class SinkBuilder:
    """Declares what a sink consumes and where it delivers.

    ``consumes()`` takes everything an agent's subscription takes (``where=``,
    ``from_agents=``, ``tags=``, ``batch=``, ``join=``, ...); ``post()``,
    ``put()`` or ``patch()`` names the target and registers the sink.

    Examples:
        >>> flock = Flock(endpoints={"myapp": Endpoint("https://myapp.example")})
        >>> flock.sink("billing-api").consumes(Reply).post("myapp:/billing")
    """

    def __init__(self, orchestrator: Flock, name: str) -> None:
        self._orchestrator = orchestrator
        self._name = name
        self._subscriptions: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self._labels: tuple[str, ...] = ()
        self._tenant: str | None = None
        self._description: str | None = None
        self._agent: AgentBuilder | None = None

    @property
    def name(self) -> str:
        return self._name

    def consumes(self, *types: Any, **options: Any) -> SinkBuilder:
        """Subscribe like an agent; several calls are OR."""
        self._subscriptions.append((types, options))
        return self

    def labels(self, *labels: str) -> SinkBuilder:
        """Labels that let the sink see ``LabelledVisibility`` artifacts."""
        self._labels = (*self._labels, *labels)
        return self

    def tenant(self, tenant_id: str) -> SinkBuilder:
        """The tenant whose ``TenantVisibility`` artifacts the sink sees."""
        self._tenant = tenant_id
        return self

    def description(self, text: str) -> SinkBuilder:
        self._description = text
        return self

    def post(
        self,
        target: str,
        *,
        body: Callable[[Artifact], Any] | None = None,
        response: type[BaseModel] | None = None,
    ) -> SinkBuilder:
        """Deliver with HTTP POST.

        Args:
            target: ``"endpoint:/path"`` on an endpoint of
                ``Flock(endpoints=...)``, or a full ``http(s)://`` URL.
            body: Maps each artifact to the JSON the target expects; by
                default the artifact's envelope (``id``, ``type``,
                ``payload``, ``produced_by``, ``correlation_id``,
                ``created_at``). A batch is sent as a list.
            response: Publishes the target's JSON answer as this type.
        """
        return self._deliver("POST", target, body, response)

    def put(
        self,
        target: str,
        *,
        body: Callable[[Artifact], Any] | None = None,
        response: type[BaseModel] | None = None,
    ) -> SinkBuilder:
        """Deliver with HTTP PUT; arguments as for :meth:`post`."""
        return self._deliver("PUT", target, body, response)

    def patch(
        self,
        target: str,
        *,
        body: Callable[[Artifact], Any] | None = None,
        response: type[BaseModel] | None = None,
    ) -> SinkBuilder:
        """Deliver with HTTP PATCH; arguments as for :meth:`post`."""
        return self._deliver("PATCH", target, body, response)

    def _deliver(
        self,
        method: str,
        target: str,
        body: Callable[[Artifact], Any] | None,
        response: type[BaseModel] | None,
    ) -> SinkBuilder:
        from flock.core.agent import AgentBuilder
        from flock.core.context_provider import EmptyContextProvider

        if self._agent is not None:
            raise ValueError(
                f"Sink '{self._name}' already delivers; a sink has one target."
            )
        if not self._subscriptions:
            raise ValueError(
                f"Sink '{self._name}': declare what it consumes before its "
                "target, e.g. flock.sink(name).consumes(Reply).post(...)."
            )
        resolved = resolve_target(target, self._orchestrator.endpoints)

        # Registered only now, complete: a sink never runs without its target
        agent = AgentBuilder(self._orchestrator, self._name)
        for types, options in self._subscriptions:
            agent.consumes(*types, **options)
        if self._labels:
            agent.labels(*self._labels)
        if self._tenant is not None:
            agent.tenant(self._tenant)
        agent.description(
            self._description or f"Delivers to {resolved.declared} ({method})"
        )
        agent.with_context(EmptyContextProvider())
        # Set on the agent: the builder warns about values this high, meant for LLMs
        agent._agent.set_max_concurrency(_CONCURRENT_DELIVERIES)
        receipts = (Delivered, DeliveryFailed) + ((response,) if response else ())
        agent.publishes(*receipts)
        for output in agent._agent.output_groups[-1].outputs:
            output.inherit_visibility = True
            output.optional = True
        agent._agent.engines.append(
            SinkEngine(method=method, target=resolved, body=body, response=response)
        )
        self._agent = agent
        return self


__all__ = ["SinkBuilder"]
