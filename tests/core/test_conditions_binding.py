"""bind_correlation scopes built-in conditions to one workflow."""

import pytest
from pydantic import BaseModel

from flock.core.conditions import (
    AndCondition,
    ExistsCondition,
    NotCondition,
    Until,
    WorkflowErrorCondition,
    bind_correlation,
)


class BindModel(BaseModel):
    value: int = 0


def test_binds_nested_conditions_without_correlation():
    condition = Until.exists(BindModel) & ~Until.artifact_count(BindModel).at_least(2)

    bound = bind_correlation(condition, "wf-1")

    assert isinstance(bound, AndCondition)
    assert bound.left.correlation_id == "wf-1"
    assert isinstance(bound.right, NotCondition)
    assert bound.right.condition.correlation_id == "wf-1"


def test_binds_unbound_workflow_error_condition():
    bound = bind_correlation(Until.workflow_error(), "wf-1")

    assert isinstance(bound, WorkflowErrorCondition)
    assert bound.correlation_id == "wf-1"


def test_keeps_explicit_correlation_when_not_strict():
    condition = ExistsCondition(model=BindModel, correlation_id="other")

    assert bind_correlation(condition, "wf-1") is condition


def test_strict_rejects_foreign_correlation():
    with pytest.raises(ValueError, match="another correlation id"):
        bind_correlation(
            ExistsCondition(model=BindModel, correlation_id="other"),
            "wf-1",
            strict=True,
        )


def test_strict_rejects_idle_condition():
    with pytest.raises(ValueError, match="idle"):
        bind_correlation(Until.idle() | Until.exists(BindModel), "wf-1", strict=True)


def test_none_correlation_returns_condition_unchanged():
    condition = Until.exists(BindModel)

    assert bind_correlation(condition, None) is condition
