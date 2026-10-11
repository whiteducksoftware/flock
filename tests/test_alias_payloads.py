"""Models with field aliases: payloads hold field names, models validate by alias.

Payloads are stored with ``model_dump()`` (field names); every place that turns
one back into its model has to accept field names too.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, Field

from flock.application import FlockApplication, WorkflowContext, WorkflowStatus
from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.core.artifacts import Artifact, ArtifactSpec, model_from_payload
from flock.core.store import SQLiteBlackboardStore
from flock.core.subscription import JoinSpec
from flock.core.visibility import PrivateVisibility
from flock.engines.dspy.artifact_materializer import DSPyArtifactMaterializer
from flock.engines.dspy.image_inputs import ensure_vision_support
from flock.engines.dspy.signature_builder import DSPySignatureBuilder
from flock.engines.dspy_engine import DSPyEngine
from flock.core.image import Image
from flock.registry import flock_type, type_registry
from flock.utils.runtime import EvalInputs, EvalResult
from flock.utils.validation import ArtifactValidator


@flock_type(name="AliasOrder")
class AliasOrder(BaseModel):
    order_id: str = Field(alias="orderId")
    note: str = "none"


@flock_type(name="AliasReceipt")
class AliasReceipt(BaseModel):
    order_id: str = Field(alias="orderId")


@flock_type(name="AliasPhoto")
class AliasPhoto(BaseModel):
    picture: Image = Field(alias="pic")


class ReceiptEngine(EngineComponent):
    """Records the typed inputs and answers every order with a receipt."""

    seen: Any = None

    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group):
        order = inputs.first_as(AliasOrder)
        self.seen.append((
            order.order_id,
            [o.order_id for o in inputs.all_as(AliasOrder)],
        ))
        return EvalResult.from_objects(
            AliasReceipt(orderId=order.order_id), agent=agent
        )


def _artifact(model: BaseModel) -> Artifact:
    return Artifact(
        type=type_registry.name_for(type(model)),
        payload=model.model_dump(),
        produced_by="external",
    )


def test_a_payload_is_rebuilt_from_field_names_and_from_aliases():
    assert model_from_payload(AliasOrder, {"order_id": "42"}).order_id == "42"
    assert model_from_payload(AliasOrder, {"orderId": "42"}).order_id == "42"


async def test_an_alias_model_is_published_matched_consumed_and_produced():
    seen: list = []
    called: list = []

    def record(receipt: AliasReceipt) -> None:
        called.append(receipt.order_id)

    flock = Flock(no_output=True)
    flock.agent("clerk").consumes(
        AliasOrder, where=lambda order: order.order_id == "42"
    ).publishes(AliasReceipt).with_engines(ReceiptEngine(seen=seen)).calls(record)

    await flock.publish(AliasOrder(orderId="42"))
    await flock.publish(AliasOrder(orderId="7"))  # filtered out by where=
    await flock.run_until_idle()

    assert seen == [("42", ["42"])]
    assert called == ["42"]
    (receipt,) = await flock.store.get_by_type(AliasReceipt)
    assert receipt.order_id == "42"


async def test_output_filters_validation_and_visibility_see_alias_models():
    flock = Flock(no_output=True)
    flock.agent("clerk").consumes(AliasOrder).publishes(
        AliasReceipt,
        where=lambda receipt: receipt.order_id != "skip",
        validate=lambda receipt: bool(receipt.order_id),
        visibility=lambda receipt: PrivateVisibility(
            agents={f"desk-{receipt.order_id}"}
        ),
    ).with_engines(ReceiptEngine(seen=[]))

    await flock.publish(AliasOrder(orderId="42"))
    await flock.publish(AliasOrder(orderId="skip"))
    await flock.run_until_idle()

    name = type_registry.name_for(AliasReceipt)
    (receipt,) = [a for a in await flock.store.list() if a.type == name]
    assert receipt.payload == {"order_id": "42"}
    assert receipt.visibility.agents == {"desk-42"}


async def test_alias_models_can_be_joined():
    joined: list = []

    class JoinEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            joined.append(sorted(a.type for a in inputs.artifacts))
            return EvalResult(artifacts=[])

    flock = Flock(no_output=True)
    flock.agent("matcher").consumes(
        AliasOrder,
        AliasReceipt,
        join=JoinSpec(by=lambda m: m.order_id, within=timedelta(minutes=1)),
    ).with_engines(JoinEngine())

    await flock.publish(AliasOrder(orderId="42"))
    await flock.publish(AliasReceipt(orderId="42"))
    await flock.run_until_idle()

    assert joined == [["AliasOrder", "AliasReceipt"]]


async def test_the_sqlite_store_returns_alias_models(tmp_path):
    store = SQLiteBlackboardStore(str(tmp_path / "blackboard.db"))
    flock = Flock(store=store, no_output=True)

    await flock.publish(AliasOrder(orderId="42"))
    (order,) = await store.get_by_type(AliasOrder)
    await store.close()

    assert order.order_id == "42"


async def test_an_application_returns_alias_outputs():
    def factory() -> Flock:
        flock = Flock(no_output=True)
        flock.agent("clerk").consumes(AliasOrder).publishes(AliasReceipt).with_engines(
            ReceiptEngine(seen=[])
        )
        return flock

    app = FlockApplication(factory, input_type=AliasOrder, output_types=(AliasReceipt,))

    result = await app.run(
        AliasOrder(orderId="42"), context=WorkflowContext(workflow_id="wf-1")
    )

    assert result.status is WorkflowStatus.SUCCEEDED
    assert result.values(AliasReceipt) == [AliasReceipt(orderId="42")]


def test_the_materializer_keeps_alias_outputs_of_the_llm():
    output = Mock()
    output.spec.model = AliasReceipt
    output.spec.type_name = "AliasReceipt"
    output.count = 1

    artifacts, errors = DSPyArtifactMaterializer().materialize_artifacts(
        {"AliasReceipt": AliasReceipt(orderId="42")}, [output], "clerk"
    )

    assert errors == []
    assert [a.payload for a in artifacts] == [{"order_id": "42"}]


def test_an_artifact_spec_builds_from_field_names():
    spec = ArtifactSpec.from_model(AliasOrder)

    artifact = spec.build(produced_by="clerk", data={"order_id": "42"})

    assert artifact.payload == {"order_id": "42", "note": "none"}


def test_the_dspy_engine_gets_alias_inputs_as_models():
    payload = {"order_id": "42"}

    built = DSPySignatureBuilder()._validate_input_payload(AliasOrder, payload)

    assert isinstance(built, AliasOrder)
    assert DSPyEngine()._validate_input_payload(AliasOrder, payload) == {
        "order_id": "42",
        "note": "none",
    }


def test_images_in_alias_models_are_found_for_text_only_models():
    from PIL import Image as PILImage

    picture = Image.from_pil(PILImage.new("RGB", (8, 8), "red"))
    inputs = EvalInputs(artifacts=[_artifact(AliasPhoto(pic=picture))], state={})

    with pytest.raises(ValueError, match=r"AliasPhoto\.picture"):
        ensure_vision_support("openai/gpt-3.5-turbo", inputs, openai_api=True)


def test_the_artifact_validator_accepts_alias_models():
    is_valid, model, error = ArtifactValidator.validate_artifact(
        _artifact(AliasOrder(orderId="42")), AliasOrder
    )

    assert (is_valid, error) == (True, None)
    assert model.order_id == "42"
