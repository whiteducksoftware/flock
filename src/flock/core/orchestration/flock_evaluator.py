# src/flock/core/orchestration/flock_evaluator.py
"""Evaluation functionality for Flock orchestrator."""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from datasets import Dataset
from pandas import DataFrame

from flock.core.flock_agent import FlockAgent
from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock import Flock


logger = get_logger("flock.evaluator")


class FlockEvaluator:
    """Handles evaluation functionality for Flock orchestrator."""

    def __init__(self, flock: "Flock"):
        self.flock = flock

    async def evaluate_async(
        self,
        dataset: str | Path | list[dict[str, Any]] | DataFrame | Dataset,
        start_agent: FlockAgent | str,
        input_mapping: dict[str, str],
        answer_mapping: dict[str, str],
        metrics: list[
            str
            | Callable[[Any, Any], bool | float | dict[str, Any]]
            | FlockAgent
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
        metadata_columns: list[str] | None = None,
    ) -> "DataFrame | list[dict[str, Any]]":
        """Evaluates the Flock's performance against a dataset (delegated)."""
        # Import processor locally
        from flock.core.execution.evaluation_executor import EvaluationExecutor

        processor = EvaluationExecutor(self.flock)  # Pass flock instance
        return await processor.evaluate_async(
            dataset=dataset,
            start_agent=start_agent,
            input_mapping=input_mapping,
            answer_mapping=answer_mapping,
            metrics=metrics,
            metric_configs=metric_configs,
            static_inputs=static_inputs,
            parallel=parallel,
            max_workers=max_workers,
            use_temporal=use_temporal,
            error_handling=error_handling,
            output_file=output_file,
            return_dataframe=return_dataframe,
            silent_mode=silent_mode,
            metadata_columns=metadata_columns,
        )

    def evaluate(
        self,
        dataset: str | Path | list[dict[str, Any]] | DataFrame | Dataset,
        start_agent: FlockAgent | str,
        input_mapping: dict[str, str],
        answer_mapping: dict[str, str],
        metrics: list[
            str
            | Callable[[Any, Any], bool | float | dict[str, Any]]
            | FlockAgent
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
        metadata_columns: list[str] | None = None,
    ) -> "DataFrame | list[dict[str, Any]]":
        """Synchronous wrapper for evaluation."""
        return self.flock._execution._run_sync(
            self.evaluate_async(
                dataset=dataset,
                start_agent=start_agent,
                input_mapping=input_mapping,
                answer_mapping=answer_mapping,
                metrics=metrics,
                metric_configs=metric_configs,
                static_inputs=static_inputs,
                parallel=parallel,
                max_workers=max_workers,
                use_temporal=use_temporal,
                error_handling=error_handling,
                output_file=output_file,
                return_dataframe=return_dataframe,
                silent_mode=silent_mode,
                metadata_columns=metadata_columns,
            )
        )
