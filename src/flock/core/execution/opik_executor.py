# src/flock/core/execution/evaluation_processor.py
"""Contains the EvaluationProcessor class responsible for evaluating Flock agents
against datasets using various metrics.
"""

from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Union,
)

from opik import Opik
from pandas import DataFrame

# Conditional pandas import
try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore
    PANDAS_AVAILABLE = False

# Box for results
from datasets import Dataset as HFDataset

from flock.core.evaluation.utils import (
    normalize_dataset,
    # Import metric calculation/aggregation helpers
)

# Flock core imports
from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock import Flock
    from flock.core.flock_agent import FlockAgent
    # Conditional types


logger = get_logger("execution.opik")


class OpikExecutor:
    """Handles the evaluation of Flock agents against datasets."""

    def __init__(self, flock_instance: "Flock"):
        """Initializes the EvaluationProcessor.

        Args:
            flock_instance: The Flock instance this processor will use.
        """
        self.flock = flock_instance

    async def evaluate_with_opik(
        self,
        dataset: str | Path | list[dict[str, Any]] | DataFrame | HFDataset,
        start_agent: Union["FlockAgent", str],
        input_mapping: dict[str, str],
        answer_mapping: dict[str, str],) -> DataFrame | list[dict[str, Any]]:
        """Evaluates the Flock's performance against a dataset asynchronously."""
        logger.info(f"Evaluating Flock's performance against dataset: {dataset}")

        # Evaluation task
        def evaluation_task(dataset_item):
          flock_result = self.flock.run(start_agent=start_agent, input=dataset_item, box_result=False)

          result = {
              "input": dataset_item.get("test"),
              "output": flock_result.get("answer"),
              "context": ["placeholder string"]
          }

          return result

        start_agent_name = (
            start_agent.name if hasattr(start_agent, "name") else start_agent
        )
        dataset_name = str(dataset)

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

        logger.info(f"type(df): {type(df)}")        # ➜ <class 'pandas.core.frame.DataFrame'>
        logger.info(f"df.shape: {df.shape}")        # e.g. (123456, N_COLUMNS+2)
        logger.info(f"df['split'].value_counts(): {df['split'].value_counts()}")
        logger.info(f"df['config'].unique(): {df['config'].unique()}")
        client = Opik()
        dataset = client.get_or_create_dataset(name=dataset_name)
        dataset.insert_from_pandas(dataframe=df, ignore_keys=["source"])
        logger.info(f"Imported dataset to Opik")
