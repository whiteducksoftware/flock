from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing():
    resource = Resource(attributes={"service.name": "flock-agent-framework"})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # Create a Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name="localhost",  # or the hostname where Jaeger is running
        agent_port=6831,  # default Jaeger agent port
    )

    provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    tracer = trace.get_tracer(__name__)
    return tracer
