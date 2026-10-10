"""Clients for decision models.

A provider answers questions about a state with a probability per option,
all questions of one decision in a single request. Question kinds map to the
protocols' native question types:

- ``choice``: systemone ``choice`` / OpenAI ``choice``
- ``yesno``: systemone ``noul`` / OpenAI ``predicate`` (options ``yes`` and ``no``)
- ``scale``: systemone ``score`` / OpenAI ``score`` (ordered levels)

Model strings select the provider:

- ``jev/<model>``: TypeSafe Jev (``JEV_API_KEY``; ``JEV_API_BASE`` overrides the endpoint)
- ``local/<name>``: any server speaking ``POST /v1/systemone``, for example
  llama.cpp's ``llama-server`` with a Clef GGUF (``DECISION_API_BASE``,
  default ``http://127.0.0.1:8080``)
- ``azure/<deployment>``: Microsoft-Decision-1 on Azure AI Foundry, systemone
  protocol (``AZURE_API_BASE``, ``AZURE_API_KEY``; ``AZURE_DECISION`` overrides
  the path or URL; an empty deployment reads ``AZURE_DECISION_DEPLOYMENT``)
- ``openai/<model>``: OpenAI Decisions, ``POST /v1/decisions`` (``OPENAI_API_KEY``)

Error messages name the provider and the HTTP status only. Response bodies
can echo the state, so they never end up in exceptions.
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import httpx


if TYPE_CHECKING:
    from flock.core.image import Image


JEV_DEFAULT_URL = "https://api.typesafe.ai/v1/systemone"
LOCAL_DEFAULT_BASE = "http://127.0.0.1:8080"
SYSTEMONE_PATH = "/v1/systemone"
AZURE_DECISION_PATH = "/providers/microsoft/v1/systemone"
OPENAI_DECISIONS_URL = "https://api.openai.com/v1/decisions"


class DecisionProviderError(RuntimeError):
    """A decision model could not answer (transport, status or answer shape)."""


@dataclass(frozen=True)
class DecisionQuestion:
    """One question: instructions plus option name -> description.

    ``kind`` is ``choice``, ``yesno`` (options ``yes`` and ``no``) or ``scale``
    (options are the ordered levels, lowest first). Checklist items are yes/no
    questions with ``group`` (the checklist) and ``item`` set; ``name`` is
    then only an identifier on the wire.
    """

    name: str
    instructions: str
    options: Mapping[str, str]
    kind: str = "choice"
    group: str | None = None
    item: str | None = None

    @property
    def label(self) -> str:
        """``Checklist.item`` for checklist items, the question class for
        tournament groups, else the question name."""
        if self.group and self.item:
            return f"{self.group}.{self.item}"
        return self.group or self.name


@dataclass(frozen=True)
class DecisionAnswer:
    """A decision model's answer to one question.

    ``choice`` is the most probable option, or None when the model refused.
    Scale answers also carry the probability-weighted ``score`` (0 = lowest level).
    """

    choice: str | None
    probabilities: dict[str, float]
    confidence: float | None = None
    model: str | None = None
    input_tokens: int | None = None
    score: float | None = None
    refused: bool = False


class DecisionProvider(ABC):
    """Answers questions about a state (and, if supported, images)."""

    label: str
    supports_images: bool = False

    @abstractmethod
    async def decide_many(
        self,
        state: str,
        questions: Sequence[DecisionQuestion],
        images: Sequence[Image] = (),
    ) -> dict[str, DecisionAnswer]:
        """Answer all ``questions`` about ``state`` and ``images``, keyed by name."""

    async def decide(
        self,
        state: str,
        question: DecisionQuestion,
        images: Sequence[Image] = (),
    ) -> DecisionAnswer:
        """Return the answer to one ``question`` about ``state`` and ``images``."""
        return (await self.decide_many(state, [question], images))[question.name]


def _check_options(
    label: str, question: DecisionQuestion, answer: DecisionAnswer
) -> DecisionAnswer:
    if answer.refused:
        return answer
    unknown = ({answer.choice} | set(answer.probabilities)) - set(question.options)
    if unknown:
        raise DecisionProviderError(
            f"Decision provider '{label}' answered with unknown option(s): "
            f"{', '.join(sorted(unknown))}"
        )
    return answer


def _yes_no_answer(probability_yes: float, **extra: Any) -> DecisionAnswer:
    p = float(probability_yes)
    probabilities = {"yes": p, "no": 1.0 - p}
    choice = "yes" if p >= 0.5 else "no"
    return DecisionAnswer(
        choice=choice,
        probabilities=probabilities,
        confidence=probabilities[choice],
        **extra,
    )


def _weighted_score(
    question: DecisionQuestion, probabilities: Mapping[str, float]
) -> float:
    return sum(
        level * probabilities.get(option, 0.0)
        for level, option in enumerate(question.options)
    )


Probabilities = Mapping[str, float] | Callable[[str], Mapping[str, float]]


class FakeDecider(DecisionProvider):
    """Deterministic provider for tests and examples.

    ``probabilities`` is a fixed mapping or a function of the state, used for
    every question, or a mapping of question name -> either of those. For a
    checklist, map its name to ``{item: probability of yes}`` (or a function
    of the state returning that). The choice is the most probable option;
    scale answers get the weighted score. Questions named in ``refuse`` (for
    checklist items ``"Checklist.item"``) are refused. Every request is
    recorded in ``requests``, every question in ``calls`` and the images in
    ``received_images``.
    """

    def __init__(
        self,
        probabilities: Probabilities | Mapping[str, Probabilities],
        *,
        label: str = "fake",
        supports_images: bool = True,
        refuse: Collection[str] = (),
    ) -> None:
        self._probabilities = probabilities
        self.label = label
        self.supports_images = supports_images
        self.refuse = set(refuse)
        self.requests: list[tuple[str, list[DecisionQuestion]]] = []
        self.calls: list[tuple[str, DecisionQuestion]] = []
        self.received_images: list[list[Image]] = []

    def _source(self, question: DecisionQuestion, state: str) -> Probabilities:
        source = self._probabilities
        if callable(source) or not any(
            isinstance(value, Mapping) or callable(value) for value in source.values()
        ):
            return source
        if (
            question.group is not None
            and question.group in source
            and not question.item
        ):
            # Tournament group: the question's options out of the full distribution
            full = source[question.group]
            full = full(state) if callable(full) else full
            subset = {
                option: float(full.get(option, 0.0)) for option in question.options
            }
            total = sum(subset.values()) or 1.0
            return {option: p / total for option, p in subset.items()}
        if question.group is not None and question.group in source:
            items = source[question.group]
            items = items(state) if callable(items) else items
            if question.item not in items:
                raise DecisionProviderError(
                    f"Decision provider '{self.label}' has no answer for "
                    f"'{question.label}'"
                )
            p = float(items[question.item])
            return {"yes": p, "no": 1.0 - p}
        if question.name not in source:
            raise DecisionProviderError(
                f"Decision provider '{self.label}' has no answer for '{question.name}'"
            )
        return source[question.name]

    def _answer(self, state: str, question: DecisionQuestion) -> DecisionAnswer:
        if question.label in self.refuse:
            return DecisionAnswer(choice=None, probabilities={}, refused=True)
        source = self._source(question, state)
        probabilities = dict(source(state) if callable(source) else source)
        if not probabilities:
            raise DecisionProviderError(
                f"Decision provider '{self.label}' returned no probabilities"
            )
        choice = max(probabilities, key=probabilities.__getitem__)
        score = (
            _weighted_score(question, probabilities)
            if question.kind == "scale"
            else None
        )
        return DecisionAnswer(
            choice=choice,
            probabilities=probabilities,
            confidence=probabilities[choice],
            score=score,
        )

    async def decide_many(
        self,
        state: str,
        questions: Sequence[DecisionQuestion],
        images: Sequence[Image] = (),
    ) -> dict[str, DecisionAnswer]:
        self.requests.append((state, list(questions)))
        self.calls.extend((state, question) for question in questions)
        self.received_images.append(list(images))
        return {
            question.name: _check_options(
                self.label,
                question,
                replace(self._answer(state, question), model=self.label),
            )
            for question in questions
        }


class _HttpDecisionProvider(DecisionProvider):
    """Shared transport for HTTP decision protocols (one request per decision)."""

    def __init__(
        self,
        url: str,
        *,
        label: str,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
        report_server_model: bool = True,
        supports_images: bool | None = None,
    ) -> None:
        self.url = url
        self.label = label
        self.model = model
        if supports_images is not None:
            self.supports_images = supports_images
        # Local servers report their model file path; decisions then carry the label
        self.report_server_model = report_server_model
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport
        # One client per event loop keeps connections alive between decisions.
        self._client: httpx.AsyncClient | None = None
        self._client_loop: asyncio.AbstractEventLoop | None = None

    def _http(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if self._client is None or self._client_loop is not loop:
            self._client = httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            )
            self._client_loop = loop
        return self._client

    @abstractmethod
    def _body(
        self,
        state: str,
        questions: Sequence[DecisionQuestion],
        images: Sequence[Image],
    ) -> dict[str, Any]:
        """Request body asking all ``questions``."""

    @abstractmethod
    def _parse(
        self, data: dict[str, Any], questions: Sequence[DecisionQuestion]
    ) -> dict[str, DecisionAnswer]:
        """Answers by question name from a decoded response body."""

    async def decide_many(
        self,
        state: str,
        questions: Sequence[DecisionQuestion],
        images: Sequence[Image] = (),
    ) -> dict[str, DecisionAnswer]:
        if images and not self.supports_images:
            raise DecisionProviderError(
                f"Decision model '{self.label}' does not accept images."
            )
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._http().post(
                self.url, json=self._body(state, questions, images), headers=headers
            )
        except httpx.HTTPError as exc:
            raise DecisionProviderError(
                f"Decision provider '{self.label}' is unreachable ({type(exc).__name__})"
            ) from None
        if response.status_code != 200:
            raise DecisionProviderError(
                f"Decision provider '{self.label}' returned HTTP {response.status_code}"
            )
        try:
            data = response.json()
            answers = self._parse(data, questions)
        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
            StopIteration,
        ):
            raise DecisionProviderError(
                f"Decision provider '{self.label}' returned an unexpected answer shape"
            ) from None
        model = data.get("model") if self.report_server_model else None
        input_tokens = (data.get("usage") or {}).get("input_tokens")
        return {
            question.name: _check_options(
                self.label,
                question,
                replace(answers[question.name], model=model, input_tokens=input_tokens),
            )
            for question in questions
        }


def _float_or_none(value: Any) -> float | None:
    return float(value) if value is not None else None


class SystemOneProvider(_HttpDecisionProvider):
    """Client for the ``POST /v1/systemone`` protocol (Jev, Clef, Decision-1)."""

    @staticmethod
    def _question(question: DecisionQuestion) -> dict[str, Any]:
        if question.kind == "yesno":
            body: dict[str, Any] = {
                "type": "noul",
                "instructions": question.instructions,
            }
            criteria = {
                option: description
                for option, description in question.options.items()
                if description
            }
            if criteria:
                body["criteria"] = criteria
            return body
        if question.kind == "scale":
            return {
                "type": "score",
                "instructions": question.instructions,
                "criteria": [
                    description or option
                    for option, description in question.options.items()
                ],
            }
        return {
            "type": "choice",
            "instructions": question.instructions,
            "criteria": {
                option: description or None
                for option, description in question.options.items()
            },
        }

    def _body(
        self,
        state: str,
        questions: Sequence[DecisionQuestion],
        images: Sequence[Image],
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "state": state,
            "questions": {
                question.name: self._question(question) for question in questions
            },
        }
        if images:
            body["images"] = [image.base64_data for image in images]
        if self.model is not None:
            body = {"model": self.model, **body}
        return body

    @staticmethod
    def _answer(question: DecisionQuestion, raw: dict[str, Any]) -> DecisionAnswer:
        if question.kind == "yesno":
            return _yes_no_answer(raw["noul"])
        if question.kind == "scale":
            levels = list(question.options)
            probabilities = {
                levels[int(index)]: float(p)
                for index, p in raw["probabilities"].items()
            }
            return DecisionAnswer(
                choice=max(probabilities, key=probabilities.__getitem__),
                probabilities=probabilities,
                confidence=_float_or_none(raw.get("confidence")),
                score=float(raw["score"]),
            )
        return DecisionAnswer(
            choice=str(raw["choice"]),
            probabilities={
                str(option): float(p) for option, p in raw["probabilities"].items()
            },
            confidence=_float_or_none(raw.get("confidence")),
        )

    def _parse(
        self, data: dict[str, Any], questions: Sequence[DecisionQuestion]
    ) -> dict[str, DecisionAnswer]:
        return {
            question.name: self._answer(question, data["answers"][question.name])
            for question in questions
        }


class OpenAIDecisionsProvider(_HttpDecisionProvider):
    """Client for OpenAI's ``POST /v1/decisions`` protocol."""

    supports_images = True

    @staticmethod
    def _question(question: DecisionQuestion) -> dict[str, Any]:
        if question.kind == "yesno":
            # Predicates take no descriptions; they become part of the instructions
            described = [
                f"{option.capitalize()}: {description}"
                for option, description in question.options.items()
                if description
            ]
            return {
                "type": "predicate",
                "name": question.name,
                "instructions": "\n".join([question.instructions, *described]),
            }
        if question.kind == "scale":
            return {
                "type": "score",
                "name": question.name,
                "instructions": question.instructions,
                "levels": [
                    {
                        "label": option,
                        **({"description": description} if description else {}),
                    }
                    for option, description in question.options.items()
                ],
            }
        return {
            "type": "choice",
            "name": question.name,
            "instructions": question.instructions,
            "choices": [
                {
                    "value": option,
                    **({"description": description} if description else {}),
                }
                for option, description in question.options.items()
            ],
        }

    def _body(
        self,
        state: str,
        questions: Sequence[DecisionQuestion],
        images: Sequence[Image],
    ) -> dict[str, Any]:
        content: str | list[dict[str, Any]] = state
        if images:
            content = [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": state},
                        *(
                            {"type": "input_image", "image_url": image.url}
                            for image in images
                        ),
                    ],
                }
            ]
        return {
            "model": self.model,
            "input": content,
            "questions": [self._question(question) for question in questions],
        }

    @staticmethod
    def _answer(question: DecisionQuestion, raw: dict[str, Any]) -> DecisionAnswer:
        if raw.get("type") == "refusal":
            return DecisionAnswer(choice=None, probabilities={}, refused=True)
        if question.kind == "yesno":
            return _yes_no_answer(raw["probability"])
        if question.kind == "scale":
            levels = list(question.options)
            probabilities = {
                levels[int(p["value"])]: float(p["probability"])
                for p in raw["probabilities"]
            }
            return DecisionAnswer(
                choice=max(probabilities, key=probabilities.__getitem__),
                probabilities=probabilities,
                confidence=_float_or_none(raw.get("confidence")),
                score=float(raw["score"]),
            )
        return DecisionAnswer(
            choice=str(raw["choice"]),
            probabilities={
                str(p["value"]): float(p["probability"]) for p in raw["probabilities"]
            },
            confidence=_float_or_none(raw.get("confidence")),
        )

    def _parse(
        self, data: dict[str, Any], questions: Sequence[DecisionQuestion]
    ) -> dict[str, DecisionAnswer]:
        by_name = {raw["name"]: raw for raw in data["answers"]}
        return {
            question.name: self._answer(question, by_name[question.name])
            for question in questions
        }


def _required_env(name: str, model: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Decision model '{model}' needs {name} to be set.")
    return value


def resolve_provider(model: str | DecisionProvider) -> DecisionProvider:
    """Turn a model string (or provider instance) into a provider."""
    if isinstance(model, DecisionProvider):
        return model
    prefix, _, name = model.partition("/")
    if prefix == "jev" and name:
        api_key = _required_env("JEV_API_KEY", model)
        url = os.getenv("JEV_API_BASE", JEV_DEFAULT_URL)
        return SystemOneProvider(url, label=model, model=name, api_key=api_key)
    if prefix == "local" and name:
        base = os.getenv("DECISION_API_BASE", LOCAL_DEFAULT_BASE).rstrip("/")
        return SystemOneProvider(
            f"{base}{SYSTEMONE_PATH}",
            label=model,
            report_server_model=False,
            supports_images=True,
        )
    if prefix == "azure":
        base = _required_env("AZURE_API_BASE", model).rstrip("/")
        api_key = _required_env("AZURE_API_KEY", model)
        deployment = name or _required_env("AZURE_DECISION_DEPLOYMENT", model)
        endpoint = os.getenv("AZURE_DECISION", AZURE_DECISION_PATH)
        url = endpoint if endpoint.startswith("http") else f"{base}{endpoint}"
        return SystemOneProvider(
            url, label=f"azure/{deployment}", model=deployment, api_key=api_key
        )
    if prefix == "openai" and name:
        api_key = _required_env("OPENAI_API_KEY", model)
        return OpenAIDecisionsProvider(
            OPENAI_DECISIONS_URL, label=model, model=name, api_key=api_key
        )
    raise ValueError(
        f"Unknown decision model '{model}'. Use 'jev/<model>', 'local/<name>', "
        "'azure/<deployment>', 'openai/<model>' or a DecisionProvider instance."
    )


__all__ = [
    "DecisionAnswer",
    "DecisionProvider",
    "DecisionProviderError",
    "DecisionQuestion",
    "FakeDecider",
    "OpenAIDecisionsProvider",
    "SystemOneProvider",
    "resolve_provider",
]
