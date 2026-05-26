# src/flock/core/api/run_store.py
"""Manages the state of active and completed Flock runs."""

import threading
from datetime import datetime
from typing import Any

from flock.core.logging.logging import get_logger

from .models import (  # Import from the models file
    FlockAPIResponse,
    FlockBatchResponse,
)

logger = get_logger("api.run_store")


class RunStore:
    """Stores and manages the state of Flock runs."""

    def __init__(self):
        self._runs: dict[str, FlockAPIResponse] = {}
        self._batches: dict[str, FlockBatchResponse] = {}
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

    def create_batch(self, batch_id: str) -> FlockBatchResponse:
        """Creates a new batch record with 'starting' status."""
        with self._lock:
            if batch_id in self._batches:
                logger.warning(
                    f"Batch ID {batch_id} already exists. Overwriting."
                )
            response = FlockBatchResponse(
                batch_id=batch_id,
                status="starting",
                results=[],
                started_at=datetime.now(),
                total_items=0,
                completed_items=0,
                progress_percentage=0.0,
            )
            self._batches[batch_id] = response
            logger.debug(f"Created batch record for batch_id: {batch_id}")
            return response

    def get_batch(self, batch_id: str) -> FlockBatchResponse | None:
        """Gets the status of a batch run."""
        with self._lock:
            return self._batches.get(batch_id)

    def update_batch_status(
        self, batch_id: str, status: str, error: str | None = None
    ):
        """Updates the status and potentially error of a batch run."""
        with self._lock:
            if batch_id in self._batches:
                self._batches[batch_id].status = status
                if error:
                    self._batches[batch_id].error = error
                if status in ["completed", "failed"]:
                    self._batches[batch_id].completed_at = datetime.now()
                    # When completed, ensure progress is 100%
                    if (
                        status == "completed"
                        and self._batches[batch_id].total_items > 0
                    ):
                        self._batches[batch_id].completed_items = self._batches[
                            batch_id
                        ].total_items
                        self._batches[batch_id].progress_percentage = 100.0
                logger.debug(
                    f"Updated status for batch_id {batch_id} to {status}"
                )
            else:
                logger.warning(
                    f"Attempted to update status for non-existent batch_id: {batch_id}"
                )

    def update_batch_result(self, batch_id: str, results: list[Any]):
        """Updates the results of a completed batch run."""
        with self._lock:
            if batch_id in self._batches:
                # Ensure results are serializable
                final_results = [
                    dict(r) if hasattr(r, "to_dict") else r for r in results
                ]
                self._batches[batch_id].results = final_results
                self._batches[batch_id].status = "completed"
                self._batches[batch_id].completed_at = datetime.now()

                # Update progress tracking
                self._batches[batch_id].completed_items = len(final_results)
                self._batches[batch_id].total_items = len(final_results)
                self._batches[batch_id].progress_percentage = 100.0

                logger.debug(
                    f"Updated results for completed batch_id: {batch_id}"
                )
            else:
                logger.warning(
                    f"Attempted to update results for non-existent batch_id: {batch_id}"
                )

    def set_batch_total_items(self, batch_id: str, total_items: int):
        """Sets the total number of items in a batch."""
        try:
            with self._lock:
                if batch_id in self._batches:
                    self._batches[batch_id].total_items = total_items
                    # Recalculate percentage
                    if total_items > 0:
                        self._batches[batch_id].progress_percentage = (
                            self._batches[batch_id].completed_items
                            / total_items
                            * 100.0
                        )
                    logger.debug(
                        f"Set total_items for batch_id {batch_id} to {total_items}"
                    )
                else:
                    logger.warning(
                        f"Attempted to set total_items for non-existent batch_id: {batch_id}"
                    )
        except Exception as e:
            logger.error(f"Error setting batch total items: {e}", exc_info=True)

    def update_batch_progress(
        self,
        batch_id: str,
        completed_items: int,
        partial_results: list[Any] = None,
    ):
        """Updates the progress of a batch run and optionally adds partial results.

        Args:
            batch_id: The ID of the batch to update
            completed_items: The number of items that have been completed
            partial_results: Optional list of results for completed items to add to the batch
        """
        try:
            with self._lock:
                if batch_id in self._batches:
                    self._batches[batch_id].completed_items = completed_items

                    # Calculate percentage if we have a total
                    if self._batches[batch_id].total_items > 0:
                        self._batches[batch_id].progress_percentage = (
                            completed_items
                            / self._batches[batch_id].total_items
                            * 100.0
                        )

                    # Add partial results if provided
                    if partial_results:
                        # Ensure results are serializable
                        final_results = [
                            dict(r) if hasattr(r, "to_dict") else r
                            for r in partial_results
                        ]
                        self._batches[batch_id].results = final_results

                    logger.debug(
                        f"Updated progress for batch_id {batch_id}: {completed_items}/{self._batches[batch_id].total_items} "
                        f"({self._batches[batch_id].progress_percentage:.1f}%)"
                    )
                else:
                    logger.warning(
                        f"Attempted to update progress for non-existent batch_id: {batch_id}"
                    )
        except Exception as e:
            logger.error(f"Error updating batch progress: {e}", exc_info=True)

    # Add methods for cleanup, persistence, etc. later
