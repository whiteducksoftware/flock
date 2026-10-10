"""Decision providers: fake decider, systemone wire protocol, model strings."""

from __future__ import annotations

import json

import httpx
import pytest

from flock.decisions.providers import (
    DecisionProviderError,
    DecisionQuestion,
    FakeDecider,
    OpenAIDecisionsProvider,
    SystemOneProvider,
    resolve_provider,
)


QUESTION = DecisionQuestion(
    name="route",
    instructions="Which team should handle this support ticket?",
    options={
        "billing": "Charges, invoices, refunds",
        "tech": "Bugs, crashes, login problems",
    },
)


async def test_fake_decider_returns_fixed_probabilities_and_argmax():
    decider = FakeDecider({"billing": 0.2, "tech": 0.8})

    answer = await decider.decide("Ticket: printer on fire", QUESTION)

    assert answer.choice == "tech"
    assert answer.probabilities == {"billing": 0.2, "tech": 0.8}
    assert decider.label == "fake"
    assert decider.calls == [("Ticket: printer on fire", QUESTION)]


async def test_fake_decider_accepts_a_function_of_the_state():
    decider = FakeDecider(
        lambda state: {"billing": 1.0, "tech": 0.0}
        if "invoice" in state
        else {"billing": 0.0, "tech": 1.0}
    )

    assert (await decider.decide("my invoice", QUESTION)).choice == "billing"
    assert (await decider.decide("app crashes", QUESTION)).choice == "tech"


async def test_fake_decider_rejects_unknown_options():
    decider = FakeDecider({"marketing": 1.0})

    with pytest.raises(DecisionProviderError, match="marketing"):
        await decider.decide("x", QUESTION)


def _systemone_transport(
    captured: list[httpx.Request], response: dict | None = None, status: int = 200
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            status,
            json=response
            or {
                "model": "jev-1.13.0",
                "answers": {
                    "route": {
                        "type": "choice",
                        "choice": "billing",
                        "confidence": 0.81,
                        "probabilities": {"billing": 0.9, "tech": 0.1},
                    }
                },
                "usage": {"input_tokens": 42, "output_tokens": 0},
            },
        )

    return httpx.MockTransport(handler)


async def test_systemone_request_carries_state_question_and_criteria():
    captured: list[httpx.Request] = []
    provider = SystemOneProvider(
        "https://decide.example/v1/systemone",
        model="jev-latest",
        api_key="secret-key",
        label="jev/jev-latest",
        transport=_systemone_transport(captured),
    )

    answer = await provider.decide("Ticket: charged twice", QUESTION)

    request = captured[0]
    assert request.url == "https://decide.example/v1/systemone"
    assert request.headers["Authorization"] == "Bearer secret-key"
    assert json.loads(request.content) == {
        "model": "jev-latest",
        "state": "Ticket: charged twice",
        "questions": {
            "route": {
                "type": "choice",
                "instructions": "Which team should handle this support ticket?",
                "criteria": {
                    "billing": "Charges, invoices, refunds",
                    "tech": "Bugs, crashes, login problems",
                },
            }
        },
    }
    assert answer.choice == "billing"
    assert answer.probabilities == {"billing": 0.9, "tech": 0.1}
    assert answer.confidence == 0.81
    assert answer.model == "jev-1.13.0"
    assert answer.input_tokens == 42


async def test_systemone_without_key_or_model_sends_neither():
    captured: list[httpx.Request] = []
    provider = SystemOneProvider(
        "http://127.0.0.1:8080/v1/systemone",
        label="local/clef-flash",
        transport=_systemone_transport(captured),
    )

    await provider.decide("state", QUESTION)

    assert "Authorization" not in captured[0].headers
    assert "model" not in json.loads(captured[0].content)


async def test_systemone_http_error_names_status_but_not_the_body():
    captured: list[httpx.Request] = []
    provider = SystemOneProvider(
        "http://127.0.0.1:8080/v1/systemone",
        label="local/clef-flash",
        transport=_systemone_transport(
            captured, response={"error": "state was: PRIVATE-CANARY"}, status=500
        ),
    )

    with pytest.raises(DecisionProviderError) as excinfo:
        await provider.decide("PRIVATE-CANARY", QUESTION)

    assert "500" in str(excinfo.value)
    assert "local/clef-flash" in str(excinfo.value)
    assert "PRIVATE-CANARY" not in str(excinfo.value)


async def test_systemone_answer_for_unknown_option_is_rejected():
    captured: list[httpx.Request] = []
    provider = SystemOneProvider(
        "http://127.0.0.1:8080/v1/systemone",
        label="local/clef-flash",
        transport=_systemone_transport(
            captured,
            response={
                "answers": {
                    "route": {"choice": "marketing", "probabilities": {"marketing": 1}}
                }
            },
        ),
    )

    with pytest.raises(DecisionProviderError, match="unknown option"):
        await provider.decide("state", QUESTION)


@pytest.mark.parametrize(
    "probabilities",
    [
        '{"billing": 2.0, "tech": -1.0}',
        '{"billing": NaN, "tech": 0.1}',  # Python's JSON parser accepts these
        '{"billing": Infinity, "tech": 0.0}',
    ],
)
async def test_answers_with_impossible_probabilities_are_rejected(probabilities):
    body = (
        '{"answers": {"route": {"type": "choice", "choice": "billing", '
        '"probabilities": ' + probabilities + "}}}"
    )
    provider = SystemOneProvider(
        "http://127.0.0.1:8080/v1/systemone",
        label="local/clef-flash",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=body, headers={"Content-Type": "application/json"}
            )
        ),
    )

    with pytest.raises(DecisionProviderError, match="probabilit"):
        await provider.decide("state", QUESTION)


async def test_yes_no_answers_outside_zero_to_one_are_rejected():
    question = DecisionQuestion(
        name="urgent",
        instructions="Urgent?",
        options={"yes": "", "no": ""},
        kind="yesno",
    )
    captured: list[httpx.Request] = []
    provider = SystemOneProvider(
        "http://127.0.0.1:8080/v1/systemone",
        label="local/clef-flash",
        transport=_systemone_transport(
            captured, response={"answers": {"urgent": {"type": "noul", "noul": 1.4}}}
        ),
    )

    with pytest.raises(DecisionProviderError, match="probabilit"):
        await provider.decide("state", question)


def test_resolve_jev_uses_the_official_endpoint_and_key(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "jev-key")
    monkeypatch.delenv("JEV_API_BASE", raising=False)

    provider = resolve_provider("jev/jev-latest")

    assert isinstance(provider, SystemOneProvider)
    assert provider.url == "https://api.typesafe.ai/v1/systemone"
    assert provider.model == "jev-latest"
    assert provider.label == "jev/jev-latest"


def test_resolve_jev_without_key_fails_early(monkeypatch):
    monkeypatch.delenv("JEV_API_KEY", raising=False)

    with pytest.raises(ValueError, match="JEV_API_KEY"):
        resolve_provider("jev/jev-latest")


def test_resolve_local_uses_decision_api_base(monkeypatch):
    monkeypatch.delenv("DECISION_API_BASE", raising=False)
    assert resolve_provider("local/clef-flash").url == (
        "http://127.0.0.1:8080/v1/systemone"
    )

    monkeypatch.setenv("DECISION_API_BASE", "http://gpu-box:9000/")
    provider = resolve_provider("local/clef-flash")
    assert provider.url == "http://gpu-box:9000/v1/systemone"
    assert provider.model is None
    assert provider.label == "local/clef-flash"


def test_resolve_passes_provider_instances_through():
    decider = FakeDecider({"billing": 1.0, "tech": 0.0})
    assert resolve_provider(decider) is decider


def test_resolve_rejects_unknown_prefixes():
    with pytest.raises(ValueError, match="jev/"):
        resolve_provider("anthropic/claude")


def test_resolve_azure_appends_the_decision_path_to_the_resource(monkeypatch):
    monkeypatch.setenv("AZURE_API_BASE", "https://res.example.com/")
    monkeypatch.setenv("AZURE_API_KEY", "azure-key")
    monkeypatch.delenv("AZURE_DECISION", raising=False)

    provider = resolve_provider("azure/decision-1")

    assert isinstance(provider, SystemOneProvider)
    assert provider.url == ("https://res.example.com/providers/microsoft/v1/systemone")
    assert provider.model == "decision-1"
    assert provider.label == "azure/decision-1"


def test_resolve_azure_decision_accepts_a_path_or_a_full_url(monkeypatch):
    monkeypatch.setenv("AZURE_API_BASE", "https://res.example.com")
    monkeypatch.setenv("AZURE_API_KEY", "azure-key")

    monkeypatch.setenv("AZURE_DECISION", "/custom/v1/systemone")
    assert resolve_provider("azure/decision-1").url == (
        "https://res.example.com/custom/v1/systemone"
    )

    monkeypatch.setenv("AZURE_DECISION", "https://other.example/v1/systemone")
    assert resolve_provider("azure/decision-1").url == (
        "https://other.example/v1/systemone"
    )


def test_resolve_azure_without_deployment_uses_the_configured_one(monkeypatch):
    monkeypatch.setenv("AZURE_API_BASE", "https://res.example.com")
    monkeypatch.setenv("AZURE_API_KEY", "azure-key")
    monkeypatch.setenv("AZURE_DECISION_DEPLOYMENT", "decision-1")

    assert resolve_provider("azure/").model == "decision-1"


@pytest.mark.parametrize("missing", ["AZURE_API_BASE", "AZURE_API_KEY"])
def test_resolve_azure_needs_resource_and_key(monkeypatch, missing):
    monkeypatch.setenv("AZURE_API_BASE", "https://res.example.com")
    monkeypatch.setenv("AZURE_API_KEY", "azure-key")
    monkeypatch.delenv(missing)

    with pytest.raises(ValueError, match=missing):
        resolve_provider("azure/decision-1")


async def test_openai_decisions_request_and_answer_mapping():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "model": "gpt-6-luna-2026-09",
                "answers": [
                    {
                        "name": "route",
                        "type": "choice",
                        "choice": "tech",
                        "confidence": 0.7,
                        "probabilities": [
                            {"value": "billing", "probability": 0.2},
                            {"value": "tech", "probability": 0.8},
                        ],
                    }
                ],
                "usage": {"input_tokens": 17},
            },
        )

    provider = OpenAIDecisionsProvider(
        "https://api.openai.com/v1/decisions",
        model="gpt-6-luna",
        api_key="sk-test",
        label="openai/gpt-6-luna",
        transport=httpx.MockTransport(handler),
    )

    answer = await provider.decide("Ticket: app crashes", QUESTION)

    assert captured[0].headers["Authorization"] == "Bearer sk-test"
    assert json.loads(captured[0].content) == {
        "model": "gpt-6-luna",
        "input": "Ticket: app crashes",
        "questions": [
            {
                "type": "choice",
                "name": "route",
                "instructions": "Which team should handle this support ticket?",
                "choices": [
                    {"value": "billing", "description": "Charges, invoices, refunds"},
                    {"value": "tech", "description": "Bugs, crashes, login problems"},
                ],
            }
        ],
    }
    assert answer.choice == "tech"
    assert answer.probabilities == {"billing": 0.2, "tech": 0.8}
    assert answer.confidence == 0.7
    assert answer.model == "gpt-6-luna-2026-09"
    assert answer.input_tokens == 17


def test_resolve_openai_uses_the_decisions_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    provider = resolve_provider("openai/gpt-6-luna")

    assert isinstance(provider, OpenAIDecisionsProvider)
    assert provider.url == "https://api.openai.com/v1/decisions"
    assert provider.model == "gpt-6-luna"


def test_resolve_openai_without_key_fails_early(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        resolve_provider("openai/gpt-6-luna")


async def test_local_provider_reports_its_label_not_the_server_model_path(monkeypatch):
    monkeypatch.delenv("DECISION_API_BASE", raising=False)
    provider = resolve_provider("local/clef-flash")
    provider._transport = _systemone_transport(
        [],
        response={
            "model": "/home/someone/models/Clef-Flash-Q8_0.gguf",
            "answers": {
                "route": {
                    "choice": "tech",
                    "probabilities": {"billing": 0.1, "tech": 0.9},
                }
            },
        },
    )

    answer = await provider.decide("state", QUESTION)

    assert answer.model is None


async def test_openai_omits_empty_option_descriptions():
    """OpenAI rejects `description: null`; options without a description omit the key."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "answers": [
                    {
                        "name": "route",
                        "choice": "tech",
                        "probabilities": [
                            {"value": "billing", "probability": 0.1},
                            {"value": "tech", "probability": 0.9},
                        ],
                    }
                ]
            },
        )

    provider = OpenAIDecisionsProvider(
        "https://api.openai.com/v1/decisions",
        model="gpt-6-luna",
        api_key="sk-test",
        label="openai/gpt-6-luna",
        transport=httpx.MockTransport(handler),
    )
    question = DecisionQuestion(
        name="route",
        instructions="Which team?",
        options={"billing": "", "tech": "Bugs"},
    )

    await provider.decide("state", question)

    choices = json.loads(captured[0].content)["questions"][0]["choices"]
    assert choices == [{"value": "billing"}, {"value": "tech", "description": "Bugs"}]
