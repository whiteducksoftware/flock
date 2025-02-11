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

OTL_SERVICE_NAME = os.getenv("OTL_SERVICE_NAME", "otel-flock")
JAEGER_ENDPOINT = os.getenv(
    "JAEGER_ENDPOINT", "http://localhost:14268/api/traces"
)  # Default gRPC endpoint for Jaeger
JAEGER_TRANSPORT = os.getenv(
    "JAEGER_TRANSPORT", "http"
).lower()  # Options: "grpc" or "http"


TELEMETRY = TelemetryConfig(OTL_SERVICE_NAME, JAEGER_ENDPOINT, JAEGER_TRANSPORT)
