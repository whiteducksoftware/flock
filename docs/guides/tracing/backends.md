# Tracing backends

Flock keeps its traces locally for the dashboard's trace viewer (`FLOCK_TRACE_FILE=true`) and
exports them over OTLP to any OpenTelemetry backend. This guide shows the settings for five of
them and what each shows of a Flock run. Every setting below was checked with a two-agent run
(a bug report goes to a `diagnostician`, its diagnosis to a `fixer`) against a local instance.

What Flock exports:

- every span of the run, with its inputs and outputs (see [auto-tracing](auto-tracing.md#span-attributes));
- one `LM.chat` span per model call in the OpenTelemetry GenAI conventions: model, provider,
  tokens and the agent (see [model calls](auto-tracing.md#model-calls-genai-spans));
- the run's correlation ID as `session.id` and `gen_ai.conversation.id`, so tools that group by
  session or thread put a run's traces together.

## The variables

Flock reads the standard OpenTelemetry variables:

| Variable | Meaning |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Base endpoint; setting it switches export on |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Full traces endpoint, used as given (wins over the base endpoint) |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` (default) or `http/protobuf`; over HTTP, Flock appends `/v1/traces` to the base endpoint |
| `OTEL_EXPORTER_OTLP_HEADERS` | Headers as `key=value` pairs, comma-separated and URL-encoded (a space is `%20`) |
| `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | `true` adds the messages of each model call to its `LM.chat` span (off by default) |

`FLOCK_TRACE_LEVEL`, `FLOCK_TRACE_SERVICES` and `FLOCK_TRACE_IGNORE` apply to exported spans too:
a filtered operation creates no span at all.

## What each tool shows

Model calls are the `LM.chat` spans. Flock exports each call's tokens, not a cost: the Cost column
is the tool's own estimate from its price list. Flock's own cost is per agent run
(`flock.usage.cost_usd`, see [auto-tracing](auto-tracing.md#model-calls-genai-spans)).

| Tool | Model calls | Tokens | Cost | A run grouped as | Checked with |
|---|---|---|---|---|---|
| [Langfuse](#langfuse) | Generations, with model and parameters | Per call and per session | When the model is in Langfuse's price list | Session | Langfuse v4, self-hosted |
| [Opik](#opik) | LLM spans, with model and provider | Per call and per trace | Estimated per call | Thread | Opik (2026-10), self-hosted |
| [Arize Phoenix](#arize-phoenix) | LLM spans, with model and provider | Per call | Not checked | `session.id` set | Phoenix 20.26 |
| [Jaeger](#jaeger) | Spans, the `gen_ai.*` attributes as tags | As tags | No | No | Jaeger 2.22 |
| [MLflow](#mlflow) | Spans of the trace | Per trace | Not checked | No | MLflow 3.17 |

## Langfuse

Langfuse takes OTLP over HTTP at `/api/public/otel` and authenticates with the project's key
pair as HTTP basic auth:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:3000/api/public/otel   # your Langfuse host
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic%20$(printf '%s' 'pk-lf-...:sk-lf-...' | base64 | tr -d '\n')"
```

What you see:

- each model call as a generation with its model, temperature, max tokens and tokens;
- the cost of a call when Langfuse knows the model's price; for a model it does not know, add a
  model definition in Langfuse's settings;
- a run as one session, with its traces and their tokens;
- with `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`, the messages of each call as a
  chat in the session view.

Local setup: Langfuse's [`docker-compose.yml`](https://github.com/langfuse/langfuse/blob/main/docker-compose.yml)
starts the web app on port 3000. Replace the values marked `CHANGEME` with secrets of your own;
`LANGFUSE_INIT_*` creates an organisation, a project, its keys and a user at the first start.

## Opik

Opik takes OTLP over HTTP at `/api/v1/private/otel`. The `projectName` header chooses the project:

```bash
# Self-hosted
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:5173/api/v1/private/otel
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_HEADERS="projectName=my-flock-app"

# Opik Cloud (from Opik's documentation)
export OTEL_EXPORTER_OTLP_ENDPOINT=https://www.comet.com/opik/api/v1/private/otel
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=<api key>,Comet-Workspace=<workspace>,projectName=my-flock-app"
```

What you see:

- each model call as an LLM span with its model, provider, tokens and an estimated cost, and the
  totals per trace;
- a run as one thread (Opik groups by `gen_ai.conversation.id`).

Local setup: in Opik's repository, `deployment/docker-compose` starts it with the profile `opik`
(or `./opik.sh`); the frontend serves on port 5173. The `docker-compose.override.yaml` next to it
publishes the database ports (MySQL, Redis, ClickHouse, MinIO); leave it out when other stacks on
the machine use those ports. `OPIK_USAGE_REPORT_ENABLED=false` switches off usage reporting.

## Arize Phoenix

Phoenix takes OTLP over HTTP on its web port:

```bash
docker run -p 6006:6006 arizephoenix/phoenix

export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:6006
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
```

What you see: each model call as an LLM span with its model, provider and tokens (Phoenix reads
the GenAI attributes), the other spans as general spans, and `session.id` on the spans of a run.
The traces land in Phoenix's `default` project.

## Jaeger

Jaeger takes OTLP over gRPC on port 4317, which is Flock's default protocol:

```bash
docker run -p 16686:16686 -p 4317:4317 jaegertracing/jaeger

export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

What you see: every span of the run under the service `flock-auto-trace`, with all attributes as
tags, `LM.chat` and its `gen_ai.*` attributes included. Jaeger has no view of its own for model
calls; it is the general-purpose timeline. The UI is on port 16686.

## MLflow

MLflow's tracking server (3.x) takes OTLP over HTTP at `/v1/traces` and needs the experiment the
traces belong to as a header:

```bash
mlflow server --port 5001 --backend-store-uri sqlite:///mlflow.db

export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:5001
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_HEADERS="x-mlflow-experiment-id=<experiment id>"
```

What you see: each trace in the experiment's traces, with the token usage of the trace.

## Several backends at once

The variables configure one OTLP exporter. To send to several backends, run an
[OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) that fans out, or add an
exporter per backend to the tracer provider in your code, after Flock has set it up:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from flock import Flock

flock = Flock()  # auto-tracing has set up the tracer provider
provider = trace.get_tracer_provider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
    endpoint="http://localhost:5173/api/v1/private/otel/v1/traces",
    headers={"projectName": "my-flock-app"},
)))
```

An endpoint passed in code is used as given: write the full traces path.
