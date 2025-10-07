"""A decorator that wraps a function in an OpenTelemetry span and logs its inputs, outputs, and exceptions."""

import functools
import inspect

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from flock.logging.logging import get_logger


logger = get_logger("tools")
tracer = trace.get_tracer(__name__)


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

            with tracer.start_as_current_span(span_name) as span:
                # Set all extracted attributes
                for key, value in attributes.items():
                    span.set_attribute(key, value)

                try:
                    result = await func(*args, **kwargs)

                    # Set result type (but not full result to avoid huge spans)
                    if result is not None:
                        span.set_attribute("result.type", type(result).__name__)
                        if hasattr(result, "__len__"):
                            try:
                                span.set_attribute("result.length", len(result))
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

        with tracer.start_as_current_span(span_name) as span:
            # Set all extracted attributes
            for key, value in attributes.items():
                span.set_attribute(key, value)

            try:
                result = func(*args, **kwargs)

                # Set result type (but not full result to avoid huge spans)
                if result is not None:
                    span.set_attribute("result.type", type(result).__name__)
                    if hasattr(result, "__len__"):
                        try:
                            span.set_attribute("result.length", len(result))
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
