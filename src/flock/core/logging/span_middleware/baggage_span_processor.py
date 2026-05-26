from opentelemetry.baggage import get_baggage
from opentelemetry.sdk.trace import SpanProcessor


class BaggageAttributeSpanProcessor(SpanProcessor):
    """A custom span processor that, on span start, inspects the baggage items from the parent context
    and attaches specified baggage keys as attributes on the span.
    """

    def __init__(self, baggage_keys=None):
        # baggage_keys: list of baggage keys to attach to spans (e.g. ["session_id", "run_id"])
        if baggage_keys is None:
            baggage_keys = []
        self.baggage_keys = baggage_keys

    def on_start(self, span, parent_context):
        # For each desired key, look up its value in the parent context baggage and set it as an attribute.
        for key in self.baggage_keys:
            value = get_baggage(key, context=parent_context)
            if value is not None:
                span.set_attribute(key, value)

    def on_end(self, span):
        # No action required on span end for this processor.
        pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000):
        pass
