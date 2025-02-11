# flock/config.py
import os

from flock.core.logging.telemetry import TelemetryConfig

# -- Connection and External Service Configurations --
TEMPORAL_SERVER_URL = os.getenv("TEMPORAL_SERVER_URL", "localhost:7233")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-4o")


# API Keys and related settings
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GITHUB_PAT = os.getenv("GITHUB_PAT", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")

# -- Debugging and Logging Configurations --
LOCAL_DEBUG = os.getenv("LOCAL_DEBUG", "0") == "1"
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")

OTEL_SERVICE_NAME = os.getenv("OTL_SERVICE_NAME", "otel-flock")
JAEGER_ENDPOINT = os.getenv(
    "JAEGER_ENDPOINT", "http://localhost:14268/api/traces"
)  # Default gRPC endpoint for Jaeger
JAEGER_TRANSPORT = os.getenv(
    "JAEGER_TRANSPORT", "http"
).lower()  # Options: "grpc" or "http"
OTEL_SQL_PATH = os.getenv("OTEL_SQL_PATH", "sqlite:///otel.db")
OTEL_FILE_PATH = os.getenv("OTEL_FILE_PATH", "telemetry.json")
OTEL_ENABLE_SQL = os.getenv("OTEL_ENABLE_SQL", "FALSE") == "1"
OTEL_ENABLE_FILE = os.getenv("OTEL_ENABLE_FILE", "FALSE") == "1"
OTEL_ENABLE_JAEGER = os.getenv("OTEL_ENABLE_JAEGER", "FALSE") == "1"


TELEMETRY = TelemetryConfig(
    OTEL_SERVICE_NAME,
    JAEGER_ENDPOINT,
    JAEGER_TRANSPORT,
    OTEL_FILE_PATH,
    OTEL_SQL_PATH,
)
