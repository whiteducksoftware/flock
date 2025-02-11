"""Flock package initialization."""

from flock.config import TELEMETRY

tracer = TELEMETRY.setup_tracing()
