# src/flock/core/api/run_store.py
"""Manages the state of active and completed Flock runs."""

import threading
from datetime import datetime

from flock.core.logging.logging import get_logger

from .models import FlockAPIResponse  # Import from the models file

logger = get_logger("api.run_store")


class RunStore:
    """Stores and manages the state of Flock runs."""

    def __init__(self):
        self._runs: dict[str, FlockAPIResponse] = {}
        self._lock = threading.Lock()  # Basic lock for thread safety

    def create_run(self, run_id: str) -> FlockAPIResponse:
        """Creates a new run record with 'starting' status."""
        with self._lock:
            if run_id in self._runs:
                logger.warning(f"Run ID {run_id} already exists. Overwriting.")
            response = FlockAPIResponse(
                run_id=run_id, status="starting", started_at=datetime.now()
            )
            self._runs[run_id] = response
            logger.debug(f"Created run record for run_id: {run_id}")
            return response

    def get_run(self, run_id: str) -> FlockAPIResponse | None:
        """Gets the status of a run."""
        with self._lock:
            return self._runs.get(run_id)

    def update_run_status(
        self, run_id: str, status: str, error: str | None = None
    ):
        """Updates the status and potentially error of a run."""
        with self._lock:
            if run_id in self._runs:
                self._runs[run_id].status = status
                if error:
                    self._runs[run_id].error = error
                if status in ["completed", "failed"]:
                    self._runs[run_id].completed_at = datetime.now()
                logger.debug(f"Updated status for run_id {run_id} to {status}")
            else:
                logger.warning(
                    f"Attempted to update status for non-existent run_id: {run_id}"
                )

    def update_run_result(self, run_id: str, result: dict):
        """Updates the result of a completed run."""
        with self._lock:
            if run_id in self._runs:
                # Ensure result is serializable (e.g., convert Box)
                final_result = (
                    dict(result) if hasattr(result, "to_dict") else result
                )
                self._runs[run_id].result = final_result
                self._runs[run_id].status = "completed"
                self._runs[run_id].completed_at = datetime.now()
                logger.debug(f"Updated result for completed run_id: {run_id}")
            else:
                logger.warning(
                    f"Attempted to update result for non-existent run_id: {run_id}"
                )

    # Add methods for cleanup, persistence, etc. later
