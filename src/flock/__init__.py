"""Flock package initialization."""

from opentelemetry import trace
from rich.console import Console
from rich.prompt import Prompt

from flock.cli.app import AgentManagementApp
from flock.config import TELEMETRY
from flock.core.util.cli_helper import display_banner

tracer = TELEMETRY.setup_tracing()
tracer = trace.get_tracer(__name__)
console = Console()


from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, Static, Tree


def main():
    """Main entry point for the Flock package."""
    with tracer.start_as_current_span("flock_main") as span:
        display_banner()
        AgentManagementApp().run()
