"""Flock package initialization."""

from opentelemetry import trace

from flock.config import TELEMETRY

tracer = TELEMETRY.setup_tracing()
tracer = trace.get_tracer(__name__)
