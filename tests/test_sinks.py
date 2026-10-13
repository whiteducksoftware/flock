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
from flock.core.conditions import Until
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


async def test_a_batch_that_times_out_waits_for_the_earlier_delivery_of_its_correlation():
    from datetime import timedelta

    from flock.core.subscription import BatchSpec

    flock = flock_with(lake=Endpoint("https://lake.test"))
    flock.sink("lake").consumes(
        SinkReply, batch=BatchSpec(size=2, timeout=timedelta(milliseconds=50))
    ).post("lake:/replies")
    order: list[list[str]] = []

    async def respond(request):
        tickets = [item["payload"]["ticket"] for item in json.loads(request.content)]
        if tickets == ["B-1", "B-2"]:
            await asyncio.sleep(0.4)  # the full batch is slow; B-3 times out meanwhile
        order.append(tickets)
        return httpx.Response(200)

    with respx.mock() as router:
        router.post("https://lake.test/replies").mock(side_effect=respond)
        for n in (1, 2, 3):
            await flock.publish(
                SinkReply(ticket=f"B-{n}", text="x"), correlation_id="batch-b"
            )
        await flock.run_until_idle()

    assert order == [["B-1", "B-2"], ["B-3"]]


async def test_a_batch_of_one_is_still_a_list():
    from datetime import timedelta

    from flock.core.subscription import BatchSpec

    flock = flock_with(lake=Endpoint("https://lake.test"))
    flock.sink("lake").consumes(
        SinkReply, batch=BatchSpec(size=5, timeout=timedelta(milliseconds=50))
    ).post("lake:/replies")

    with respx.mock() as router:
        route = router.post("https://lake.test/replies").mock(
            return_value=httpx.Response(200)
        )
        await flock.publish(SinkReply(ticket="L-1", text="alone"))
        # The batch goes out when its timeout flushes it
        await flock.run_until(Until.artifact_count(Delivered).at_least(1), timeout=10)

    body = json.loads(route.calls.last.request.content)
    assert isinstance(body, list)
    assert body[0]["payload"]["ticket"] == "L-1"


async def test_payloads_go_out_as_json():
    from enum import Enum

    class Tier(Enum):
        GOLD = "gold"

    @flock_type
    class SinkTagged(BaseModel):
        tags: set[str]
        tier: Tier

    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("tags").consumes(SinkTagged).post("myapp:/tags")

    with respx.mock() as router:
        route = router.post("https://myapp.test/tags").mock(
            return_value=httpx.Response(200)
        )
        await flock.publish(SinkTagged(tags={"alpha"}, tier=Tier.GOLD))
        await flock.run_until_idle()

    payload = json.loads(route.calls.last.request.content)["payload"]
    assert payload == {"tags": ["alpha"], "tier": "gold"}


async def test_a_secret_never_shows_in_a_failed_delivery(monkeypatch, waits):
    monkeypatch.setenv("SINK_BROKEN_KEY", "line\nbreak-secret")
    flock = flock_with(
        myapp=Endpoint("https://myapp.test", auth=Bearer(env="SINK_BROKEN_KEY"))
    )
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")

    with respx.mock(assert_all_called=False) as router:
        route = router.post("https://myapp.test/billing").mock(
            return_value=httpx.Response(200)
        )
        await flock.publish(SinkReply(ticket="T-30", text="x"))
        await flock.run_until_idle()

    assert route.call_count == 0
    (failed,) = await payloads(flock, DeliveryFailed)
    assert "SINK_BROKEN_KEY" in failed["error"]
    assert "secret" not in json.dumps([a.payload for a in await flock.store.list()])


async def test_a_transport_error_that_quotes_a_secret_is_redacted(monkeypatch, waits):
    monkeypatch.setenv("SINK_QUOTED_KEY", "quoted-secret")
    flock = flock_with(
        myapp=Endpoint(
            "https://myapp.test", auth=Header("X-Key", env="SINK_QUOTED_KEY"), retries=0
        )
    )
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")

    with respx.mock() as router:
        router.post("https://myapp.test/billing").mock(
            side_effect=httpx.LocalProtocolError("bad header value quoted-secret")
        )
        await flock.publish(SinkReply(ticket="T-31", text="x"))
        await flock.run_until_idle()

    (failed,) = await payloads(flock, DeliveryFailed)
    assert "quoted-secret" not in failed["error"]
    assert "***" in failed["error"]


async def test_shutdown_closes_the_endpoints_connections():
    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")
    flock.sink("hook").consumes(SinkReply).post("https://other.test/hook")

    with respx.mock() as router:
        router.post("https://myapp.test/billing").mock(return_value=httpx.Response(200))
        router.post("https://other.test/hook").mock(return_value=httpx.Response(200))
        await flock.publish(SinkReply(ticket="T-32", text="x"))
        await flock.run_until_idle()
        clients = [
            engine.target.endpoint._client
            for agent in flock.agents
            for engine in agent.engines
            if hasattr(engine, "target")
        ]
        await flock.shutdown()

    assert len(clients) == 2
    assert all(client is not None and client.is_closed for client in clients)


async def test_a_secret_echoed_in_an_answer_of_another_shape_is_redacted(monkeypatch):
    monkeypatch.setenv("SINK_ECHO_KEY", "echoed-secret")
    flock = flock_with(
        myapp=Endpoint("https://myapp.test", auth=Header("X-Key", env="SINK_ECHO_KEY"))
    )
    flock.sink("crm").consumes(SinkReply).post("myapp:/records", response=SinkCrmRecord)

    with respx.mock() as router:
        router.post("https://myapp.test/records").mock(
            return_value=httpx.Response(200, json={"record_id": ["echoed-secret"]})
        )
        await flock.publish(SinkReply(ticket="T-40", text="x"))
        await flock.run_until_idle()

    (delivered,) = await payloads(flock, Delivered)
    assert "echoed-secret" not in delivered["response_error"]
    assert "***" in delivered["response_error"]


async def test_an_and_gate_delivers_everything_it_collected():
    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    flock.sink("pair").consumes(SinkReply, SinkCrmRecord).post("myapp:/pairs")

    with respx.mock() as router:
        route = router.post("https://myapp.test/pairs").mock(
            return_value=httpx.Response(200)
        )
        await flock.publish(SinkReply(ticket="T-41", text="x"), correlation_id="pair-1")
        await flock.publish(SinkCrmRecord(record_id="R-41"), correlation_id="pair-1")
        await flock.run_until_idle()

    body = json.loads(route.calls.last.request.content)
    assert sorted(item["type"].rsplit(".", 1)[-1] for item in body) == [
        "SinkCrmRecord",
        "SinkReply",
    ]


async def test_a_batch_of_several_correlations_waits_for_each_of_them():
    from flock.core.subscription import BatchSpec

    flock = flock_with(lake=Endpoint("https://lake.test"))
    flock.sink("lake").consumes(SinkReply, batch=BatchSpec(size=2)).post(
        "lake:/replies"
    )
    order: list[list[str]] = []

    async def respond(request):
        tickets = [item["payload"]["ticket"] for item in json.loads(request.content)]
        if tickets == ["A1", "B1"]:
            await asyncio.sleep(0.2)  # slow: the batch after it holds B2, B3
        order.append(tickets)
        return httpx.Response(200)

    with respx.mock() as router:
        router.post("https://lake.test/replies").mock(side_effect=respond)
        await flock.publish(SinkReply(ticket="A1", text="x"), correlation_id="corr-a")
        await flock.publish(SinkReply(ticket="B1", text="x"), correlation_id="corr-b")
        await flock.publish(SinkReply(ticket="B2", text="x"), correlation_id="corr-b")
        await flock.publish(SinkReply(ticket="B3", text="x"), correlation_id="corr-b")
        await flock.run_until_idle()

    assert order == [["A1", "B1"], ["B2", "B3"]]


@pytest.mark.parametrize("readership", ["tenant", "labels", "agent tenant"])
async def test_the_shorthand_sink_reads_what_its_agent_publishes(readership):
    from flock.components.agent import EngineComponent
    from flock.core.visibility import LabelledVisibility, TenantVisibility
    from flock.utils.runtime import EvalResult

    @flock_type
    class SinkScopedTicket(BaseModel):
        ticket: str

    class Answer(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            return EvalResult.from_object(
                SinkReply(ticket="T-42", text="Scoped"), agent=agent
            )

    flock = flock_with(myapp=Endpoint("https://myapp.test"))
    agent = flock.agent("scoped").consumes(SinkScopedTicket).with_engines(Answer())
    if readership == "tenant":
        agent.publishes(
            SinkReply, visibility=TenantVisibility(tenant_id="T1"), post="myapp:/x"
        )
    elif readership == "labels":
        agent.publishes(
            SinkReply,
            visibility=LabelledVisibility(required_labels={"pii"}),
            post="myapp:/x",
        )
    else:
        agent.tenant("T1").publishes(
            SinkReply,
            visibility=lambda reply: TenantVisibility(tenant_id="T1"),
            post="myapp:/x",
        )

    with respx.mock() as router:
        route = router.post("https://myapp.test/x").mock(
            return_value=httpx.Response(200)
        )
        await flock.publish(SinkScopedTicket(ticket="T-42"))
        await flock.run_until_idle()

    assert route.call_count == 1


def test_the_shorthand_cannot_reach_a_private_output():
    from flock.core.visibility import PrivateVisibility

    flock = flock_with(myapp=Endpoint("https://myapp.test"))

    with pytest.raises(ValueError, match="private"):
        flock.agent("secretive").consumes(SinkCrmRecord).publishes(
            SinkReply, visibility=PrivateVisibility(agents={"ops"}), post="myapp:/x"
        )


async def test_a_sinks_card_counts_its_deliveries(waits):
    from flock.api.collector import DashboardEventCollector
    from flock.api.graph_builder import GraphAssembler
    from flock.components.server.models.graph import GraphRequest

    flock = flock_with(myapp=Endpoint("https://myapp.test", retries=0))
    flock.sink("billing-api").consumes(SinkReply).post("myapp:/billing")

    with respx.mock() as router:
        router.post("https://myapp.test/billing").mock(
            side_effect=[
                httpx.Response(200),
                httpx.Response(200),
                httpx.Response(503, text="down"),
            ]
        )
        for n in range(3):
            await flock.publish(
                SinkReply(ticket=f"T-2{n}", text="Counted"), correlation_id="one-run"
            )
        await flock.run_until_idle()

    collector = DashboardEventCollector(store=flock.store)
    snapshot = await GraphAssembler(flock.store, collector, flock).build_snapshot(
        GraphRequest(view_mode="agent")
    )
    node = next(node for node in snapshot.nodes if node.id == "billing-api")

    sink = node.data["sink"]
    assert sink["method"] == "POST"
    assert sink["target"] == "myapp:/billing"
    assert (sink["delivered"], sink["failed"]) == (2, 1)
    assert sink["last"]["ok"] is False
    assert sink["last"]["status"] == 503
    assert "down" in sink["last"]["error"]
    # Agents that are not sinks have no deliveries
    assert all("sink" not in n.data for n in snapshot.nodes if n.id != "billing-api")
