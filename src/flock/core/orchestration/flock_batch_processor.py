# src/flock/core/orchestration/flock_batch_processor.py
"""Batch processing functionality for Flock orchestrator."""

from typing import TYPE_CHECKING, Any

from box import Box
from pandas import DataFrame

from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock import Flock
    from flock.core.flock_agent import FlockAgent

logger = get_logger("flock.batch_processor")


class FlockBatchProcessor:
    """Handles batch processing functionality for Flock orchestrator."""

    def __init__(self, flock: "Flock"):
        self.flock = flock

    async def run_batch_async(
        self,
        start_agent: "FlockAgent | str",
        batch_inputs: list[dict[str, Any]] | DataFrame | str,
        input_mapping: dict[str, str] | None = None,
        static_inputs: dict[str, Any] | None = None,
        parallel: bool = True,
        max_workers: int = 5,
        use_temporal: bool | None = None,
        box_results: bool = True,
        return_errors: bool = False,
        silent_mode: bool = False,
        write_to_csv: str | None = None,
        hide_columns: list[str] | None = None,
        delimiter: str = ",",
    ) -> list[Box | dict | None | Exception]:
        """Runs the specified agent/workflow for each item in a batch asynchronously (delegated)."""
        # Import processor locally
        from flock.core.execution.batch_executor import BatchProcessor

        processor = BatchProcessor(self.flock)  # Pass flock instance
        return await processor.run_batch_async(
            start_agent=start_agent,
            batch_inputs=batch_inputs,
            input_mapping=input_mapping,
            static_inputs=static_inputs,
            parallel=parallel,
            max_workers=max_workers,
            use_temporal=use_temporal,
            box_results=box_results,
            return_errors=return_errors,
            silent_mode=silent_mode,
            write_to_csv=write_to_csv,
            hide_columns=hide_columns,
            delimiter=delimiter,
        )

    def run_batch(
        self,
        start_agent: "FlockAgent | str",
        batch_inputs: list[dict[str, Any]] | DataFrame | str,
        input_mapping: dict[str, str] | None = None,
        static_inputs: dict[str, Any] | None = None,
        parallel: bool = True,
        max_workers: int = 5,
        use_temporal: bool | None = None,
        box_results: bool = True,
        return_errors: bool = False,
        silent_mode: bool = False,
        write_to_csv: str | None = None,
        hide_columns: list[str] | None = None,
        delimiter: str = ",",
    ) -> list[Box | dict | None | Exception]:
        """Synchronous wrapper for batch processing."""
        return self.flock._execution._run_sync(
            self.run_batch_async(
                start_agent=start_agent,
                batch_inputs=batch_inputs,
                input_mapping=input_mapping,
                static_inputs=static_inputs,
                parallel=parallel,
                max_workers=max_workers,
                use_temporal=use_temporal,
                box_results=box_results,
                return_errors=return_errors,
                silent_mode=silent_mode,
                write_to_csv=write_to_csv,
                hide_columns=hide_columns,
                delimiter=delimiter,
            )
        )
