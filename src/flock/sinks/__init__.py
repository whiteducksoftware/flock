"""Sinks: external systems as consumers on the blackboard (#618).

``Flock(endpoints={"myapp": Endpoint(...)})`` names the systems, and
``flock.sink(name).consumes(X).post("myapp:/path")`` delivers every ``X`` to
one of them. A sink publishes ``Delivered`` or ``DeliveryFailed`` for every
delivery, so the workflow, the dashboard and the trace see what went out.
"""

from flock.sinks.builder import SinkBuilder
from flock.sinks.endpoint import Bearer, Endpoint, Header, Hmac, SecretError
from flock.sinks.engine import SinkEngine, close_endpoints
from flock.sinks.models import Delivered, DeliveryFailed


__all__ = [
    "Bearer",
    "Delivered",
    "DeliveryFailed",
    "Endpoint",
    "Header",
    "Hmac",
    "SecretError",
    "SinkBuilder",
    "SinkEngine",
    "close_endpoints",
]
