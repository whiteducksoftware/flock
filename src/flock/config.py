# flock/config.py
from decouple import config

from flock.core.logging.telemetry import TelemetryConfig

# -- Connection and External Service Configurations --
TEMPORAL_SERVER_URL = config("TEMPORAL_SERVER_URL", "localhost:7233")
DEFAULT_MODEL = config("DEFAULT_MODEL", "openai/gpt-4o")


# API Keys and related settings
TAVILY_API_KEY = config("TAVILY_API_KEY", "")
GITHUB_PAT = config("GITHUB_PAT", "")
GITHUB_REPO = config("GITHUB_REPO", "")
GITHUB_USERNAME = config("GITHUB_USERNAME", "")

# -- Debugging and Logging Configurations --
LOCAL_DEBUG = config("LOCAL_DEBUG", True)
LOG_LEVEL = config("LOG_LEVEL", "DEBUG")
LOGGING_DIR = config("LOGGING_DIR", "logs")

OTEL_SERVICE_NAME = config("OTL_SERVICE_NAME", "otel-flock")
JAEGER_ENDPOINT = config(
    "JAEGER_ENDPOINT", "http://localhost:14268/api/traces"
)  # Default gRPC endpoint for Jaeger
JAEGER_TRANSPORT = config(
    "JAEGER_TRANSPORT", "http"
).lower()  # Options: "grpc" or "http"
OTEL_SQL_DATABASE_NAME = config("OTEL_SQL_DATABASE", "flock_events.db")
OTEL_FILE_NAME = config("OTEL_FILE_NAME", "flock_events.jsonl")
OTEL_ENABLE_SQL: bool = config("OTEL_ENABLE_SQL", True) == "True"
OTEL_ENABLE_FILE: bool = config("OTEL_ENABLE_FILE", True) == "True"
OTEL_ENABLE_JAEGER: bool = config("OTEL_ENABLE_JAEGER", False) == "True"


TELEMETRY = TelemetryConfig(
    OTEL_SERVICE_NAME,
    JAEGER_ENDPOINT,
    JAEGER_TRANSPORT,
    LOGGING_DIR,
    OTEL_FILE_NAME,
    OTEL_SQL_DATABASE_NAME,
    OTEL_ENABLE_JAEGER,
    OTEL_ENABLE_FILE,
    OTEL_ENABLE_SQL,
)
