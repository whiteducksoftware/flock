"""A decorator that wraps a function in an OpenTelemetry span and logs its inputs, outputs, and exceptions."""

import functools
import inspect

from opentelemetry import trace

from flock.core.logging.logging import get_logger

logger = get_logger("tools")
tracer = trace.get_tracer(__name__)


def traced_and_logged(func):
    """A decorator that wraps a function in an OpenTelemetry span.

    and logs its inputs,
    outputs, and exceptions. Supports both synchronous and asynchronous functions.
    """
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(func.__name__) as span:
                span.set_attribute("args", str(args))
                span.set_attribute("kwargs", str(kwargs))
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("result", str(result))
                    logger.debug(
                        f"{func.__name__} executed successfully", result=result
                    )
                    return result
                except Exception as e:
                    logger.error(f"Error in {func.__name__}", error=str(e))
                    span.record_exception(e)
                    raise

        return async_wrapper
    else:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(func.__name__) as span:
                span.set_attribute("args", str(args))
                span.set_attribute("kwargs", str(kwargs))
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("result", str(result))
                    logger.debug(
                        f"{func.__name__} executed successfully", result=result
                    )
                    return result
                except Exception as e:
                    logger.error(f"Error in {func.__name__}", error=str(e))
                    span.record_exception(e)
                    raise

        return wrapper
