"""Sinks: external systems as consumers on the blackboard (#618)."""

import asyncio
import hashlib
import hmac
import json

import httpx
import pytest
import respx
from pydantic import BaseModel

from flock import Bearer, Endpoint, Flock, Header, Hmac, flock_type
from flock.sinks import Delivered, DeliveryFailed
from flock.sinks import engine as sink_engine


@flock_type
class SinkReply(BaseModel):
    ticket: str
    text: str


@flock_type
class SinkCrmRecord(BaseModel):
    record_id: str


@pytest.fixture
def waits(monkeypatch):
    """The waits between attempts, requested but not slept."""
    requested: list[float] = []

    async def no_wait(seconds: float) -> None:
        requested.append(seconds)

    monkeypatch.setattr(sink_engine, "_sleep", no_wait)
    return requested


def flock_with(**endpoints) -> Flock:
    return Flock("openai/gpt-4.1", endpoints=endpoints)


async def payloads(flock: Flock, model: type[BaseModel]) -> list[dict]:
    return [
        a.payload for a in await flock.store.list() if a.type.endswith(model.__name__)
    ]


async def test_a_sink_posts_the_artifact_with_its_id_as_idempotency_key(monkeypatch):
    monkeypatch.setenv("SINK_TEST_KEY", "s3cret")
    flock = flock_with(
        myapp=Endpoint("https://myapp.test", auth=Bearer(env="SINK_TEST_KEY"))
    )
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")

    with respx.mock() as router:
        route = router.post("https://myapp.test/billing").mock(
            return_value=httpx.Response(200)
        )
        artifact = await flock.publish(SinkReply(ticket="T-1", text="Refunded"))
        await flock.run_until_idle()

    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["id"] == str(artifact.id)
    assert body["type"].endswith("SinkReply")
    assert body["payload"] == {"ticket": "T-1", "text": "Refunded"}
    assert body["produced_by"] == "external"
    assert body["correlation_id"] == artifact.correlation_id
    assert request.headers["Idempotency-Key"] == str(artifact.id)
    assert request.headers["Authorization"] == "Bearer s3cret"
    assert request.headers["X-Flock-Correlation-Id"] == artifact.correlation_id

    (delivered,) = await payloads(flock, Delivered)
    assert delivered["sink"] == "billing-api"
    assert delivered["method"] == "POST"
    assert delivered["target"] == "myapp:/billing"
    assert delivered["status"] == 200
    assert delivered["attempts"] == 1
    assert delivered["artifact_ids"] == [str(artifact.id)]
    # The secret is resolved for the request only
    assert "s3cret" not in json.dumps([a.payload for a in await flock.store.list()])
    delivery = next(a for a in await flock.store.list() if a.type.endswith("Delivered"))
    assert delivery.correlation_id == artifact.correlation_id


async def test_a_sink_retries_an_unavailable_target(waits):
    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")

    with respx.mock() as router:
        router.post("https://myapp.test/billing").mock(
            side_effect=[
                httpx.Response(503, headers={"Retry-After": "2"}),
                httpx.Response(200),
            ]
        )
        await flock.publish(SinkReply(ticket="T-2", text="Shipped"))
        await flock.run_until_idle()

    (delivered,) = await payloads(flock, Delivered)
    assert delivered["attempts"] == 2
    # The target's advice is the floor of the wait
    assert len(waits) == 1
    assert waits[0] >= 2


async def test_a_sink_gives_up_and_publishes_delivery_failed(waits):
    flock = flock_with(myapp=Endpoint("https://myapp.test", retries=3))
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")

    with respx.mock() as router:
        route = router.post("https://myapp.test/billing").mock(
            return_value=httpx.Response(503)
        )
        artifact = await flock.publish(SinkReply(ticket="T-3", text="Late"))
        await flock.run_until_idle()

    assert route.call_count == 4  # one attempt and three retries
    assert await payloads(flock, Delivered) == []
    (failed,) = await payloads(flock, DeliveryFailed)
    assert failed["sink"] == "billing-api"
    assert failed["status"] == 503
    assert failed["attempts"] == 4
    assert failed["artifact_ids"] == [str(artifact.id)]
    assert "503" in failed["error"]


async def test_a_sink_does_not_retry_a_rejected_request(waits):
    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")

    with respx.mock() as router:
        route = router.post("https://myapp.test/billing").mock(
            return_value=httpx.Response(400, text="ticket unknown")
        )
        await flock.publish(SinkReply(ticket="T-4", text="?"))
        await flock.run_until_idle()

    assert route.call_count == 1
    assert waits == []
    (failed,) = await payloads(flock, DeliveryFailed)
    assert failed["status"] == 400
    assert "ticket unknown" in failed["error"]


async def test_a_sink_retries_a_connection_error(waits):
    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")

    with respx.mock() as router:
        router.post("https://myapp.test/billing").mock(
            side_effect=[httpx.ConnectError("refused"), httpx.Response(201)]
        )
        await flock.publish(SinkReply(ticket="T-5", text="Back"))
        await flock.run_until_idle()

    (delivered,) = await payloads(flock, Delivered)
    assert delivered["status"] == 201
    assert delivered["attempts"] == 2


async def test_a_missing_secret_fails_the_delivery_without_a_request(monkeypatch):
    monkeypatch.delenv("SINK_MISSING_KEY", raising=False)
    flock = flock_with(
        lake=Endpoint("https://lake.test", auth=Header("X-Key", env="SINK_MISSING_KEY"))
    )
    flock.sink("lake").consumes(SinkReply).put("lake:/replies")

    with respx.mock(assert_all_called=False) as router:
        route = router.put("https://lake.test/replies").mock(
            return_value=httpx.Response(200)
        )
        await flock.publish(SinkReply(ticket="T-6", text="Stored"))
        await flock.run_until_idle()

    assert route.call_count == 0
    (failed,) = await payloads(flock, DeliveryFailed)
    assert "SINK_MISSING_KEY" in failed["error"]
    assert failed["status"] is None


async def test_a_header_secret_and_a_signature(monkeypatch):
    monkeypatch.setenv("SINK_LAKE_KEY", "lake-key")
    monkeypatch.setenv("SINK_SIGNING", "signing-secret")
    flock = flock_with(
        lake=Endpoint(
            "https://lake.test",
            auth=Header("X-Key", env="SINK_LAKE_KEY"),
            sign=Hmac(env="SINK_SIGNING"),
        )
    )
    flock.sink("lake").consumes(SinkReply).patch("lake:/replies")

    with respx.mock() as router:
        route = router.patch("https://lake.test/replies").mock(
            return_value=httpx.Response(204)
        )
        await flock.publish(SinkReply(ticket="T-7", text="Signed"))
        await flock.run_until_idle()

    request = route.calls.last.request
    assert request.headers["X-Key"] == "lake-key"
    expected = hmac.new(b"signing-secret", request.content, hashlib.sha256).hexdigest()
    assert request.headers["X-Flock-Signature"] == f"sha256={expected}"


async def test_a_body_maps_the_artifact_to_the_target_schema():
    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("crm").consumes(SinkReply).post(
        "myapp:/notes", body=lambda artifact: {"note": artifact.payload["text"]}
    )

    with respx.mock() as router:
        route = router.post("https://myapp.test/notes").mock(
            return_value=httpx.Response(200)
        )
        await flock.publish(SinkReply(ticket="T-8", text="Mapped"))
        await flock.run_until_idle()

    assert json.loads(route.calls.last.request.content) == {"note": "Mapped"}


async def test_a_batch_goes_out_in_one_request():
    from flock.core.subscription import BatchSpec

    flock = flock_with(lake=Endpoint("https://lake.test"))
    flock.sink("lake").consumes(SinkReply, batch=BatchSpec(size=3)).post(
        "lake:/replies"
    )

    with respx.mock() as router:
        route = router.post("https://lake.test/replies").mock(
            return_value=httpx.Response(200)
        )
        for n in range(3):
            await flock.publish(SinkReply(ticket=f"T-9{n}", text="Batched"))
        await flock.run_until_idle()

    assert route.call_count == 1
    body = json.loads(route.calls.last.request.content)
    assert [item["payload"]["ticket"] for item in body] == ["T-90", "T-91", "T-92"]
    (delivered,) = await payloads(flock, Delivered)
    assert len(delivered["artifact_ids"]) == 3


async def test_the_target_response_becomes_an_artifact():
    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("crm").consumes(SinkReply).post("myapp:/records", response=SinkCrmRecord)

    with respx.mock() as router:
        router.post("https://myapp.test/records").mock(
            return_value=httpx.Response(201, json={"record_id": "R-1"})
        )
        await flock.publish(SinkReply(ticket="T-10", text="Recorded"))
        await flock.run_until_idle()

    assert await payloads(flock, SinkCrmRecord) == [{"record_id": "R-1"}]
    assert len(await payloads(flock, Delivered)) == 1


async def test_the_publishes_shorthand_creates_a_sink_for_that_agents_output():
    from flock.components.agent import EngineComponent
    from flock.utils.runtime import EvalResult

    @flock_type
    class SinkTicket(BaseModel):
        ticket: str

    class Answer(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            ticket = inputs.artifacts[0].payload["ticket"]
            return EvalResult.from_object(
                SinkReply(ticket=ticket, text="Done"), agent=agent
            )

    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.agent("billing").consumes(SinkTicket).with_engines(Answer()).publishes(
        SinkReply, post="myapp:/billing"
    )

    with respx.mock() as router:
        route = router.post("https://myapp.test/billing").mock(
            return_value=httpx.Response(200)
        )
        await flock.publish(SinkTicket(ticket="T-11"))
        # Another producer's reply does not go to billing's target
        await flock.publish(SinkReply(ticket="T-12", text="Not billing"))
        await flock.run_until_idle()

    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content)["produced_by"] == "billing"
    names = [agent.name for agent in flock.agents]
    assert "billing-sinkreply-post" in names


async def test_deliveries_keep_their_order_per_correlation_and_run_concurrently_across(
    waits,
):
    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("game").consumes(SinkReply).post("myapp:/moves")
    order: list[str] = []
    first_seen = asyncio.Event()

    async def respond(request):
        ticket = json.loads(request.content)["payload"]["ticket"]
        if ticket == "A-1":
            first_seen.set()
            await asyncio.sleep(0.05)  # slow: A-2 waits for it, B-1 does not
        order.append(ticket)
        return httpx.Response(200)

    with respx.mock() as router:
        router.post("https://myapp.test/moves").mock(side_effect=respond)
        await flock.publish(SinkReply(ticket="A-1", text="1"), correlation_id="game-a")
        await flock.publish(SinkReply(ticket="A-2", text="2"), correlation_id="game-a")
        await flock.publish(SinkReply(ticket="B-1", text="1"), correlation_id="game-b")
        await flock.run_until_idle()

    assert order.index("A-1") < order.index("A-2")
    assert order.index("B-1") < order.index("A-1")


async def test_sinks_share_their_endpoints_rate_limit(monkeypatch):
    flock = flock_with(myapp=Endpoint("https://myapp.test", rate_limit="100/min"))
    flock.sink("one").consumes(SinkReply).post("myapp:/one")
    flock.sink("two").consumes(SinkReply).post("myapp:/two")
    budget = flock.endpoints["myapp"].budget
    acquired = 0
    original = budget.acquire

    async def counting():
        nonlocal acquired
        acquired += 1
        await original()

    monkeypatch.setattr(budget, "acquire", counting)
    with respx.mock() as router:
        router.post("https://myapp.test/one").mock(return_value=httpx.Response(200))
        router.post("https://myapp.test/two").mock(return_value=httpx.Response(200))
        await flock.publish(SinkReply(ticket="T-13", text="Twice"))
        await flock.run_until_idle()

    assert acquired == 2


def test_a_target_names_a_known_endpoint_or_a_url():
    flock = flock_with(myapp=Endpoint("https://myapp.test"))

    with pytest.raises(ValueError, match="unknown endpoint 'nope'"):
        flock.sink("one").consumes(SinkReply).post("nope:/billing")
    # A full URL needs no endpoint
    flock.sink("two").consumes(SinkReply).post("https://other.test/hook")
    with pytest.raises(ValueError, match="consumes"):
        flock.sink("three").post("myapp:/x")


def test_an_endpoint_keeps_secret_names_not_values(monkeypatch):
    monkeypatch.setenv("SINK_REPR_KEY", "value-that-must-not-show")
    endpoint = Endpoint(
        "https://myapp.test",
        auth=Bearer(env="SINK_REPR_KEY"),
        sign=Hmac(env="SINK_REPR_KEY"),
    )

    assert "value-that-must-not-show" not in repr(endpoint)
    assert "SINK_REPR_KEY" in repr(endpoint)


def test_a_sink_shows_its_method_and_path_on_its_card():
    from flock.api.graph_builder import GraphAssembler

    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")
    flock.sink("hook").consumes(SinkReply).put("https://other.test/hook")

    assert (
        GraphAssembler._engine_tag(flock.get_agent("billing-api")) == "↗ POST /billing"
    )
    assert (
        GraphAssembler._engine_tag(flock.get_agent("hook")) == "↗ PUT other.test/hook"
    )


@pytest.mark.parametrize("store", ["memory", "sqlite"])
async def test_a_failed_delivery_counts_as_an_error(store, tmp_path):
    from flock.core.store import SQLiteBlackboardStore

    flock = Flock(
        "openai/gpt-4.1",
        endpoints={"myapp": Endpoint("https://myapp.test", retries=0)},
        store=SQLiteBlackboardStore(str(tmp_path / "board.db"))
        if store == "sqlite"
        else None,
    )
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")

    with respx.mock() as router:
        router.post("https://myapp.test/billing").mock(return_value=httpx.Response(500))
        await flock.publish(SinkReply(ticket="T-14", text="Broken"))
        await flock.run_until_idle()

    from datetime import UTC, datetime, timedelta

    from flock.core.store import FilterConfig

    now = datetime.now(UTC)
    filters = FilterConfig(start=now - timedelta(hours=1), end=now + timedelta(hours=1))
    counts, errors = await flock.store.artifact_histogram(filters, buckets=1)
    assert counts == [2]  # the reply and its failed delivery
    assert errors == [1]


async def test_a_failed_run_frees_the_turn_of_its_correlation():
    def body(artifact):
        if artifact.payload["ticket"] == "C-1":
            raise RuntimeError("cannot map C-1")
        return artifact.payload

    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("crm").consumes(SinkReply).post("myapp:/notes", body=body)

    with respx.mock() as router:
        route = router.post("https://myapp.test/notes").mock(
            return_value=httpx.Response(200)
        )
        await flock.publish(SinkReply(ticket="C-1", text="1"), correlation_id="game-c")
        await flock.publish(SinkReply(ticket="C-2", text="2"), correlation_id="game-c")
        await asyncio.wait_for(flock.run_until_idle(), timeout=5)

    assert [json.loads(c.request.content)["ticket"] for c in route.calls] == ["C-2"]
    assert len(await payloads(flock, Delivered)) == 1


async def test_an_answer_of_another_shape_is_noted_on_the_receipt():
    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("crm").consumes(SinkReply).post("myapp:/records", response=SinkCrmRecord)

    with respx.mock() as router:
        router.post("https://myapp.test/records").mock(
            return_value=httpx.Response(200, json={"unexpected": True})
        )
        await flock.publish(SinkReply(ticket="T-15", text="Odd"))
        await flock.run_until_idle()

    assert await payloads(flock, SinkCrmRecord) == []
    (delivered,) = await payloads(flock, Delivered)
    assert "SinkCrmRecord" in delivered["response_error"]
