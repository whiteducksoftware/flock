"""Clients for decision models.

A provider answers one choice question about a state with a probability per
option. Model strings select the provider:

- ``jev/<model>``: TypeSafe Jev (``JEV_API_KEY``; ``JEV_API_BASE`` overrides the endpoint)
- ``local/<name>``: any server speaking ``POST /v1/systemone``, for example
  llama.cpp's ``llama-server`` with a Clef GGUF (``DECISION_API_BASE``,
  default ``http://127.0.0.1:8080``)

Error messages name the provider and the HTTP status only. Response bodies
can echo the state, so they never end up in exceptions.
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx


JEV_DEFAULT_URL = "https://api.typesafe.ai/v1/systemone"
LOCAL_DEFAULT_BASE = "http://127.0.0.1:8080"
SYSTEMONE_PATH = "/v1/systemone"


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
    """Answers choice questions about a state."""

    label: str

    @abstractmethod
    async def decide(self, state: str, question: DecisionQuestion) -> DecisionAnswer:
        """Return the answer to ``question`` about ``state``."""


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
    The choice is the most probable option. Every call is recorded in ``calls``.
    """

    def __init__(
        self,
        probabilities: Mapping[str, float] | Callable[[str], Mapping[str, float]],
        *,
        label: str = "fake",
    ) -> None:
        self._probabilities = probabilities
        self.label = label
        self.calls: list[tuple[str, DecisionQuestion]] = []

    async def decide(self, state: str, question: DecisionQuestion) -> DecisionAnswer:
        self.calls.append((state, question))
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


class SystemOneProvider(DecisionProvider):
    """Client for the ``POST /v1/systemone`` decision protocol."""

    def __init__(
        self,
        url: str,
        *,
        label: str,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url
        self.label = label
        self.model = model
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

    def _body(self, state: str, question: DecisionQuestion) -> dict[str, Any]:
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
        if self.model is not None:
            body = {"model": self.model, **body}
        return body

    async def decide(self, state: str, question: DecisionQuestion) -> DecisionAnswer:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = await self._http().post(
                self.url, json=self._body(state, question), headers=headers
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
            raw = data["answers"][question.name]
            probabilities = {
                str(option): float(p) for option, p in raw["probabilities"].items()
            }
            answer = DecisionAnswer(
                choice=str(raw["choice"]),
                probabilities=probabilities,
                confidence=(
                    float(raw["confidence"])
                    if raw.get("confidence") is not None
                    else None
                ),
                model=data.get("model"),
                input_tokens=(data.get("usage") or {}).get("input_tokens"),
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            raise DecisionProviderError(
                f"Decision provider '{self.label}' returned an unexpected answer shape"
            ) from None
        return _check_options(self.label, question, answer)


def resolve_provider(model: str | DecisionProvider) -> DecisionProvider:
    """Turn a model string (or provider instance) into a provider."""
    if isinstance(model, DecisionProvider):
        return model
    prefix, _, name = model.partition("/")
    if prefix == "jev" and name:
        api_key = os.getenv("JEV_API_KEY")
        if not api_key:
            raise ValueError(f"Decision model '{model}' needs JEV_API_KEY to be set.")
        url = os.getenv("JEV_API_BASE", JEV_DEFAULT_URL)
        return SystemOneProvider(url, label=model, model=name, api_key=api_key)
    if prefix == "local" and name:
        base = os.getenv("DECISION_API_BASE", LOCAL_DEFAULT_BASE).rstrip("/")
        return SystemOneProvider(f"{base}{SYSTEMONE_PATH}", label=model)
    raise ValueError(
        f"Unknown decision model '{model}'. Use 'jev/<model>', 'local/<name>' "
        "or a DecisionProvider instance."
    )


__all__ = [
    "DecisionAnswer",
    "DecisionProvider",
    "DecisionProviderError",
    "DecisionQuestion",
    "FakeDecider",
    "SystemOneProvider",
    "resolve_provider",
]
