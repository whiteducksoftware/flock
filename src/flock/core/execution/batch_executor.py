import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from box import Box
from opentelemetry import trace
from pandas import DataFrame
from rich.progress import (  # Import Rich Progress
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from flock.config import TELEMETRY
from flock.core.context.context import FlockContext
from flock.core.context.context_vars import FLOCK_BATCH_SILENT_MODE
from flock.core.flock_agent import FlockAgent
from flock.core.logging.logging import get_logger

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False

if TYPE_CHECKING:
    from flock.core.flock import Flock

logger = get_logger("flock")
TELEMETRY.setup_tracing()  # Setup OpenTelemetry
tracer = trace.get_tracer(__name__)


class BatchProcessor:
    def __init__(self, flock_instance: "Flock"):
        self.flock = flock_instance

    async def run_batch_async(
        self,
        start_agent: FlockAgent | str,
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
        """Runs the specified agent/workflow for each item in a batch asynchronously.

        Args:
            start_agent: Agent instance or name to start each run.
            batch_inputs: Input data in one of these forms:
                - List of dictionaries, each representing inputs for one run
                - Pandas DataFrame where each row is inputs for one run
                - String path to a CSV file to load as DataFrame
            input_mapping: Maps DataFrame/CSV column names to agent input keys (required for DataFrame/CSV).
            static_inputs: Dictionary of inputs constant across all batch runs.
            parallel: Whether to run local jobs in parallel (ignored if use_temporal=True).
            max_workers: Max concurrent local workers (used if parallel=True and use_temporal=False).
            use_temporal: Override Flock's 'enable_temporal' setting for this batch.
            box_results: Wrap successful dictionary results in Box objects.
            return_errors: If True, return Exception objects for failed runs instead of raising.
            silent_mode: If True, suppress output and show progress bar instead.
            write_to_csv: Path to save results as CSV file.
            hide_columns: List of column names to hide from output.

        Returns:
            List containing results (Box/dict), None (if error and not return_errors),
            or Exception objects (if error and return_errors). Order matches input.

        Raises:
            ValueError: For invalid input combinations.
            ImportError: If DataFrame/CSV used without pandas.
            Exception: First exception from a run if return_errors is False.
        """
        effective_use_temporal = (
            use_temporal
            if use_temporal is not None
            else self.flock.enable_temporal
        )
        exec_mode = (
            "Temporal"
            if effective_use_temporal
            else ("Parallel Local" if parallel else "Sequential Local")
        )
        logger.info(
            f"Starting batch run for agent '{start_agent}'. Execution: {exec_mode}, Silent: {silent_mode}"
        )

        # --- Input Preparation ---
        prepared_batch_inputs: list[dict[str, Any]] = []

        if input_mapping == {}:
            input_mapping = None
        if static_inputs == {}:
            static_inputs = None

        if isinstance(batch_inputs, str):
            # Handle CSV file input
            try:
                df = pd.read_csv(batch_inputs)
                logger.debug(
                    f"Loaded CSV file with {len(df)} rows: {batch_inputs}"
                )
                batch_inputs = df  # Convert to DataFrame for unified handling
            except Exception as e:
                raise ValueError(
                    f"Failed to load CSV file '{batch_inputs}': {e}"
                )

        if isinstance(batch_inputs, DataFrame):
            # Handle DataFrame input
            logger.debug(
                f"Converting DataFrame ({len(batch_inputs)} rows) to batch inputs."
            )
            for _, row in batch_inputs.iterrows():
                if input_mapping:
                    item_input = {
                        agent_key: row[df_col]
                        for df_col, agent_key in input_mapping.items()
                        if df_col in row
                    }
                else:
                    item_input = row.to_dict()
                prepared_batch_inputs.append(item_input)
        else:
            # Handle list of dictionaries
            if not isinstance(batch_inputs, list):
                raise ValueError(
                    "batch_inputs must be a list of dictionaries, DataFrame, or CSV file path"
                )

            if input_mapping:
                # Apply mapping to dictionary inputs
                logger.debug("Applying input mapping to dictionary inputs")
                for item in batch_inputs:
                    mapped_input = {}
                    for df_col, agent_key in input_mapping.items():
                        if df_col in item:
                            mapped_input[agent_key] = item[df_col]
                        else:
                            logger.warning(
                                f"Input mapping key '{df_col}' not found in input dictionary"
                            )
                    prepared_batch_inputs.append(mapped_input)
            else:
                # Use dictionaries as-is if no mapping provided
                prepared_batch_inputs = batch_inputs

            logger.debug(
                f"Using provided list of {len(prepared_batch_inputs)} batch inputs."
            )

        if not prepared_batch_inputs:
            return []

        # --- Setup Progress Bar if Silent ---
        progress_context = None
        progress_task_id = None
        if silent_mode:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed}/{task.total})"),
                TimeElapsedColumn(),
                # transient=True # Optionally remove progress bar when done
            )
            progress_context = progress  # Use as context manager
            progress_task_id = progress.add_task(
                f"Processing Batch ({exec_mode})",
                total=len(prepared_batch_inputs),
            )
            progress.start()

        results = [None] * len(
            prepared_batch_inputs
        )  # Pre-allocate results list
        tasks = []
        semaphore = asyncio.Semaphore(
            max_workers if parallel and not effective_use_temporal else 1
        )  # Semaphore for parallel local

        async def worker(index, item_inputs):
            async with semaphore:
                full_input = {**(static_inputs or {}), **item_inputs}
                context = FlockContext()
                context.set_variable(FLOCK_BATCH_SILENT_MODE, silent_mode)

                run_desc = f"Batch item {index + 1}"
                logger.debug(f"{run_desc} started.")
                try:
                    result = await self.flock.run_async(
                        start_agent,
                        full_input,
                        box_result=box_results,
                        context=context,
                    )
                    results[index] = result
                    logger.debug(f"{run_desc} finished successfully.")
                except Exception as e:
                    logger.error(
                        f"{run_desc} failed: {e}", exc_info=not return_errors
                    )
                    if return_errors:
                        results[index] = e
                    else:
                        # If not returning errors, ensure the exception propagates
                        # to stop asyncio.gather if running in parallel.
                        if parallel and not effective_use_temporal:
                            raise  # Re-raise to stop gather
                        else:
                            # For sequential, we just store None or the exception if return_errors=True
                            # For Temporal, error handling happens within the workflow/activity usually
                            results[index] = e if return_errors else None
                finally:
                    if progress_context:
                        progress.update(
                            progress_task_id, advance=1
                        )  # Update progress

        try:
            if effective_use_temporal:
                # Temporal Batching (Simplified: sequential execution for this example)
                # A real implementation might use start_workflow or signals
                logger.info(
                    "Running batch using Temporal (executing sequentially for now)..."
                )
                for i, item_data in enumerate(prepared_batch_inputs):
                    await worker(i, item_data)  # Run sequentially for demo
                # TODO: Implement true parallel Temporal workflow execution if needed

            elif parallel:
                logger.info(
                    f"Running batch in parallel with max_workers={max_workers}..."
                )
                for i, item_data in enumerate(prepared_batch_inputs):
                    tasks.append(asyncio.create_task(worker(i, item_data)))
                await asyncio.gather(
                    *tasks
                )  # gather handles exceptions based on return_errors logic in worker

            else:  # Sequential Local
                logger.info("Running batch sequentially...")
                for i, item_data in enumerate(prepared_batch_inputs):
                    await worker(
                        i, item_data
                    )  # Already handles errors internally based on return_errors

            logger.info("Batch execution finished.")

        except Exception as batch_error:
            # This catch handles errors re-raised from workers when return_errors=False
            logger.error(f"Batch execution stopped due to error: {batch_error}")
            # No need to cancel tasks here as gather would have stopped
            if not return_errors:
                raise  # Re-raise the first error encountered if not returning errors
        finally:
            if progress_context:
                progress.stop()

        if write_to_csv:
            try:
                df = pd.DataFrame(results)
                if hide_columns:
                    df = df.drop(columns=hide_columns)
                # create write_to_csv directory if it doesn't exist
                Path(write_to_csv).parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(write_to_csv, index=False, sep=delimiter)
                logger.info(f"Results written to CSV file: {write_to_csv}")
            except Exception as e:
                logger.error(f"Failed to write results to CSV: {e}")

        return results

    def run_batch(  # Synchronous wrapper
        self,
        start_agent: FlockAgent | str,
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
        """Synchronous wrapper for run_batch_async."""
        # (Standard asyncio run wrapper - same as in previous suggestion)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        coro = self.run_batch_async(
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

        if asyncio.get_event_loop() is loop and not loop.is_running():
            results = loop.run_until_complete(coro)
            # loop.close() # Avoid closing potentially shared loop
            return results
        else:
            # Run within an existing loop
            future = asyncio.ensure_future(coro)
            return loop.run_until_complete(future)
