"""FLOCK_TRACE_LEVEL: agent work by default, Flock's internals on request (#601)."""

import pytest

from flock.logging import auto_trace, trace_and_logged
from flock.logging.auto_trace import AutoTracedMeta, trace_level
from flock.logging.trace_and_logged import _trace_filter_config


pytestmark = pytest.mark.skipif(
    not auto_trace.ENABLE_AUTO_TRACE, reason="auto-tracing is off"
)


def traced(method) -> bool:
    return getattr(method, "_traced", False)


def _classes(level: str, monkeypatch):
    """A class traced only at `all`, and one with a single method only at `all`."""
    monkeypatch.setattr(_trace_filter_config, "level", level)

    class InternalHelper(metaclass=AutoTracedMeta):
        __trace_level__ = "all"

        def hook(self):
            return "hook"

    class Workflow(metaclass=AutoTracedMeta):
        def work(self):
            return "work"

        @trace_level("all")
        def register(self):
            return "register"

    return InternalHelper, Workflow


def test_the_agents_level_leaves_internals_untraced(monkeypatch):
    internal, workflow = _classes("agents", monkeypatch)

    assert not traced(internal.hook)
    assert traced(workflow.work)
    assert not traced(workflow.register)
    # Untraced methods still work
    assert internal().hook() == "hook"
    assert workflow().register() == "register"


def test_the_all_level_traces_everything(monkeypatch):
    internal, workflow = _classes("all", monkeypatch)

    assert traced(internal.hook)
    assert traced(workflow.work)
    assert traced(workflow.register)


@pytest.mark.parametrize(
    ("value", "level"),
    [
        ("agents", "agents"),
        ("ALL", "all"),
        (" all ", "all"),
        ("", "agents"),
        ("verbose", "agents"),
    ],
)
def test_the_level_comes_from_the_environment(monkeypatch, value, level):
    monkeypatch.setenv("FLOCK_TRACE_LEVEL", value)

    assert auto_trace._trace_level_from_env() == level


def test_flock_traces_agent_work_and_leaves_its_internals_at_the_default_level():
    if _trace_filter_config.level != "agents":
        pytest.skip("FLOCK_TRACE_LEVEL is set for this run")
    from flock import Flock
    from flock.api.collector import DashboardEventCollector
    from flock.api.graph_builder import GraphAssembler
    from flock.components.orchestrator import (
        ActivationComponent,
        BuiltinCollectionComponent,
        CircuitBreakerComponent,
        DeduplicationComponent,
    )
    from flock.components.orchestrator.scheduling.timer import TimerComponent
    from flock.core.agent import Agent

    # Workflow roots and agent work
    for method in (Flock.publish, Flock.invoke, Flock.run_until_idle, Flock.traced_run):
        assert traced(method), method
    assert traced(Agent.execute)
    # Building and registering
    for method in (Flock.agent, Flock.register_agent, Flock.add_component, Flock.serve):
        assert not traced(method), method
    # The dashboard serving itself
    assert not traced(GraphAssembler.build_snapshot)
    assert not traced(DashboardEventCollector.on_post_publish)
    # The built-in orchestrator components' hooks
    for component in (
        ActivationComponent,
        BuiltinCollectionComponent,
        CircuitBreakerComponent,
        DeduplicationComponent,
        TimerComponent,
    ):
        hooks = [
            getattr(component, name)
            for name in vars(component)
            if name.startswith("on_")
        ]
        assert hooks, component
        assert not any(traced(hook) for hook in hooks), component


class _Recorder:
    """A tracer that records the spans started."""

    def __init__(self):
        self.names: list[str] = []

    def start_as_current_span(self, name):
        import contextlib
        from unittest.mock import MagicMock

        self.names.append(name)
        return contextlib.nullcontext(MagicMock())


@pytest.mark.parametrize(
    ("level", "spans"), [("agents", []), ("all", ["Internal.hook"])]
)
async def test_hooks_an_internal_class_inherits_follow_its_level(
    monkeypatch, level, spans
):
    monkeypatch.setattr(_trace_filter_config, "level", "all")

    class Base(metaclass=AutoTracedMeta):
        async def hook(self):
            return "hook"

    class Internal(Base):
        __trace_level__ = "all"

    recorder = _Recorder()
    monkeypatch.setattr(trace_and_logged, "tracer", recorder)
    monkeypatch.setattr(_trace_filter_config, "level", level)

    assert await Internal().hook() == "hook"
    assert recorder.names == spans


@pytest.mark.parametrize(("level", "tracing"), [("agents", False), ("all", True)])
def test_the_server_traces_its_requests_at_the_all_level_only(
    monkeypatch, level, tracing
):
    from flock import Flock
    from flock.api.service import BlackboardHTTPService

    monkeypatch.setattr(_trace_filter_config, "level", level)

    assert BlackboardHTTPService(Flock()).app._telemetry.get("tracing") is tracing
