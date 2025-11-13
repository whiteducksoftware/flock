"""Tests for DSPySignatureBuilder fan-out semantics."""

from __future__ import annotations

from unittest.mock import Mock

from flock.core.agent import AgentOutput, OutputGroup
from flock.core.artifacts import ArtifactSpec
from flock.core.fan_out import FanOutRange
from flock.engines.dspy.signature_builder import DSPySignatureBuilder
from flock.registry import flock_type, type_registry
from pydantic import BaseModel, Field


@flock_type(name="IdeaOutput")
class Idea(BaseModel):
    text: str = Field(description="Idea text")


class DummyAgent:
    def __init__(self) -> None:
        self.name = "agent"
        self.description = "agent description"


class DummyDSPyModule:
    """Minimal stand-in for dspy module used by SignatureBuilder."""

    class InputField:
        def __init__(self, desc: str | None = None) -> None:
            self.desc = desc

    class OutputField:
        def __init__(self, desc: str | None = None) -> None:
            self.desc = desc

    class Signature(dict):
        def with_instructions(self, instruction: str):
            self.instruction = instruction
            return self


def _make_output_group_with_fan_out(fan_out_spec) -> OutputGroup:
    spec = ArtifactSpec(type_name=type_registry.name_for(Idea), model=Idea)
    output_decl = AgentOutput(spec=spec, default_visibility=None, fan_out=fan_out_spec)
    return OutputGroup(outputs=[output_decl])


def test_signature_builder_dynamic_fan_out_description():
    """Dynamic FanOutRange should produce a 'between min and max' description."""
    dspy_mod = DummyDSPyModule()
    builder = DSPySignatureBuilder()
    agent = DummyAgent()
    output_group = _make_output_group_with_fan_out(FanOutRange(min=2, max=5))

    # No inputs/artifacts required for this test
    from flock.utils.runtime import EvalInputs

    inputs = EvalInputs(artifacts=[], state={})

    signature = builder.prepare_signature_for_output_group(
        dspy_mod,
        agent=agent,
        inputs=inputs,
        output_group=output_group,
        has_context=False,
        batched=False,
        engine_instructions=None,
    )

    # Field name should be pluralized
    assert "ideas" in signature
    field_type, field_meta = signature["ideas"]
    # Signature builder registers list[Idea] as output type
    assert field_type == list[Idea]
    assert isinstance(field_meta, DummyDSPyModule.OutputField)
    assert "between 2 and 5" in field_meta.desc


def test_extract_multi_output_payload_uses_pluralized_field_name():
    """extract_multi_output_payload should read from pluralized field when fan_out is set."""
    dspy_mod = DummyDSPyModule()
    builder = DSPySignatureBuilder()

    output_group = _make_output_group_with_fan_out(FanOutRange(min=1, max=3))

    class Prediction:
        def __init__(self) -> None:
            # Field name is pluralized version of Idea -> ideas
            self.ideas = [
                Idea(text="idea-1"),
                Idea(text="idea-2"),
            ]

    prediction = Prediction()

    payload = builder.extract_multi_output_payload(prediction, output_group)

    # Key should be the type_name, value should be list of serialized items
    type_name = type_registry.name_for(Idea)
    assert type_name in payload
    values = payload[type_name]
    assert isinstance(values, list)
    # extract_multi_output_payload preserves Pydantic instances; they can be serialized later
    assert {v.text for v in values} == {"idea-1", "idea-2"}
