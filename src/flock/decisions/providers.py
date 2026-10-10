"""Clients for decision models.

A provider answers one choice question about a state with a probability per
option. Model strings select the provider:

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
from collections.abc import Callable, Mapping, Sequence
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
    """One choice question: instructions plus option name -> description."""

    name: str
    instructions: str
    options: Mapping[str, str]


@dataclass(frozen=True)
class DecisionAnswer:
    """A decision model's answer to one choice question."""

    choice: str
    probabilities: dict[str, float]
    confidence: float | None = None
    model: str | None = None
    input_tokens: int | None = None


class DecisionProvider(ABC):
    """Answers choice questions about a state (and, if supported, images)."""

    label: str
    supports_images: bool = False

    @abstractmethod
    async def decide(
        self,
        state: str,
        question: DecisionQuestion,
        images: Sequence[Image] = (),
    ) -> DecisionAnswer:
        """Return the answer to ``question`` about ``state`` and ``images``."""


def _check_options(
    label: str, question: DecisionQuestion, answer: DecisionAnswer
) -> DecisionAnswer:
    unknown = ({answer.choice} | set(answer.probabilities)) - set(question.options)
    if unknown:
        raise DecisionProviderError(
            f"Decision provider '{label}' answered with unknown option(s): "
            f"{', '.join(sorted(unknown))}"
        )
    return answer


class FakeDecider(DecisionProvider):
    """Deterministic provider for tests and examples.

    ``probabilities`` is either a fixed mapping or a function of the state.
    The choice is the most probable option. Every call is recorded in ``calls``
    and its images in ``received_images``.
    """

    def __init__(
        self,
        probabilities: Mapping[str, float] | Callable[[str], Mapping[str, float]],
        *,
        label: str = "fake",
        supports_images: bool = True,
    ) -> None:
        self._probabilities = probabilities
        self.label = label
        self.supports_images = supports_images
        self.calls: list[tuple[str, DecisionQuestion]] = []
        self.received_images: list[list[Image]] = []

    async def decide(
        self,
        state: str,
        question: DecisionQuestion,
        images: Sequence[Image] = (),
    ) -> DecisionAnswer:
        self.calls.append((state, question))
        self.received_images.append(list(images))
        source = self._probabilities
        probabilities = dict(source(state) if callable(source) else source)
        if not probabilities:
            raise DecisionProviderError(
                f"Decision provider '{self.label}' returned no probabilities"
            )
        choice = max(probabilities, key=probabilities.__getitem__)
        answer = DecisionAnswer(
            choice=choice,
            probabilities=probabilities,
            confidence=probabilities[choice],
            model=self.label,
        )
        return _check_options(self.label, question, answer)


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
        self, state: str, question: DecisionQuestion, images: Sequence[Image]
    ) -> dict[str, Any]:
        """Request body for one choice question."""

    @abstractmethod
    def _parse(
        self, data: dict[str, Any], question: DecisionQuestion
    ) -> DecisionAnswer:
        """Answer from a decoded response body."""

    async def decide(
        self,
        state: str,
        question: DecisionQuestion,
        images: Sequence[Image] = (),
    ) -> DecisionAnswer:
        if images and not self.supports_images:
            raise DecisionProviderError(
                f"Decision model '{self.label}' does not accept images."
            )
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._http().post(
                self.url, json=self._body(state, question, images), headers=headers
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
            answer = self._parse(response.json(), question)
        except (ValueError, KeyError, TypeError, AttributeError, StopIteration):
            raise DecisionProviderError(
                f"Decision provider '{self.label}' returned an unexpected answer shape"
            ) from None
        if not self.report_server_model:
            answer = replace(answer, model=None)
        return _check_options(self.label, question, answer)


def _float_or_none(value: Any) -> float | None:
    return float(value) if value is not None else None


class SystemOneProvider(_HttpDecisionProvider):
    """Client for the ``POST /v1/systemone`` protocol (Jev, Clef, Decision-1)."""

    def _body(
        self, state: str, question: DecisionQuestion, images: Sequence[Image]
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "state": state,
            "questions": {
                question.name: {
                    "type": "choice",
                    "instructions": question.instructions,
                    "criteria": {
                        option: description or None
                        for option, description in question.options.items()
                    },
                }
            },
        }
        if images:
            body["images"] = [image.base64_data for image in images]
        if self.model is not None:
            body = {"model": self.model, **body}
        return body

    def _parse(
        self, data: dict[str, Any], question: DecisionQuestion
    ) -> DecisionAnswer:
        raw = data["answers"][question.name]
        return DecisionAnswer(
            choice=str(raw["choice"]),
            probabilities={
                str(option): float(p) for option, p in raw["probabilities"].items()
            },
            confidence=_float_or_none(raw.get("confidence")),
            model=data.get("model"),
            input_tokens=(data.get("usage") or {}).get("input_tokens"),
        )


class OpenAIDecisionsProvider(_HttpDecisionProvider):
    """Client for OpenAI's ``POST /v1/decisions`` protocol."""

    supports_images = True

    def _body(
        self, state: str, question: DecisionQuestion, images: Sequence[Image]
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
            "questions": [
                {
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
            ],
        }

    def _parse(
        self, data: dict[str, Any], question: DecisionQuestion
    ) -> DecisionAnswer:
        raw = next(a for a in data["answers"] if a["name"] == question.name)
        return DecisionAnswer(
            choice=str(raw["choice"]),
            probabilities={
                str(p["value"]): float(p["probability"]) for p in raw["probabilities"]
            },
            confidence=_float_or_none(raw.get("confidence")),
            model=data.get("model"),
            input_tokens=(data.get("usage") or {}).get("input_tokens"),
        )


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
