"""A decorator that wraps a function in an OpenTelemetry span and logs its inputs, outputs, and exceptions."""

import functools
import inspect
import json
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from flock.logging.logging import get_logger


logger = get_logger("tools")
tracer = trace.get_tracer(__name__)


# Global trace filter configuration
class TraceFilterConfig:
    """Configuration for filtering which operations get traced."""

    def __init__(self):
        self.services: set[str] | None = None  # Whitelist: only trace these services
        self.ignore_operations: set[str] = (
            set()
        )  # Blacklist: never trace these operations
        # FLOCK_TRACE_LEVEL: `agents` traces agent work, `all` also Flock's internals
        self.level: str = "agents"
        # FLOCK_TRACE_MAX_ATTRIBUTE_BYTES: longer inputs and outputs are cut (0: no cap)
        self.max_attribute_bytes: int = 4096

    def hides(self, owner: object) -> bool:
        """Whether a call on ``owner`` is one of Flock's internals left out at this level.

        Classes marked ``__trace_level__ = "all"`` (and their subclasses) are
        checked at call time too, since the hooks they inherit were wrapped in
        their base class.
        """
        return (
            self.level != "all"
            and getattr(type(owner), "__trace_level__", "agents") == "all"
        )

    def should_trace(self, service: str, operation: str) -> bool:
        """Check if an operation should be traced based on filters.

        Args:
            service: Service name (e.g., "Flock", "Agent")
            operation: Full operation name (e.g., "Flock.publish")

        Returns:
            True if should trace, False otherwise
        """
        # Check blacklist first (highest priority)
        if operation in self.ignore_operations:
            return False

        # Check whitelist if configured
        if self.services is not None:
            service_lower = service.lower()
            if service_lower not in self.services:
                return False

        return True


# Global instance
_trace_filter_config = TraceFilterConfig()


def capped(value: str) -> str:
    """An input or output attribute within FLOCK_TRACE_MAX_ATTRIBUTE_BYTES.

    A longer value becomes JSON that says it was cut and how large it was,
    with as much of its start as ``preview`` as fits in the cap, escaping and
    marker included; the cut never splits a character.
    """
    limit = _trace_filter_config.max_attribute_bytes
    encoded = value.encode()
    if limit <= 0 or len(encoded) <= limit:
        return value

    def marker(preview: str) -> str:
        return json.dumps(
            {"truncated": True, "bytes": len(encoded), "preview": preview},
            ensure_ascii=False,
        )

    # The value's start that fits next to the marker; escaping can make the
    # preview longer than its bytes, so it shrinks until the whole fits
    room = max(0, limit - len(marker("").encode()))
    preview = encoded[:room].decode(errors="ignore")
    while preview:
        excess = len(marker(preview).encode()) - limit
        if excess <= 0:
            break
        preview = preview[: len(preview) - max(1, excess // 6)]
    return marker(preview)


def run_attributes(correlation_id: object) -> dict[str, str]:
    """A run's correlation as the attributes observability tools group traces by
    (#681): Langfuse sessions read ``session.id``, Opik threads
    ``gen_ai.conversation.id``."""
    value = str(correlation_id)
    return {"session.id": value, "gen_ai.conversation.id": value}


def _context_run(func: Any, args: tuple, kwargs: dict[str, Any]) -> Any:
    """The run a call's context names: the argument bound to ``ctx``, or a Flock
    ``Context`` under another name. A payload names no run, even with
    ``correlation_id`` and ``task_id`` fields of its own (#681)."""
    from flock.utils.runtime import (
        Context,
    )  # at call time: runtime imports Flock's core

    try:
        bound = dict(inspect.signature(func).bind_partial(*args, **kwargs).arguments)
    except (TypeError, ValueError):
        bound = dict(kwargs)
    candidates = [bound.get("ctx")]
    candidates += [value for value in bound.values() if isinstance(value, Context)]
    for value in candidates:
        run = getattr(value, "correlation_id", None)
        if run:
            return run
    return None


def _result_correlation(result: Any) -> str | None:
    """The one correlation of what a call returned: an artifact's, or the one
    that several artifacts share."""
    items = result if isinstance(result, list | tuple) else [result]
    found = {str(c) for item in items if (c := getattr(item, "correlation_id", None))}
    return found.pop() if len(found) == 1 else None


def _record_run(span: Any, attributes: dict[str, Any], result: Any) -> None:
    """Put the run on a span whose context did not name it, from its result
    (``Flock.publish`` creates the correlation). The result's run also replaces
    a ``correlation_id`` read from a payload field of the same name."""
    if "session.id" in attributes:
        return
    correlation = _result_correlation(result)
    if correlation:
        span.set_attribute("correlation_id", correlation)
        span.set_attributes(run_attributes(correlation))


def _serialize_value(value, max_depth=10, current_depth=0):
    """Serialize a value to JSON-compatible format for span attributes.

    Args:
        value: The value to serialize
        max_depth: Maximum recursion depth to prevent infinite loops
        current_depth: Current recursion depth

    Returns:
        A JSON-serializable representation of the value
    """
    if current_depth >= max_depth:
        return f"<max_depth_reached: {type(value).__name__}>"

    try:
        # Handle None
        if value is None:
            return None

        # Image data is described, not copied into every span
        if isinstance(value, str):
            from flock.core.image import describe_image_data

            return describe_image_data(value) or value

        # Handle primitives - these are already JSON-serializable
        if isinstance(value, (int, float, bool)):
            return value

        # An artifact in short: what it is, who made it and what it says
        # (its visibility, tags and times are on the blackboard, if it got there)
        from flock.core.artifacts import Artifact

        if isinstance(value, Artifact):
            return {
                "artifact": value.type,
                "id": str(value.id),
                "produced_by": value.produced_by,
                "payload": _serialize_value(
                    value.payload, max_depth, current_depth + 1
                ),
            }

        # Handle lists/tuples
        if isinstance(value, (list, tuple)):
            return [
                _serialize_value(item, max_depth, current_depth + 1) for item in value
            ]

        # Handle dicts
        if isinstance(value, dict):
            return {
                str(k): _serialize_value(v, max_depth, current_depth + 1)
                for k, v in value.items()
            }

        # Handle sets
        if isinstance(value, set):
            return [
                _serialize_value(item, max_depth, current_depth + 1) for item in value
            ]

        # For custom objects with __dict__, serialize their attributes
        if hasattr(value, "__dict__"):
            class_name = value.__class__.__name__
            try:
                obj_dict = {}
                for k, v in value.__dict__.items():
                    # Skip private attributes and methods
                    if k.startswith("_"):
                        continue
                    # Skip methods and callables
                    if callable(v):
                        continue
                    try:
                        obj_dict[k] = _serialize_value(v, max_depth, current_depth + 1)
                    except Exception:
                        obj_dict[k] = f"<error serializing {k}>"

                return {
                    "__class__": class_name,
                    "__module__": value.__class__.__module__,
                    **obj_dict,
                }
            except Exception as e:
                return {"__class__": class_name, "__error__": str(e)}

        # For objects with a useful string representation
        result = str(value)
        # If the string is too long (> 5000 chars), truncate it
        if len(result) > 5000:
            return result[:5000] + "... (string truncated at 5000 chars)"
        return result

    except Exception as e:
        # If all else fails, return type information with error
        return {"__type__": type(value).__name__, "__error__": str(e)}


def _extract_span_attributes(func, args, kwargs):
    """Extract useful attributes from function arguments for OTEL spans.

    Returns a dict of attributes and a display name for the span.
    """
    attributes = {}
    span_name = func.__name__

    # Try to get class name if this is a method
    if args and hasattr(args[0], "__class__"):
        obj = args[0]
        class_name = obj.__class__.__name__
        span_name = f"{class_name}.{func.__name__}"
        attributes["class"] = class_name

        # Extract agent-specific attributes
        if hasattr(obj, "name"):
            attributes["agent.name"] = str(obj.name)
        if hasattr(obj, "description"):
            attributes["agent.description"] = str(obj.description)[:200]  # Truncate

    # Extract context attributes (correlation_id, task_id)
    for arg_name, arg_value in kwargs.items():
        if arg_name == "ctx" and hasattr(arg_value, "correlation_id"):
            if arg_value.correlation_id:
                attributes["correlation_id"] = str(arg_value.correlation_id)
            if hasattr(arg_value, "task_id"):
                attributes["task_id"] = str(arg_value.task_id)

    # Check positional args for Context
    for arg in args[1:]:  # Skip self
        if hasattr(arg, "correlation_id"):
            if arg.correlation_id:
                attributes["correlation_id"] = str(arg.correlation_id)
            if hasattr(arg, "task_id"):
                attributes["task_id"] = str(arg.task_id)
            break

    run = _context_run(func, args, kwargs)
    if run:
        attributes.update(run_attributes(run))

    # Add function metadata
    attributes["function"] = func.__name__
    attributes["module"] = func.__module__

    # Capture input arguments (skip 'self' for methods)
    try:
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        # Serialize arguments
        for param_name, param_value in bound_args.arguments.items():
            # Skip 'self' and 'cls'
            if param_name in ("self", "cls"):
                continue
            # Serialize the argument value to JSON-compatible format
            serialized = _serialize_value(param_value)
            # Convert to JSON string for OTEL attribute storage
            try:
                attributes[f"input.{param_name}"] = capped(
                    json.dumps(serialized, default=str)
                )
            except Exception:
                # If JSON serialization fails, use string representation
                attributes[f"input.{param_name}"] = capped(str(serialized))
    except Exception as e:
        # If we can't capture inputs, just note that
        attributes["input.error"] = str(e)

    return attributes, span_name


def traced_and_logged(func):
    """A decorator that wraps a function in an OpenTelemetry span.

    Creates proper parent-child span relationships and extracts relevant
    attributes for observability in Grafana/Jaeger.

    Automatically extracts:
    - Agent name and description
    - Correlation ID and task ID from Context
    - Class and method names
    - Exception information

    Supports both synchronous and asynchronous functions.
    """
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            attributes, span_name = _extract_span_attributes(func, args, kwargs)

            # Check if we should trace this operation
            service_name = span_name.split(".")[0] if "." in span_name else span_name
            if not _trace_filter_config.should_trace(service_name, span_name) or (
                args and _trace_filter_config.hides(args[0])
            ):
                # Skip tracing, just call the function
                return await func(*args, **kwargs)

            with tracer.start_as_current_span(span_name) as span:
                # Set all extracted attributes
                for key, value in attributes.items():
                    span.set_attribute(key, value)

                try:
                    result = await func(*args, **kwargs)

                    # Capture output value as JSON
                    try:
                        serialized_result = _serialize_value(result)
                        span.set_attribute(
                            "output.value",
                            capped(json.dumps(serialized_result, default=str)),
                        )
                    except Exception as e:
                        span.set_attribute("output.value", capped(str(result)))
                        span.set_attribute("output.serialization_error", str(e))

                    # Set result type and metadata
                    if result is not None:
                        span.set_attribute("output.type", type(result).__name__)
                        if hasattr(result, "__len__"):
                            try:
                                span.set_attribute("output.length", len(result))
                            except TypeError:
                                pass

                    _record_run(span, attributes, result)
                    span.set_status(Status(StatusCode.OK))
                    logger.debug(f"{span_name} executed successfully")
                    return result

                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    logger.exception(f"Error in {span_name}", error=str(e))
                    raise

        return async_wrapper

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        attributes, span_name = _extract_span_attributes(func, args, kwargs)

        # Check if we should trace this operation
        service_name = span_name.split(".")[0] if "." in span_name else span_name
        if not _trace_filter_config.should_trace(service_name, span_name) or (
            args and _trace_filter_config.hides(args[0])
        ):
            # Skip tracing, just call the function
            return func(*args, **kwargs)

        with tracer.start_as_current_span(span_name) as span:
            # Set all extracted attributes
            for key, value in attributes.items():
                span.set_attribute(key, value)

            try:
                result = func(*args, **kwargs)

                # Capture output value as JSON
                try:
                    serialized_result = _serialize_value(result)
                    span.set_attribute(
                        "output.value",
                        capped(json.dumps(serialized_result, default=str)),
                    )
                except Exception as e:
                    span.set_attribute("output.value", capped(str(result)))
                    span.set_attribute("output.serialization_error", str(e))

                # Set result type and metadata
                if result is not None:
                    span.set_attribute("output.type", type(result).__name__)
                    if hasattr(result, "__len__"):
                        try:
                            span.set_attribute("output.length", len(result))
                        except TypeError:
                            pass

                _record_run(span, attributes, result)
                span.set_status(Status(StatusCode.OK))
                logger.debug(f"{span_name} executed successfully")
                return result

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                logger.exception(f"Error in {span_name}", error=str(e))
                raise

    return wrapper
