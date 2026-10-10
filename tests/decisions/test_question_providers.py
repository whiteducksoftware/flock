"""Yes/no and scale questions on the wire: several questions in one request."""

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
)


URGENT = DecisionQuestion(
    name="Urgent",
    instructions="Does the customer need an answer today?",
    options={"yes": "", "no": ""},
    kind="yesno",
)
REFUND = DecisionQuestion(
    name="Refund",
    instructions="Does the customer ask for a refund?",
    options={"yes": "They want money back", "no": "No refund request"},
    kind="yesno",
)
ANGER = DecisionQuestion(
    name="Anger",
    instructions="How angry is the customer?",
    options={"calm": "Calm", "annoyed": "", "angry": "Angry", "furious": "Furious"},
    kind="scale",
)
ROUTE = DecisionQuestion(
    name="Route",
    instructions="Which team?",
    options={"billing": "Charges, refunds", "tech": "Bugs"},
)
QUESTIONS = [URGENT, REFUND, ANGER, ROUTE]


def _transport(captured: list[httpx.Request], response: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=response)

    return httpx.MockTransport(handler)


SYSTEMONE_ANSWERS = {
    "model": "decision-1",
    "answers": {
        "Urgent": {"type": "noul", "noul": 0.96},
        "Refund": {"type": "noul", "noul": 0.3},
        "Anger": {
            "type": "score",
            "score": 2.18,
            "confidence": 0.71,
            "legend": {"0": "Calm", "1": "annoyed", "2": "Angry", "3": "Furious"},
            "probabilities": {"0": 0.0, "1": 0.02, "2": 0.78, "3": 0.2},
        },
        "Route": {
            "type": "choice",
            "choice": "billing",
            "confidence": 0.99,
            "probabilities": {"billing": 0.99, "tech": 0.01},
        },
    },
}


async def test_systemone_sends_all_questions_in_one_request():
    captured: list[httpx.Request] = []
    provider = SystemOneProvider(
        "https://decide.test/v1/systemone",
        label="azure/decision-1",
        model="decision-1",
        transport=_transport(captured, SYSTEMONE_ANSWERS),
    )

    await provider.decide_many("Ticket: charged twice", QUESTIONS)

    assert len(captured) == 1
    questions = json.loads(captured[0].content)["questions"]
    assert questions["Urgent"] == {
        "type": "noul",
        "instructions": "Does the customer need an answer today?",
    }
    assert questions["Refund"] == {
        "type": "noul",
        "instructions": "Does the customer ask for a refund?",
        "criteria": {"yes": "They want money back", "no": "No refund request"},
    }
    assert questions["Anger"] == {
        "type": "score",
        "instructions": "How angry is the customer?",
        "criteria": ["Calm", "annoyed", "Angry", "Furious"],
    }
    assert questions["Route"]["type"] == "choice"


async def test_systemone_maps_noul_and_score_answers():
    provider = SystemOneProvider(
        "https://decide.test/v1/systemone",
        label="azure/decision-1",
        transport=_transport([], SYSTEMONE_ANSWERS),
    )

    answers = await provider.decide_many("Ticket: charged twice", QUESTIONS)

    urgent, refund, anger, route = (answers[q.name] for q in QUESTIONS)
    assert urgent.choice == "yes"
    assert urgent.probabilities == pytest.approx({"yes": 0.96, "no": 0.04})
    assert urgent.confidence == pytest.approx(0.96)
    assert refund.choice == "no"
    assert refund.confidence == pytest.approx(0.7)
    assert anger.choice == "angry"
    assert anger.probabilities == {
        "calm": 0.0,
        "annoyed": 0.02,
        "angry": 0.78,
        "furious": 0.2,
    }
    assert anger.score == 2.18
    assert anger.confidence == 0.71
    assert route.choice == "billing"
    assert all(a.model == "decision-1" for a in answers.values())


async def test_a_missing_answer_is_an_unexpected_shape():
    response = {"answers": {"Urgent": {"type": "noul", "noul": 0.9}}}
    provider = SystemOneProvider(
        "https://decide.test/v1/systemone",
        label="jev/jev-latest",
        transport=_transport([], response),
    )

    with pytest.raises(DecisionProviderError, match="unexpected answer shape"):
        await provider.decide_many("x", [URGENT, ROUTE])


OPENAI_ANSWERS = {
    "model": "gpt-6-luna",
    "answers": [
        {"type": "predicate", "name": "Urgent", "probability": 1.0},
        {"type": "refusal", "name": "Refund"},
        {
            "type": "score",
            "name": "Anger",
            "score": 2.77,
            "confidence": 0.77,
            "probabilities": [
                {"value": 0, "label": "calm", "probability": 0.0},
                {"value": 1, "label": "annoyed", "probability": 0.0},
                {"value": 2, "label": "angry", "probability": 0.23},
                {"value": 3, "label": "furious", "probability": 0.77},
            ],
        },
        {
            "type": "choice",
            "name": "Route",
            "choice": "billing",
            "confidence": 1.0,
            "probabilities": [
                {"value": "billing", "probability": 1.0},
                {"value": "tech", "probability": 0.0},
            ],
        },
    ],
}


async def test_openai_sends_predicates_and_score_levels():
    captured: list[httpx.Request] = []
    provider = OpenAIDecisionsProvider(
        "https://api.test/v1/decisions",
        label="openai/gpt-6-luna",
        model="gpt-6-luna",
        transport=_transport(captured, OPENAI_ANSWERS),
    )

    await provider.decide_many("Ticket: charged twice", QUESTIONS)

    assert len(captured) == 1
    questions = json.loads(captured[0].content)["questions"]
    assert questions[0] == {
        "type": "predicate",
        "name": "Urgent",
        "instructions": "Does the customer need an answer today?",
    }
    # Predicates take no descriptions; they become part of the instructions
    assert questions[1] == {
        "type": "predicate",
        "name": "Refund",
        "instructions": "Does the customer ask for a refund?\n"
        "Yes: They want money back\nNo: No refund request",
    }
    assert questions[2] == {
        "type": "score",
        "name": "Anger",
        "instructions": "How angry is the customer?",
        "levels": [
            {"label": "calm", "description": "Calm"},
            {"label": "annoyed"},
            {"label": "angry", "description": "Angry"},
            {"label": "furious", "description": "Furious"},
        ],
    }
    assert questions[3]["type"] == "choice"


async def test_openai_maps_predicates_scores_and_refusals():
    provider = OpenAIDecisionsProvider(
        "https://api.test/v1/decisions",
        label="openai/gpt-6-luna",
        model="gpt-6-luna",
        transport=_transport([], OPENAI_ANSWERS),
    )

    answers = await provider.decide_many("Ticket: charged twice", QUESTIONS)

    assert answers["Urgent"].choice == "yes"
    assert answers["Urgent"].probabilities == {"yes": 1.0, "no": 0.0}
    refund = answers["Refund"]
    assert refund.refused
    assert refund.choice is None
    assert refund.probabilities == {}
    assert answers["Anger"].choice == "furious"
    assert answers["Anger"].score == 2.77
    assert answers["Anger"].probabilities["angry"] == 0.23
    assert answers["Route"].choice == "billing"


async def test_fake_decider_answers_several_questions_by_name():
    decider = FakeDecider(
        {
            "Urgent": {"yes": 0.8, "no": 0.2},
            "Anger": {"calm": 0.0, "annoyed": 0.1, "angry": 0.6, "furious": 0.3},
            "Route": lambda state: {"billing": 1.0, "tech": 0.0},
        },
        refuse={"Refund"},
    )

    answers = await decider.decide_many("Ticket", QUESTIONS)

    assert answers["Urgent"].choice == "yes"
    assert answers["Anger"].choice == "angry"
    assert answers["Anger"].score == pytest.approx(2.2)
    assert answers["Route"].choice == "billing"
    assert answers["Refund"].refused
    assert decider.requests == [("Ticket", QUESTIONS)]


async def test_fake_decider_without_an_answer_for_a_question_fails():
    decider = FakeDecider({"Route": {"billing": 1.0, "tech": 0.0}})

    with pytest.raises(DecisionProviderError, match="Urgent"):
        await decider.decide_many("Ticket", [ROUTE, URGENT])
