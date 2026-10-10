"""Choice types: a closed option set that a decision agent picks from.

A ``Choice`` subclass declares its options as string attributes. The attribute
value describes the option and is sent to the decision model as its criteria;
the class docstring is the question::

    class Route(Choice):
        \"\"\"Which team should handle this support ticket?\"\"\"

        billing = "Charges, invoices, refunds"
        tech = "Bugs, crashes, login problems"

After class creation every option attribute is a :class:`ChoiceRef`, a
subscription handle that ``AgentBuilder.consumes()`` accepts in place of a
type (``.consumes(Route.billing)``). ``Route.UNSURE`` matches decisions below
the decider's threshold and ``Route.ANY`` matches every decision.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pydantic import BaseModel


UNSURE = "UNSURE"
"""Choice value of a decision whose top probability is below the threshold."""

ANY_OPTION = "ANY"
"""Handle option that matches every decision of a question."""

_RESERVED = frozenset({UNSURE, ANY_OPTION})

# The systemone protocol accepts at most 255 options per choice question
# and 2-10 levels per score question.
MAX_OPTIONS = 255
MAX_LEVELS = 10


_MODE_SUFFIX = {"exact": "", "at_least": ".or_higher", "at_most": ".or_lower"}


@dataclass(frozen=True)
class ChoiceRef:
    """Subscription handle for one option of a question.

    ``mode`` is ``exact`` (the decision chose this option) or, for
    :class:`Scale` levels, ``at_least`` / ``at_most`` (the decision's weighted
    score is at or above / at or below this level).
    """

    choice: type[Question]
    option: str
    mode: str = "exact"

    def matches(self, decision: BaseModel) -> bool:
        """Return True if ``decision`` satisfies this handle."""
        if self.option == ANY_OPTION:
            return True
        if self.mode == "exact":
            return getattr(decision, "choice", None) == self.option
        score = getattr(decision, "score", None)
        if score is None:
            return False
        level = list(self.choice.__options__).index(self.option)
        return score >= level if self.mode == "at_least" else score <= level

    def _scale_level(self, mode: str) -> ChoiceRef:
        if (
            self.choice.__kind__ != "scale"
            or self.mode != "exact"
            or self.option in _RESERVED
        ):
            raise AttributeError(
                f"{self!r} has no {_MODE_SUFFIX[mode][1:]}: only Scale levels do."
            )
        return ChoiceRef(self.choice, self.option, mode)

    @property
    def or_higher(self) -> ChoiceRef:
        """Scale handle: the weighted score is at or above this level."""
        return self._scale_level("at_least")

    @property
    def or_lower(self) -> ChoiceRef:
        """Scale handle: the weighted score is at or below this level."""
        return self._scale_level("at_most")

    def __repr__(self) -> str:
        return f"{self.choice.__name__}.{self.option}{_MODE_SUFFIX[self.mode]}"


class _QuestionMeta(type):
    """Collects option attributes and replaces them with :class:`ChoiceRef`."""

    def __new__(
        mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> _QuestionMeta:
        options: dict[str, str] = {}
        for key, value in namespace.items():
            if key.startswith("_") or not isinstance(value, str):
                continue
            if key in _RESERVED:
                raise TypeError(
                    f"'{name}' cannot declare an option named '{key}': "
                    f"{key} is reserved for {name}.{key}."
                )
            options[key] = value

        cls = super().__new__(mcls, name, bases, namespace)
        if namespace.get("__root__", False):  # Question, Choice, YesNo, Scale
            cls.__options__ = {}
            cls.__question__ = ""
            return cls

        kind = cls.__kind__
        if kind == "yesno":
            extra = sorted(set(options) - {"yes", "no"})
            if extra:
                raise TypeError(
                    f"YesNo '{name}' accepts only 'yes' and 'no' descriptions, "
                    f"got: {', '.join(extra)}."
                )
            options = {"yes": options.get("yes", ""), "no": options.get("no", "")}
        elif kind == "scale":
            if not 2 <= len(options) <= MAX_LEVELS:
                raise TypeError(
                    f"Scale '{name}' must declare between 2 and {MAX_LEVELS} levels, "
                    f"got {len(options)}."
                )
        else:
            if len(options) < 2:
                raise TypeError(
                    f"Choice '{name}' must declare at least two options, got {len(options)}."
                )
            if len(options) > MAX_OPTIONS:
                raise TypeError(
                    f"Choice '{name}' declares {len(options)} options; "
                    f"decision models accept at most {MAX_OPTIONS}."
                )

        cls.__options__ = options
        doc = namespace.get("__doc__")
        default = f"{name}?" if kind == "yesno" else f"Which {name} option applies?"
        cls.__question__ = inspect.cleandoc(doc) if doc else default
        for option in options:
            setattr(cls, option, ChoiceRef(cls, option))
        cls.UNSURE = ChoiceRef(cls, UNSURE)
        cls.ANY = ChoiceRef(cls, ANY_OPTION)
        return cls


# Backwards-compatible name
ChoiceMeta = _QuestionMeta


class Question(metaclass=_QuestionMeta):
    """Base of all decision questions: :class:`Choice`, :class:`YesNo`, :class:`Scale`."""

    __root__ = True
    __kind__ = "choice"
    __options__: dict[str, str]
    __question__: str

    def __init__(self) -> None:
        raise TypeError(
            "Question classes are not instantiated; use their options as handles."
        )


class Choice(Question):
    """One option out of a closed set (see module docstring)."""

    __root__ = True
    __kind__ = "choice"


class YesNo(Question):
    """A yes/no question; optional ``yes = "..."`` / ``no = "..."`` describe the answers.

    Asked natively (systemone ``noul``, OpenAI ``predicate``). Handles:
    ``.yes``, ``.no``, ``.UNSURE``, ``.ANY``.
    """

    __root__ = True
    __kind__ = "yesno"


class Scale(Question):
    """Ordered levels, lowest first (2-10). The decision carries the most probable
    level and the probability-weighted ``score`` (0 = lowest level).

    Handles: ``.<level>`` (most probable level), ``.<level>.or_higher`` and
    ``.<level>.or_lower`` (weighted score at or above / below the level).
    """

    __root__ = True
    __kind__ = "scale"


__all__ = [
    "ANY_OPTION",
    "MAX_LEVELS",
    "MAX_OPTIONS",
    "UNSURE",
    "Choice",
    "ChoiceRef",
    "Question",
    "Scale",
    "YesNo",
]
