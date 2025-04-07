# src/flock/core/execution/evaluation_processor.py
"""Contains the EvaluationProcessor class responsible for evaluating Flock agents
against datasets using various metrics.
"""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Union,
)

from pandas import DataFrame

# Conditional pandas import
try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore
    PANDAS_AVAILABLE = False

# Box for results
from box import Box
from datasets import Dataset as HFDataset

from flock.core.evaluation.utils import (
    aggregate_results,
    calculate_evaluation_metrics,
    extract_value_by_dot_notation,
    normalize_dataset,
    # Import metric calculation/aggregation helpers
)

# Flock core imports
from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock import Flock
    from flock.core.flock_agent import FlockAgent
    from flock.core.flock_evaluator import FlockEvaluator
    # Conditional types


logger = get_logger("execution.evaluation")


class EvaluationExecutor:
    """Handles the evaluation of Flock agents against datasets."""

    def __init__(self, flock_instance: "Flock"):
        """Initializes the EvaluationProcessor.

        Args:
            flock_instance: The Flock instance this processor will use.
        """
        self.flock = flock_instance

    async def evaluate_async(
        self,
        dataset: str | Path | list[dict[str, Any]] | DataFrame | HFDataset,
        start_agent: Union["FlockAgent", str],
        input_mapping: dict[str, str],
        answer_mapping: dict[str, str],
        metrics: list[
            Union[
                str,
                Callable[[Any, Any], bool | float | dict[str, Any]],
                "FlockAgent",
                "FlockEvaluator",
            ]
        ],
        metric_configs: dict[str, dict[str, Any]] | None = None,
        static_inputs: dict[str, Any] | None = None,
        parallel: bool = True,
        max_workers: int = 5,
        use_temporal: bool | None = None,
        error_handling: Literal["raise", "skip", "log"] = "log",
        output_file: str | Path | None = None,
        return_dataframe: bool = True,
        silent_mode: bool = False,
        metadata_columns: list[str] | None = None,  # Columns to pass through
        # dataset_split: Optional[str] = None # TODO: Add split support in normalize_dataset
    ) -> DataFrame | list[dict[str, Any]]:
        """Evaluates the Flock's performance against a dataset asynchronously."""
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
        start_agent_name = (
            start_agent.name if hasattr(start_agent, "name") else start_agent
        )
        logger.info(
            f"Starting evaluation for agent '{start_agent_name}'. Execution: {exec_mode}, Silent: {silent_mode}"
        )

        # --- 1. Normalize Dataset ---
        try:
            df = normalize_dataset(dataset)  # Uses helper
            if df is None or df.empty:
                raise ValueError(
                    "Provided dataset is empty or could not be normalized."
                )
            logger.info(f"Normalized dataset with {len(df)} items.")
        except Exception as e:
            logger.error(
                f"Failed to load or normalize dataset: {e}", exc_info=True
            )
            raise ValueError(f"Dataset processing failed: {e}") from e

        # --- 2. Prepare Batch Items ---
        batch_items = []
        required_input_cols = list(input_mapping.keys())
        required_answer_cols = list(answer_mapping.values())
        required_metadata_cols = metadata_columns or []
        all_required_cols = set(
            required_input_cols + required_answer_cols + required_metadata_cols
        )

        missing_cols = all_required_cols - set(df.columns)
        if missing_cols:
            raise ValueError(
                f"Dataset missing required columns: {', '.join(missing_cols)}"
            )

        for index, row in df.iterrows():
            agent_input = {
                agent_key: row[df_col]
                for df_col, agent_key in input_mapping.items()
            }
            expected_answers = {
                agent_out_key: row[answer_col]
                for agent_out_key, answer_col in answer_mapping.items()
            }
            metadata = {col: row[col] for col in required_metadata_cols}
            batch_items.append(
                {
                    "_original_index": index,  # Store original DF index
                    "_agent_input": agent_input,
                    "_expected_answers": expected_answers,
                    "_metadata": metadata,
                }
            )

        if not batch_items:
            logger.warning("No items prepared for evaluation.")
            return pd.DataFrame() if return_dataframe else []

        # --- 3. Execute Workers ---
        results_dict = {}  # Store results keyed by original index
        tasks = []
        semaphore = asyncio.Semaphore(
            max_workers if parallel and not effective_use_temporal else 1
        )

        # --- Worker Function ---
        async def evaluate_worker(item_index: int, item_data: dict[str, Any]):
            nonlocal results_dict
            original_index = item_data["_original_index"]
            item_result_details = {
                "index": original_index,  # Use original index in result
                "inputs": item_data["_agent_input"],
                "expected_answers": item_data["_expected_answers"],
                "agent_output": None,
                "metrics": {},
                "error": None,
                **(item_data["_metadata"]),  # Include pass-through metadata
            }
            agent_inputs_with_static = {
                **(static_inputs or {}),
                **item_data["_agent_input"],
            }

            async with semaphore:  # Acquire semaphore
                run_desc = f"Evaluation item (original index: {original_index})"
                logger.debug(f"{run_desc} starting.")
                try:
                    # Run the agent/flock for this item
                    agent_output = await self.flock.run_async(
                        start_agent=start_agent,  # Name or instance
                        input=agent_inputs_with_static,
                        box_result=True,  # Use Box for easier access via dot notation
                        # context=... # Assuming isolated context for now
                    )
                    item_result_details["agent_output"] = (
                        agent_output  # Store Box or dict
                    )

                    # Extract predicted values based on answer_mapping
                    predicted_answers = {}
                    for agent_out_key in answer_mapping:
                        # Use helper to handle dot notation
                        predicted_answers[agent_out_key] = (
                            extract_value_by_dot_notation(
                                agent_output, agent_out_key
                            )
                        )

                    # Calculate metrics using helper
                    item_result_details["metrics"] = (
                        calculate_evaluation_metrics(
                            metrics=metrics,
                            metric_configs=metric_configs or {},
                            predicted_answers=predicted_answers,
                            expected_answers=item_data["_expected_answers"],
                            agent_inputs=agent_inputs_with_static,  # Pass context if needed
                            agent_output=agent_output,  # Pass context if needed
                        )
                    )
                    logger.debug(f"{run_desc} finished successfully.")

                except Exception as e:
                    logger.warning(
                        f"Error processing item {original_index}: {e}"
                    )
                    item_result_details["error"] = str(e)
                    if error_handling == "raise":
                        raise  # Re-raise to stop processing (if parallel, stops gather)
                    elif error_handling == "skip":
                        item_result_details["_skip"] = (
                            True  # Mark for filtering
                        )

                # Store result associated with original index
                results_dict[original_index] = item_result_details

                # Update progress bar if applicable (inside the worker is okay)
                if progress_context:
                    progress.update(progress_task_id, advance=1)

        # --- Setup Progress Bar if Silent ---
        progress_context = None
        progress_task_id = None
        if silent_mode:
            from rich.progress import (
                BarColumn,
                Progress,
                SpinnerColumn,
                TextColumn,
                TimeElapsedColumn,
            )

            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed}/{task.total})"),
                TimeElapsedColumn(),
            )
            progress_context = progress
            progress_task_id = progress.add_task(
                f"Evaluating {len(batch_items)} items...",
                total=len(batch_items),
            )
            progress.start()

        # --- Execute Tasks ---
        try:
            if effective_use_temporal:
                # TODO: Implement parallel Temporal evaluation
                logger.info(
                    "Running evaluation using Temporal (executing sequentially for now)..."
                )
                for i, item_data in enumerate(batch_items):
                    await evaluate_worker(i, item_data)  # Pass sequential index
            elif parallel:
                logger.info(
                    f"Running evaluation in parallel with max_workers={max_workers}..."
                )
                for i, item_data in enumerate(batch_items):
                    # Pass sequential index i, and the item_data which contains original_index
                    tasks.append(
                        asyncio.create_task(evaluate_worker(i, item_data))
                    )
                await asyncio.gather(*tasks)
            else:  # Sequential Local
                logger.info("Running evaluation sequentially...")
                for i, item_data in enumerate(batch_items):
                    await evaluate_worker(i, item_data)

            logger.info("Evaluation execution finished.")

        except Exception as batch_error:
            logger.error(
                f"Evaluation stopped due to an error in one of the items: {batch_error}"
            )
            if (
                not error_handling == "skip"
            ):  # If skipping, we continue; otherwise, re-raise if required
                if error_handling == "raise":
                    raise
        finally:
            if progress_context:
                progress.stop()

        # --- 4. Process Results ---
        # Reconstruct results list based on original order and filtering
        final_results_list = []
        for idx in df.index:  # Iterate through original DataFrame index
            res = results_dict.get(idx)
            if res:
                if error_handling == "skip" and res.get("_skip"):
                    continue  # Skip items marked for skipping
                # Remove internal skip flag if present
                res.pop("_skip", None)
                final_results_list.append(res)

        # Calculate aggregate summary using helper
        summary = aggregate_results(final_results_list)
        logger.info(
            "Evaluation Summary:", extra=summary
        )  # Log summary automatically

        # --- 5. Save and Return ---
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                results_df = pd.DataFrame(final_results_list)
                # Handle complex objects before saving
                if "agent_output" in results_df.columns:
                    results_df["agent_output"] = results_df[
                        "agent_output"
                    ].apply(lambda x: x.to_dict() if isinstance(x, Box) else x)
                if (
                    "expected_answers" in results_df.columns
                ):  # Flatten dicts for CSV
                    results_df = pd.concat(
                        [
                            results_df.drop(["expected_answers"], axis=1),
                            pd.json_normalize(
                                results_df["expected_answers"]
                            ).add_prefix("expected_"),
                        ],
                        axis=1,
                    )
                if "metrics" in results_df.columns:  # Flatten dicts for CSV
                    results_df = pd.concat(
                        [
                            results_df.drop(["metrics"], axis=1),
                            pd.json_normalize(results_df["metrics"]).add_prefix(
                                "metric_"
                            ),
                        ],
                        axis=1,
                    )
                if "inputs" in results_df.columns:  # Flatten dicts for CSV
                    results_df = pd.concat(
                        [
                            results_df.drop(["inputs"], axis=1),
                            pd.json_normalize(results_df["inputs"]).add_prefix(
                                "input_"
                            ),
                        ],
                        axis=1,
                    )

                # Convert lists/dicts in metadata columns for CSV saving
                for col in metadata_columns or []:
                    if col in results_df.columns:
                        # Check if column contains lists/dicts before converting
                        if (
                            results_df[col]
                            .apply(lambda x: isinstance(x, (list, dict)))
                            .any()
                        ):
                            results_df[col] = results_df[col].apply(json.dumps)

                if output_path.suffix.lower() == ".csv":
                    results_df.to_csv(output_path, index=False)
                elif output_path.suffix.lower() == ".json":
                    # Save list of dicts directly (before potential DataFrame manipulation)
                    # Need to handle non-serializable types like Box
                    serializable_results = []
                    for res_dict in final_results_list:
                        if "agent_output" in res_dict and isinstance(
                            res_dict["agent_output"], Box
                        ):
                            res_dict["agent_output"] = res_dict[
                                "agent_output"
                            ].to_dict()
                        serializable_results.append(res_dict)
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(
                            serializable_results, f, indent=2, default=str
                        )  # Use default=str for safety
                else:
                    logger.warning(
                        f"Unsupported output file format: {output_path.suffix}. Use .csv or .json."
                    )
                logger.info(
                    f"Detailed evaluation results saved to {output_path}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to save evaluation results to {output_file}: {e}",
                    exc_info=True,
                )

        if return_dataframe:
            if not PANDAS_AVAILABLE:
                logger.error(
                    "Cannot return DataFrame: pandas library not installed."
                )
                return final_results_list  # Fallback to list
            # Ensure DataFrame is created if not done for saving
            if "results_df" not in locals():
                results_df = pd.DataFrame(final_results_list)
                # Convert Box if needed
                if "agent_output" in results_df.columns:
                    results_df["agent_output"] = results_df[
                        "agent_output"
                    ].apply(lambda x: x.to_dict() if isinstance(x, Box) else x)
            return results_df
        else:
            # Ensure Box objects are converted if returning list
            final_list = []
            for res_dict in final_results_list:
                if "agent_output" in res_dict and isinstance(
                    res_dict["agent_output"], Box
                ):
                    res_dict["agent_output"] = res_dict[
                        "agent_output"
                    ].to_dict()
                final_list.append(res_dict)
            return final_list
