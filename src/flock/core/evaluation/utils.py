# src/flock/core/util/evaluation_helpers.py
import inspect
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Union

import pandas as pd
from box import Box
from datasets import get_dataset_config_names, load_dataset

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator
from flock.core.logging.logging import get_logger

# Potentially import metrics libraries like rouge_score, nltk, sentence_transformers

logger_helpers = get_logger("util.evaluation")


def load_and_merge_all_configs(dataset_name: str) -> pd.DataFrame:
    all_configs = get_dataset_config_names(dataset_name)
    all_dfs = []

    for config in all_configs:
        dataset_dict = load_dataset(dataset_name, config)
        for split_name, split_dataset in dataset_dict.items():
            df = split_dataset.to_pandas()
            df["config"] = config
            df["split"] = split_name
            all_dfs.append(df)

    merged_df = pd.concat(all_dfs, ignore_index=True)
    return merged_df


def normalize_dataset(dataset: Any) -> pd.DataFrame:
    """Converts various dataset formats into a pandas DataFrame."""
    if isinstance(dataset, pd.DataFrame):
        return dataset.copy()
    elif isinstance(dataset, str | Path):
        path = Path(dataset)
        if not path.exists():
            try:
                return load_and_merge_all_configs(dataset)
            except Exception as e:
                raise FileNotFoundError(
                    f"Dataset file not found: {path}"
                ) from e
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        # Add support for json, jsonl etc. if needed
        else:
            raise ValueError(
                f"Unsupported file type for dataset: {path.suffix}"
            )
    elif isinstance(dataset, list):
        if not dataset or not isinstance(dataset[0], dict):
            raise ValueError("Dataset list must contain dictionaries.")
        return pd.DataFrame(dataset)
    elif "datasets" in sys.modules and isinstance(
        dataset, sys.modules["datasets"].Dataset
    ):
        # Requires 'datasets' library to be installed
        return dataset.to_pandas()
    else:
        raise TypeError(f"Unsupported dataset type: {type(dataset)}")


def extract_value_by_dot_notation(data: dict | Box, key: str) -> Any:
    """Retrieves a value from a nested dictionary or Box object using dot notation."""
    if not key:
        return None
    keys = key.split(".")
    value = data
    try:
        for k in keys:
            if isinstance(value, (dict, Box)):
                value = value.get(k)
            # Add list index handling if needed: e.g., 'results[0].field'
            # elif isinstance(value, list) and k.isdigit():
            #     value = value[int(k)]
            else:
                return None  # Cannot traverse further
            if value is None:
                return None  # Key not found at this level
        return value
    except (KeyError, IndexError, AttributeError):
        return None


def calculate_evaluation_metrics(
    metrics: list[Union[str, Callable, "FlockAgent", "FlockEvaluator"]],
    metric_configs: dict[str, dict[str, Any]],
    predicted_answers: dict[str, Any],
    expected_answers: dict[str, Any],
    agent_inputs: dict[str, Any],  # For context
    agent_output: Any,  # For context
) -> dict[str, Any]:
    """Calculates all specified metrics for a single evaluation item."""
    results = {}
    for metric in metrics:
        metric_name = ""
        metric_result = None
        try:
            if isinstance(metric, str):
                metric_name = metric
                # Find predicted/expected values relevant to this metric string
                # Simple case: metric name matches an answer_mapping key
                if (
                    metric_name in predicted_answers
                    and metric_name in expected_answers
                ):
                    predicted = predicted_answers[metric_name]
                    expected = expected_answers[metric_name]
                    metric_func = _get_metric_function(metric_name)
                    config = metric_configs.get(metric_name, {})
                    metric_result = metric_func(predicted, expected, **config)
                else:
                    logger_helpers.warning(
                        f"Could not find matching predicted/expected values for metric '{metric_name}' based on answer_mapping keys."
                    )
                    metric_result = None  # Or some error indicator

            elif isinstance(metric, Callable):
                metric_name = getattr(metric, "__name__", "custom_function")
                # Custom functions might need specific predicted/expected pairs, or all of them
                # Let's pass all for flexibility, user function needs to handle it
                config = metric_configs.get(metric_name, {})
                # Allow passing context if function signature supports it
                sig = inspect.signature(metric)
                call_kwargs = config.copy()
                if "agent_inputs" in sig.parameters:
                    call_kwargs["agent_inputs"] = agent_inputs
                if "agent_output" in sig.parameters:
                    call_kwargs["agent_output"] = agent_output

                metric_result = metric(
                    predicted_answers, expected_answers, **call_kwargs
                )

            # --- Placeholder for Agent/Evaluator based metrics ---
            elif "FlockAgent" in str(
                type(metric)
            ):  # Avoid hard import if possible
                metric_name = getattr(metric, "name", "judge_agent")
                config = metric_configs.get(metric_name, {})
                # Requires running the judge agent - needs async context
                # metric_result = asyncio.run(_run_judge_agent(metric, predicted_answers, expected_answers, config))
                logger_helpers.warning(
                    f"Agent-based metric '{metric_name}' execution not implemented in this sketch."
                )
                metric_result = "[Agent Judge Not Implemented]"

            elif "FlockEvaluator" in str(
                type(metric)
            ):  # Avoid hard import if possible
                metric_name = getattr(metric, "name", "judge_evaluator")
                config = metric_configs.get(metric_name, {})
                # Requires running the evaluator - needs async context
                # metric_result = asyncio.run(_run_judge_evaluator(metric, predicted_answers, expected_answers, config))
                logger_helpers.warning(
                    f"Evaluator-based metric '{metric_name}' execution not implemented in this sketch."
                )
                metric_result = "[Evaluator Judge Not Implemented]"
            # --- End Placeholder ---

            else:
                logger_helpers.warning(
                    f"Unsupported metric type: {type(metric)}"
                )
                continue

            # Store result - handle dict results from metrics
            if isinstance(metric_result, dict):
                for sub_key, sub_value in metric_result.items():
                    results[f"{metric_name}_{sub_key}"] = sub_value
            else:
                results[metric_name] = metric_result

        except Exception as e:
            logger_helpers.error(
                f"Error calculating metric '{metric_name}': {e}"
            )
            results[metric_name] = f"[Error: {e}]"

    return results


def _get_metric_function(metric_name: str) -> Callable:
    """Maps metric names to their implementation functions."""
    # Lazy load metric libraries
    if metric_name == "exact_match":
        return lambda pred, act, **kw: str(pred).strip() == str(act).strip()
    elif metric_name == "fuzzy_match":
        try:
            from thefuzz import fuzz

            return (
                lambda pred, act, threshold=85, **kw: fuzz.ratio(
                    str(pred), str(act)
                )
                >= threshold
            )
        except ImportError:
            logger_helpers.warning(
                "fuzzy_match requires 'thefuzz': pip install thefuzz[speedup]"
            )
            return lambda p, a, **kw: None
    elif metric_name.startswith("rouge"):  # rouge_1, rouge_2, rouge_l
        try:
            from rouge_score import rouge_scorer

            scorer = rouge_scorer.RougeScorer(
                [metric_name.replace("_", "")], use_stemmer=True
            )

            def calculate_rouge(pred, act, score_type="fmeasure", **kw):
                scores = scorer.score(str(act), str(pred))
                return (
                    scores[metric_name.replace("_", "")]
                    ._asdict()
                    .get(score_type, 0.0)
                )

            return calculate_rouge
        except ImportError:
            logger_helpers.warning(
                "rouge requires 'rouge-score': pip install rouge-score"
            )
            return lambda p, a, **kw: None
    elif metric_name == "semantic_similarity":
        try:
            from sentence_transformers import SentenceTransformer, util

            # Cache the model? Maybe pass it in via config?
            model = SentenceTransformer("all-MiniLM-L6-v2")

            def calculate_similarity(pred, act, **kw):
                emb1 = model.encode(str(pred), convert_to_tensor=True)
                emb2 = model.encode(str(act), convert_to_tensor=True)
                return util.pytorch_cos_sim(emb1, emb2).item()

            return calculate_similarity
        except ImportError:
            logger_helpers.warning(
                "semantic_similarity requires 'sentence-transformers': pip install sentence-transformers"
            )
            return lambda p, a, **kw: None
    # Add bleu, f1 etc.
    elif metric_name == "llm_judge":
        # This is handled by checking type in calculate_evaluation_metrics
        # but we need a placeholder callable here if we map by string first
        return lambda p, a, **kw: "[LLM Judge Not Implemented Directly]"
    else:
        raise ValueError(f"Unknown built-in metric: {metric_name}")


def aggregate_results(results_list: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregates evaluation results across all items."""
    summary = {"total_items": len(results_list), "errors": 0}
    metric_values: dict[str, list[float | bool]] = {}

    for item in results_list:
        if item.get("error"):
            summary["errors"] += 1
        metrics = item.get("metrics", {})
        for name, value in metrics.items():
            if isinstance(
                value, (float, int, bool)
            ):  # Only aggregate numerics/bools
                if name not in metric_values:
                    metric_values[name] = []
                metric_values[name].append(value)

    summary["metrics_summary"] = {}
    for name, values in metric_values.items():
        if not values:
            continue
        # Calculate different stats based on value type
        if all(isinstance(v, bool) for v in values):
            summary["metrics_summary"][name] = {
                "accuracy": sum(values) / len(values)
            }
        elif all(isinstance(v, (int, float)) for v in values):
            numeric_values = [v for v in values if isinstance(v, (int, float))]
            if numeric_values:
                summary["metrics_summary"][name] = {
                    "mean": sum(numeric_values) / len(numeric_values),
                    "count": len(numeric_values),
                    # Add min, max, stddev if needed
                }

    return summary


# --- Placeholder for async judge execution ---
# Need to run these within the main async context or manage loops carefully
async def _run_judge_agent(judge_agent, predicted, expected, config):
    # Prepare input for the judge agent based on its signature
    # E.g., judge_input = {"prediction": predicted_value, "reference": expected_value, "criteria": ...}
    # judge_result = await judge_agent.run_async(judge_input)
    # return judge_result # Or extract specific score/judgement
    return "[Agent Judge Not Implemented]"


async def _run_judge_evaluator(judge_evaluator, predicted, expected, config):
    # Prepare input for the judge evaluator based on its signature
    # judge_input = {"prediction": predicted_value, "reference": expected_value, **config}
    # judge_result = await judge_evaluator.evaluate(None, judge_input, []) # Agent might not be needed
    # return judge_result # Or extract specific score/judgement
    return "[Evaluator Judge Not Implemented]"
