"""Token usage and cost of agent runs.

Engines report what their model requests consumed as model -> prompt (input)
tokens and completion (output) tokens: with :func:`report_usage` as soon as a
model answers, which counts even when the run fails afterwards, or in
``EvalResult.metrics["usage"]``, which the agent reports when the engine
returns. The agent adds them up per run and prices them, with the prices of
``Flock(model_prices=...)`` first and LiteLLM's price table second. A run with
a model that has no price shows its tokens and no cost.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


USAGE = "usage"

# The usage of the agent run being executed (see collecting_usage)
_RUN_USAGE: ContextVar[dict[str, Any] | None] = ContextVar(
    "flock_run_usage", default=None
)


@dataclass(frozen=True)
class ModelPrice:
    """Price of a model in USD per million tokens."""

    input: float
    output: float = 0.0


PriceLike = ModelPrice | tuple[float, float] | tuple[float] | Mapping[str, float]


def model_price(price: PriceLike) -> ModelPrice:
    """A ``ModelPrice`` from ``(input, output)``, ``{"input": .., "output": ..}``
    or a ``ModelPrice``."""
    if isinstance(price, ModelPrice):
        return price
    if isinstance(price, Mapping):
        return ModelPrice(
            input=float(price["input"]), output=float(price.get("output", 0.0))
        )
    values = tuple(price)
    if not 1 <= len(values) <= 2:
        raise ValueError(
            f"A model price is (input, output) per million tokens, got {price!r}"
        )
    return ModelPrice(*(float(v) for v in values))


def record_usage(
    metrics: dict[str, Any],
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None = 0,
) -> None:
    """Add one request's tokens for ``model`` to ``metrics["usage"]``."""
    entry = metrics.setdefault(USAGE, {}).setdefault(
        model, {"prompt_tokens": 0, "completion_tokens": 0}
    )
    entry["prompt_tokens"] += int(prompt_tokens or 0)
    entry["completion_tokens"] += int(completion_tokens or 0)


def merge_usage(
    metrics: dict[str, Any], usage: Mapping[str, Mapping[str, Any]] | None
) -> None:
    """Add a usage mapping (model -> tokens) to ``metrics["usage"]``."""
    for model, tokens in (usage or {}).items():
        if not isinstance(tokens, Mapping):
            continue
        record_usage(
            metrics,
            model,
            tokens.get("prompt_tokens"),
            tokens.get("completion_tokens"),
        )


def report_usage(usage: Mapping[str, Mapping[str, Any]] | None) -> None:
    """Add what a model request used (model -> tokens) to the agent run being
    executed. Outside a run it does nothing."""
    metrics = _RUN_USAGE.get()
    if metrics is not None:
        merge_usage(metrics, usage)


@contextmanager
def collecting_usage() -> Iterator[dict[str, Any]]:
    """Collect what the model requests of one agent run use, under
    ``"usage"`` in the yielded dict."""
    metrics: dict[str, Any] = {}
    token = _RUN_USAGE.set(metrics)
    try:
        yield metrics
    finally:
        _RUN_USAGE.reset(token)


def model_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    prices: Mapping[str, ModelPrice],
) -> float | None:
    """USD for the tokens of ``model``, or None when it has no price."""
    price = prices.get(model)
    if price is not None:
        return (prompt_tokens * price.input + completion_tokens * price.output) / 1e6
    try:
        import litellm

        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    except Exception:  # noqa: BLE001 - LiteLLM raises for models it does not map
        return None
    return float(prompt_cost) + float(completion_cost)


def run_metrics(
    usage: Mapping[str, Mapping[str, Any]], prices: Mapping[str, ModelPrice]
) -> dict[str, Any]:
    """Totals of a run: tokens, cost (None when a model has no price) and the
    models without a price."""
    prompt = completion = 0
    cost = 0.0
    unpriced: list[str] = []
    for model, tokens in usage.items():
        p = int(tokens.get("prompt_tokens") or 0)
        c = int(tokens.get("completion_tokens") or 0)
        prompt += p
        completion += c
        price = model_cost(model, p, c, prices)
        if price is None:
            unpriced.append(model)
        else:
            cost += price
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "tokens_used": prompt + completion,
        "cost_usd": None if unpriced else cost,
        "unpriced_models": sorted(unpriced),
    }


__all__ = [
    "USAGE",
    "ModelPrice",
    "collecting_usage",
    "merge_usage",
    "model_cost",
    "model_price",
    "record_usage",
    "report_usage",
    "run_metrics",
]
