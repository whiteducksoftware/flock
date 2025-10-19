"""Unified tracing utilities for orchestrator workflows.

Handles OpenTelemetry workflow spans and trace database management.
Extracted from orchestrator.py to reduce complexity.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class TracingManager:
    """Manages unified tracing for orchestrator workflows.

    Provides workflow span creation and trace database cleanup utilities.
    """

    def __init__(self) -> None:
        """Initialize tracing manager."""
        self._workflow_span = None

    @asynccontextmanager
    async def traced_run(
        self, name: str = "workflow", flock_id: str | None = None
    ) -> AsyncGenerator[Any, None]:
        """Context manager for wrapping an entire execution in a single unified trace.

        This creates a parent span that encompasses all operations (publish, run_until_idle, etc.)
        within the context, ensuring they all belong to the same trace_id for better observability.

        Args:
            name: Name for the workflow trace (default: "workflow")
            flock_id: Optional Flock instance ID for attribution

        Yields:
            The workflow span for optional manual attribute setting

        Examples:
            # Explicit workflow tracing (recommended)
            async with tracing_manager.traced_run("pizza_workflow"):
                await flock.publish(pizza_idea)
                await flock.run_until_idle()
                # All operations now share the same trace_id!

            # Custom attributes
            async with tracing_manager.traced_run("data_pipeline") as span:
                span.set_attribute("pipeline.version", "2.0")
                await flock.publish(data)
                await flock.run_until_idle()
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(name) as span:
            # Set workflow-level attributes
            span.set_attribute("flock.workflow", True)
            span.set_attribute("workflow.name", name)
            if flock_id:
                span.set_attribute("workflow.flock_id", flock_id)

            # Store span for nested operations to use
            prev_workflow_span = self._workflow_span
            self._workflow_span = span

            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                # Restore previous workflow span
                self._workflow_span = prev_workflow_span

    @property
    def current_workflow_span(self) -> Any:
        """Get the current workflow span (for nested operations)."""
        return self._workflow_span

    @staticmethod
    def clear_traces(db_path: str = ".flock/traces.duckdb") -> dict[str, Any]:
        """Clear all traces from the DuckDB database.

        Useful for resetting debug sessions or cleaning up test data.

        Args:
            db_path: Path to the DuckDB database file (default: ".flock/traces.duckdb")

        Returns:
            Dictionary with operation results:
                - deleted_count: Number of spans deleted
                - success: Whether operation succeeded
                - error: Error message if failed

        Examples:
            # Clear all traces
            result = TracingManager.clear_traces()
            print(f"Deleted {result['deleted_count']} spans")

            # Custom database path
            result = TracingManager.clear_traces(".flock/custom_traces.duckdb")

            # Check if operation succeeded
            if result['success']:
                print("Traces cleared successfully!")
            else:
                print(f"Error: {result['error']}")
        """
        try:
            import duckdb

            db_file = Path(db_path)
            if not db_file.exists():
                return {
                    "success": False,
                    "deleted_count": 0,
                    "error": f"Database file not found: {db_path}",
                }

            # Connect and clear
            conn = duckdb.connect(str(db_file))
            try:
                # Get count before deletion
                count_result = conn.execute("SELECT COUNT(*) FROM spans").fetchone()
                deleted_count = count_result[0] if count_result else 0

                # Delete all spans
                conn.execute("DELETE FROM spans")

                # Vacuum to reclaim space
                conn.execute("VACUUM")

                return {"success": True, "deleted_count": deleted_count, "error": None}

            finally:
                conn.close()

        except Exception as e:
            return {"success": False, "deleted_count": 0, "error": str(e)}
