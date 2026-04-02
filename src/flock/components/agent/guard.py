"""Guard component framework for pluggable input/output safety guards.

Provides an abstract base class ``GuardComponent`` that scans agent inputs
(``on_pre_evaluate``) and outputs (``on_post_evaluate``) for unsafe content.
Concrete implementations only need to override ``scan_input`` and/or
``scan_output``, returning a ``GuardVerdict``.

The ``scan_input(text, documents)`` signature takes raw strings so guard
implementations stay backend-focused and do not need to understand Flock
artifact internals.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from flock.components.agent.base import AgentComponent, AgentComponentConfig
from flock.logging.logging import get_logger


if TYPE_CHECKING:  # pragma: no cover - type checking only
    from flock.agent import Agent
    from flock.utils.runtime import Context, EvalInputs, EvalResult

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class GuardVerdict(BaseModel):
    """Result returned by a guard scan."""

    safe: bool
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    provider: str = "unknown"


class GuardComponentConfig(AgentComponentConfig):
    """Configuration shared by all guard components."""

    on_input_flagged: Literal["block", "warn", "annotate"] = "block"
    on_output_flagged: Literal["block", "warn", "annotate"] = "warn"
    scan_input: bool = True
    scan_output: bool = False
    scan_context_artifacts: bool = True


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class GuardBlockedError(Exception):
    """Raised when a guard blocks execution."""

    def __init__(self, verdict: GuardVerdict) -> None:
        self.verdict = verdict
        super().__init__(
            f"Guard '{verdict.provider}' blocked execution: {verdict.reason}"
        )


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class GuardComponent(AgentComponent, abc.ABC):
    """Abstract guard component that scans agent inputs and outputs.

    Concrete subclasses override ``scan_input`` and optionally
    ``scan_output``.  The base class wires those scanners into the
    agent lifecycle via ``on_pre_evaluate`` / ``on_post_evaluate``.

    The ``scan_input(text, documents)`` contract uses raw strings so
    guard backends remain framework-agnostic.
    """

    config: GuardComponentConfig = Field(default_factory=GuardComponentConfig)

    # ------------------------------------------------------------------
    # Scanner interface – implement in subclasses
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def scan_input(
        self,
        text: str,
        documents: list[str] | None = None,
        **kwargs: Any,
    ) -> GuardVerdict:
        """Scan the user prompt and optional context documents.

        Args:
            text: The primary user / agent prompt text.
            documents: Optional context documents (e.g. artifact payloads).

        Returns:
            A ``GuardVerdict`` indicating whether the content is safe.
        """
        ...  # pragma: no cover

    async def scan_output(self, text: str, **kwargs: Any) -> GuardVerdict:
        """Scan agent output text.  Override for output scanning.

        The default implementation passes everything through.
        """
        return GuardVerdict(safe=True, provider=self.name or "unknown")

    # ------------------------------------------------------------------
    # Lifecycle hooks – wired automatically
    # ------------------------------------------------------------------

    async def on_pre_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs
    ) -> EvalInputs:
        """Scan inputs before the engine evaluates."""
        if not self.config.scan_input:
            return inputs

        text = self._extract_prompt_text(inputs)
        documents = (
            self._extract_context_documents(inputs)
            if self.config.scan_context_artifacts
            else None
        )

        verdict = await self.scan_input(text, documents)
        if not verdict.safe:
            self._handle_verdict(
                verdict,
                phase="input",
                action=self.config.on_input_flagged,
                agent_name=agent.name,
            )
        return inputs

    async def on_post_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        """Scan outputs after the engine evaluates."""
        if not self.config.scan_output:
            return result

        text = self._extract_result_text(result)
        if not text:
            return result

        verdict = await self.scan_output(text)
        if not verdict.safe:
            self._handle_verdict(
                verdict,
                phase="output",
                action=self.config.on_output_flagged,
                agent_name=agent.name,
            )
        return result

    # ------------------------------------------------------------------
    # Text extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_prompt_text(inputs: EvalInputs) -> str:
        """Build a single prompt string from input artifacts."""
        parts: list[str] = []
        for artifact in inputs.artifacts:
            for value in artifact.payload.values():
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, str):
                            parts.append(item)
        return " ".join(parts)

    @staticmethod
    def _extract_context_documents(inputs: EvalInputs) -> list[str]:
        """Extract each artifact payload as a separate document string."""
        docs: list[str] = []
        for artifact in inputs.artifacts:
            parts: list[str] = []
            for value in artifact.payload.values():
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, str):
                            parts.append(item)
            if parts:
                docs.append(" ".join(parts))
        return docs

    @staticmethod
    def _extract_result_text(result: EvalResult) -> str:
        """Build a single text string from evaluation result artifacts."""
        parts: list[str] = []
        for artifact in result.artifacts:
            for value in artifact.payload.values():
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        if isinstance(item, str):
                            parts.append(item)
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Verdict routing
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_verdict(
        verdict: GuardVerdict,
        *,
        phase: str,
        action: str,
        agent_name: str,
    ) -> None:
        """Route a non-safe verdict based on the configured action."""
        msg = (
            f"Guard '{verdict.provider}' flagged {phase} for agent "
            f"'{agent_name}': {verdict.reason}"
        )
        if action == "block":
            logger.warning(msg)
            raise GuardBlockedError(verdict)
        elif action == "warn":
            logger.warning(msg)
        elif action == "annotate":
            logger.info(f"[annotate] {msg}")


__all__ = [
    "GuardBlockedError",
    "GuardComponent",
    "GuardComponentConfig",
    "GuardVerdict",
]
