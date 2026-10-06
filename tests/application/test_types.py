"""Contracts and the Azure-free import boundary."""

from __future__ import annotations

import subprocess
import sys

import pytest

from flock.application import OutputContract, WorkflowContext

from .conftest import AppSummary, AppTicket, AppTriage


def test_context_is_frozen_with_immutable_attributes():
    context = WorkflowContext("wf", principal_id="p", attributes={"k": "v"})

    with pytest.raises(AttributeError):
        context.workflow_id = "other"  # type: ignore[misc]
    with pytest.raises(TypeError):
        context.attributes["k"] = "changed"  # type: ignore[index]


@pytest.mark.parametrize("bad", ["", "   ", "a\nb", "x" * 300])
def test_context_rejects_invalid_ids(bad):
    with pytest.raises(ValueError):
        WorkflowContext(bad)


def test_required_outputs_must_be_public_outputs():
    with pytest.raises(ValueError, match="required_output_types"):
        OutputContract(
            input_type=AppTicket,
            output_types=(AppTriage,),
            required_output_types=(AppSummary,),
        )


def test_application_api_imports_no_azure_modules():
    code = (
        "import sys, flock, flock.application, flock.integrations.foundry; "
        "leaked = sorted(m for m in sys.modules if m == 'azure' or m.startswith('azure.')); "
        "print('LEAKED=' + ','.join(leaked))"
    )
    lines = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.splitlines()

    assert [line for line in lines if line.startswith("LEAKED=")] == ["LEAKED="]
