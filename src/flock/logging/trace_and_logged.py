"""A decorator that wraps a function in an OpenTelemetry span and logs its inputs, outputs, and exceptions."""

import functools
import inspect
import json

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

        # Handle primitives - these are already JSON-serializable
        if isinstance(value, (str, int, float, bool)):
            return value

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
                attributes[f"input.{param_name}"] = json.dumps(serialized, default=str)
            except Exception:
                # If JSON serialization fails, use string representation
                attributes[f"input.{param_name}"] = str(serialized)
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
            if not _trace_filter_config.should_trace(service_name, span_name):
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
                            "output.value", json.dumps(serialized_result, default=str)
                        )
                    except Exception as e:
                        span.set_attribute("output.value", str(result))
                        span.set_attribute("output.serialization_error", str(e))

                    # Set result type and metadata
                    if result is not None:
                        span.set_attribute("output.type", type(result).__name__)
                        if hasattr(result, "__len__"):
                            try:
                                span.set_attribute("output.length", len(result))
                            except TypeError:
                                pass

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
        if not _trace_filter_config.should_trace(service_name, span_name):
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
                        "output.value", json.dumps(serialized_result, default=str)
                    )
                except Exception as e:
                    span.set_attribute("output.value", str(result))
                    span.set_attribute("output.serialization_error", str(e))

                # Set result type and metadata
                if result is not None:
                    span.set_attribute("output.type", type(result).__name__)
                    if hasattr(result, "__len__"):
                        try:
                            span.set_attribute("output.length", len(result))
                        except TypeError:
                            pass

                span.set_status(Status(StatusCode.OK))
                logger.debug(f"{span_name} executed successfully")
                return result

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                logger.exception(f"Error in {span_name}", error=str(e))
                raise

    return wrapper
