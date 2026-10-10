"""DSPy input payloads match the signature's field types (#496).

DSPy 3.2+ checks every input value against its signature type with typeguard
and logs "Type mismatch for field ..." when they differ.
"""

from __future__ import annotations

import dspy
import pytest
from pydantic import BaseModel
from typeguard import check_type

from flock.core.agent import AgentOutput, OutputGroup
from flock.core.artifacts import Artifact, ArtifactSpec
from flock.engines.dspy.signature_builder import DSPySignatureBuilder
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalInputs


@flock_type
class PayloadTopping(BaseModel):
    name: str
    grams: float


@flock_type
class PayloadIdea(BaseModel):
    pizza_idea: str
    toppings: list[PayloadTopping] = []


@flock_type
class PayloadPizza(BaseModel):
    name: str


class Agent:
    name = "pizza_master"
    description = "Makes pizzas"


def _output_group() -> OutputGroup:
    spec = ArtifactSpec(
        type_name=type_registry.name_for(PayloadPizza), model=PayloadPizza
    )
    return OutputGroup(outputs=[AgentOutput(spec=spec, default_visibility=None)])


def _idea(text: str) -> Artifact:
    return Artifact(
        type=type_registry.name_for(PayloadIdea),
        payload={"pizza_idea": text, "toppings": [{"name": "ham", "grams": 50}]},
        produced_by="external",
    )


@pytest.mark.parametrize("batched", [False, True])
def test_payload_values_match_the_signature_types(batched):
    builder = DSPySignatureBuilder()
    inputs = EvalInputs(artifacts=[_idea("pineapple"), _idea("salami")], state={})
    group = _output_group()

    signature = builder.prepare_signature_for_output_group(
        dspy, agent=Agent(), inputs=inputs, output_group=group, batched=batched
    )
    payload = builder.prepare_execution_payload_for_output_group(
        inputs,
        group,
        batched=batched,
        has_context=False,
        context_history=None,
        sys_desc="Make a pizza",
    )

    for name, field in signature.input_fields.items():
        check_type(payload[name], field.annotation)  # what DSPy's Predict checks


def test_invalid_payloads_still_pass_through_as_data():
    """A payload that does not validate is handed on unchanged, as before."""
    builder = DSPySignatureBuilder()
    broken = Artifact(
        type=type_registry.name_for(PayloadIdea),
        payload={"toppings": "not a list"},
        produced_by="external",
    )

    payload = builder.prepare_execution_payload_for_output_group(
        EvalInputs(artifacts=[broken], state={}),
        _output_group(),
        batched=False,
        has_context=False,
        context_history=None,
        sys_desc="Make a pizza",
    )

    assert payload["payload_idea"] == {"toppings": "not a list"}
