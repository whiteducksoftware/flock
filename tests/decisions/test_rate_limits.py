"""Rate limits: retries on HTTP 429/503 and request budgets per decision model."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.decisions import Choice, Decision, providers
from flock.decisions.budget import RequestBudget
from flock.decisions.providers import (
    MAX_RETRY_WAIT,
    DecisionProviderError,
    DecisionQuestion,
    FakeDecider,
    SystemOneProvider,
    retry_wait,
)
from flock.registry import flock_type, type_registry


QUESTION = DecisionQuestion(
    name="route",
    instructions="Which team should handle this support ticket?",
    options={"billing": "Charges", "tech": "Bugs"},
)


def _answer(request: httpx.Request) -> dict:
    """Billing for every question asked."""
    questions = json.loads(request.content)["questions"]
    choice = {
        "type": "choice",
        "choice": "billing",
        "probabilities": {"billing": 0.9, "tech": 0.1},
    }
    return {"answers": dict.fromkeys(questions, choice)}


@flock_type
class RateTicket(BaseModel):
    text: str


class Route(Choice):
    """Which team should handle this support ticket?"""

    billing = "Charges"
    tech = "Bugs"


class FakeClock:
    """A clock that only moves when someone sleeps on it."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


# --- request budget -----------------------------------------------------------


@pytest.mark.parametrize(
    ("rate", "limit", "period"),
    [
        ("100/min", 100, 60.0),
        ("5/s", 5, 1.0),
        ("1000/h", 1000, 3600.0),
        (" 7 / min ", 7, 60.0),
    ],
)
def test_budget_parses_requests_per_period(rate, limit, period):
    budget = RequestBudget.parse(rate)
    assert (budget.limit, budget.period) == (limit, period)


@pytest.mark.parametrize("rate", ["100", "0/min", "100/day", "fast", "-1/s", ""])
def test_budget_rejects_invalid_rates(rate):
    with pytest.raises(ValueError, match="rate limit"):
        RequestBudget.parse(rate)


async def test_budget_lets_requests_within_the_limit_start_at_once():
    clock = FakeClock()
    budget = RequestBudget(3, 60.0, clock=clock, sleep=clock.sleep)

    for _ in range(3):
        await budget.acquire()

    assert clock.sleeps == []


async def test_requests_over_the_budget_wait_for_the_oldest_slot():
    clock = FakeClock()
    budget = RequestBudget(2, 60.0, clock=clock, sleep=clock.sleep)

    starts = []
    for _ in range(5):
        await budget.acquire()
        starts.append(clock.now)

    assert starts == [0.0, 0.0, 60.0, 60.0, 120.0]


async def test_concurrent_requests_never_exceed_the_budget():
    waits: list[float] = []

    async def sleep(seconds: float) -> None:  # all callers arrive at t=0
        waits.append(seconds)
        await asyncio.sleep(0)

    budget = RequestBudget(2, 10.0, clock=lambda: 0.0, sleep=sleep)

    await asyncio.gather(*(budget.acquire() for _ in range(5)))

    # Each caller reserves its slot before waiting: 2 now, 2 after 10 s, 1 after 20 s
    assert sorted(waits) == [10.0, 10.0, 20.0]


async def test_slots_free_up_as_time_passes():
    clock = FakeClock()
    budget = RequestBudget(2, 10.0, clock=clock, sleep=clock.sleep)

    await budget.acquire()
    clock.now = 4.0
    await budget.acquire()
    clock.now = 11.0
    await budget.acquire()  # the slot from t=0 is free again

    assert clock.sleeps == []


# --- retry waits ----------------------------------------------------------------


def _response(status: int = 429, **headers: str) -> httpx.Response:
    return httpx.Response(
        status,
        headers={name.replace("_", "-"): value for name, value in headers.items()},
    )


@pytest.mark.parametrize(
    ("headers", "seconds"),
    [
        ({"retry_after_ms": "1500"}, 1.5),
        ({"retry_after": "7"}, 7.0),
        ({"x_ratelimit_reset_requests": "12"}, 12.0),  # Azure: seconds
        ({"x_ratelimit_reset_requests": "250ms"}, 0.25),  # OpenAI: durations
        ({"x_ratelimit_reset_requests": "0m30.5s"}, 30.5),
        ({"retry_after_ms": "2000", "retry_after": "9"}, 2.0),  # most precise first
        ({"retry_after": "9", "x_ratelimit_reset_requests": "30"}, 9.0),
    ],
)
def test_retry_wait_starts_at_the_advertised_wait(headers, seconds):
    # The advice plus the first backoff step (0.5-1 s) spreads concurrent retries
    wait = retry_wait(_response(**headers), attempt=0)
    assert seconds + 0.5 <= wait <= seconds + 1.0


@pytest.mark.parametrize("attempt", [0, 1, 2, 3])
def test_retries_after_short_advice_still_back_off(attempt):
    # Azure advises ~0.4 s until its next token; a burst of concurrent
    # requests retrying after exactly that would fail again together.
    wait = retry_wait(_response(retry_after_ms="400"), attempt=attempt)
    assert 0.4 + 2**attempt / 2 <= wait <= 0.4 + 2**attempt


def test_retry_wait_reads_http_dates():
    later = datetime.now(UTC) + timedelta(seconds=20)
    wait = retry_wait(
        _response(retry_after=format_datetime(later, usegmt=True)), attempt=0
    )
    assert 18.5 <= wait <= 21.0


@pytest.mark.parametrize("value", ["3600", "1h"])
def test_retry_waits_are_capped(value):
    assert (
        retry_wait(_response(x_ratelimit_reset_requests=value), attempt=0)
        == MAX_RETRY_WAIT
    )


@pytest.mark.parametrize("attempt", [0, 1, 2, 3])
def test_retry_wait_backs_off_exponentially_without_headers(attempt):
    wait = retry_wait(_response(503), attempt=attempt)
    assert 2**attempt / 2 <= wait <= 2**attempt


@pytest.mark.parametrize("value", ["0", "soon", "-3"])
def test_unusable_headers_fall_back_to_backoff(value):
    wait = retry_wait(_response(x_ratelimit_reset_requests=value), attempt=1)
    assert 1.0 <= wait <= 2.0


# --- provider retries -------------------------------------------------------------


@pytest.fixture(autouse=True)
def retries(monkeypatch) -> list[tuple[int, int]]:
    """Retry after 10 ms instead of the real backoff; records (status, attempt)."""
    calls: list[tuple[int, int]] = []

    def quick_wait(response: httpx.Response, attempt: int) -> float:
        calls.append((response.status_code, attempt))
        return 0.01

    monkeypatch.setattr(providers, "retry_wait", quick_wait)
    return calls


def _provider(
    statuses: list[int], captured: list[httpx.Request], **kwargs
) -> SystemOneProvider:
    """A provider whose server answers with ``statuses`` in turn."""
    replies = iter(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        status = next(replies)
        if status == 200:
            return httpx.Response(200, json=_answer(request))
        return httpx.Response(status, json={})

    return SystemOneProvider(
        "https://decide.example/v1/systemone",
        label="azure/decision-1",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


async def test_rate_limited_and_overloaded_requests_are_retried(retries):
    captured: list[httpx.Request] = []
    provider = _provider([429, 503, 200], captured)

    answer = await provider.decide("Ticket: charged twice", QUESTION)

    assert answer.choice == "billing"
    assert len(captured) == 3
    assert captured[0].content == captured[2].content  # the same request again
    assert retries == [(429, 0), (503, 1)]


async def test_retries_give_up_after_max_retries():
    captured: list[httpx.Request] = []
    provider = _provider([429] * 3, captured, max_retries=2)

    with pytest.raises(DecisionProviderError) as excinfo:
        await provider.decide("PRIVATE-CANARY", QUESTION)

    assert len(captured) == 3
    assert "HTTP 429 after 3 attempts" in str(excinfo.value)
    assert "PRIVATE-CANARY" not in str(excinfo.value)


@pytest.mark.parametrize("status", [400, 401, 500])
async def test_other_errors_fail_without_retry(retries, status):
    captured: list[httpx.Request] = []
    provider = _provider([status], captured)

    with pytest.raises(DecisionProviderError, match=f"HTTP {status}$"):
        await provider.decide("state", QUESTION)

    assert len(captured) == 1
    assert retries == []


async def test_every_attempt_takes_a_slot_of_the_budget():
    clock = FakeClock()
    captured: list[httpx.Request] = []
    provider = _provider([429, 200], captured)
    provider.budget = RequestBudget(1, 60.0, clock=clock, sleep=clock.sleep)

    await provider.decide("state", QUESTION)

    assert len(captured) == 2
    assert clock.sleeps == [60.0]  # the retry waited for the next slot


# --- Flock(decision_rate_limit=...) -----------------------------------------------


def _provider_of(flock: Flock, name: str):
    (engine,) = next(a for a in flock.agents if a.name == name).engines
    return engine.provider


def test_deciders_of_one_model_share_a_budget():
    flock = Flock(decision_model="local/clef-flash", decision_rate_limit="100/min")
    flock.agent("a").consumes(RateTicket).decides(Route)
    flock.agent("b").consumes(RateTicket).decides(Route)
    flock.agent("c").consumes(RateTicket).decides(Route, model="local/other")

    budget_a, budget_b, budget_c = (_provider_of(flock, name).budget for name in "abc")
    assert budget_a is budget_b
    assert budget_c is not budget_a
    assert (budget_a.limit, budget_a.period) == (100, 60.0)


def test_without_a_rate_limit_nothing_waits():
    flock = Flock(decision_model="local/clef-flash")
    flock.agent("a").consumes(RateTicket).decides(Route)

    assert _provider_of(flock, "a").budget is None


def test_provider_instances_get_the_budget_of_their_label():
    flock = Flock(decision_rate_limit="10/s")
    decider = FakeDecider({"billing": 1.0, "tech": 0.0}, label="fake/one")
    flock.agent("a").consumes(RateTicket).decides(Route, model=decider)

    assert decider.budget is not None
    assert decider.budget.limit == 10


def test_invalid_rate_limits_fail_when_the_flock_is_created():
    with pytest.raises(ValueError, match="rate limit"):
        Flock(decision_rate_limit="lots")


async def test_rate_limited_decisions_still_route():
    captured: list[httpx.Request] = []
    flock = Flock(decision_rate_limit="100/min")
    flock.agent("triage").consumes(RateTicket).decides(
        Route, model=_provider([429, 200], captured)
    )

    await flock.publish(RateTicket(text="charged twice"))
    await flock.run_until_idle()

    name = type_registry.name_for(Decision.of(Route))
    (decision,) = [a for a in await flock.store.list() if a.type == name]
    assert decision.payload["choice"] == "billing"
    assert len(captured) == 2
