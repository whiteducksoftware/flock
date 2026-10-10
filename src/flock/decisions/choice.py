"""Question types: what a decision agent asks a decision model.

``Choice`` (one option of a closed set), ``YesNo``, ``Scale`` (ordered levels)
and ``Checklist`` (many yes/no items answered as one decision).

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
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pydantic import BaseModel


UNSURE = "UNSURE"
"""Choice value of a decision whose top probability is below the threshold."""

ANY_OPTION = "ANY"
"""Handle option that matches every decision of a question."""

PASSED = "passed"
FAILED = "failed"
"""Checklist outcomes: every item answered yes / at least one item answered no."""

_RESERVED = frozenset({UNSURE, ANY_OPTION})
_CHECKLIST_RESERVED = _RESERVED | {PASSED, FAILED}

# The systemone protocol accepts at most 255 options per choice question
# and 2-10 levels per score question.
MAX_OPTIONS = 255
MAX_LEVELS = 10


_MODE_SUFFIX = {
    "exact": "",
    "at_least": ".or_higher",
    "at_most": ".or_lower",
    "item_yes": "",
    "item_no": ".no",
    "item_unsure": f".{UNSURE}",
}
_ITEM_RESULT = {"item_yes": "yes", "item_no": "no", "item_unsure": UNSURE}


@dataclass(frozen=True)
class ChoiceRef:
    """Subscription handle for one option of a question.

    ``mode`` is ``exact`` (the decision chose this option); for
    :class:`Scale` levels ``at_least`` / ``at_most`` (the decision's weighted
    score is at or above / at or below this level); for :class:`Checklist`
    items ``item_yes`` / ``item_no`` / ``item_unsure`` (the item's result).
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
        if self.mode in _ITEM_RESULT:
            results = getattr(decision, "results", None) or {}
            return results.get(self.option) == _ITEM_RESULT[self.mode]
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

    def _item_answer(self, mode: str) -> ChoiceRef:
        if self.mode not in _ITEM_RESULT:
            raise AttributeError(
                f"{self!r} has no {mode}: only Checklist items have yes/no answers."
            )
        return ChoiceRef(self.choice, self.option, mode)

    @property
    def yes(self) -> ChoiceRef:
        """Checklist handle: this item was answered yes."""
        return self._item_answer("item_yes")

    @property
    def no(self) -> ChoiceRef:
        """Checklist handle: this item was answered no."""
        return self._item_answer("item_no")

    @property
    def UNSURE(self) -> ChoiceRef:  # noqa: N802 - mirrors Question.UNSURE
        """Checklist handle: this item's answer is below the threshold or refused."""
        return self._item_answer("item_unsure")

    def __repr__(self) -> str:
        return f"{self.choice.__name__}.{self.option}{_MODE_SUFFIX[self.mode]}"


class _QuestionMeta(type):
    """Collects option attributes and replaces them with :class:`ChoiceRef`."""

    def __new__(
        mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> _QuestionMeta:
        options: dict[str, str] = dict(namespace.pop("__pending_options__", {}))
        kind = namespace.get("__kind__") or next(
            (getattr(base, "__kind__", None) for base in bases), "choice"
        )
        reserved = _CHECKLIST_RESERVED if kind == "checklist" else _RESERVED
        for key, value in namespace.items():
            if key.startswith("_") or not isinstance(value, str):
                continue
            options[key] = value
        for key in options:
            if key in reserved:
                raise TypeError(
                    f"'{name}' cannot declare an option named '{key}': "
                    f"{key} is reserved for {name}.{key}."
                )

        cls = super().__new__(mcls, name, bases, namespace)
        if namespace.get("__root__", False):  # Question, Choice, YesNo, Scale
            cls.__options__ = {}
            cls.__question__ = ""
            return cls

        kind = cls.__kind__
        if kind == "checklist":
            if not options:
                raise TypeError(f"Checklist '{name}' must declare at least one item.")
        elif kind == "yesno":
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
        default = {
            "yesno": f"{name}?",
            "checklist": f"Is this {name} item fulfilled?",
        }.get(kind, f"Which {name} option applies?")
        cls.__question__ = inspect.cleandoc(doc) if doc else default
        item_mode = "item_yes" if kind == "checklist" else "exact"
        for option in options:
            setattr(cls, option, ChoiceRef(cls, option, item_mode))
        if kind == "checklist":
            cls.passed = ChoiceRef(cls, PASSED)
            cls.failed = ChoiceRef(cls, FAILED)
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

    @classmethod
    def _define(
        cls, name: str, options: Mapping[str, str], question: str | None
    ) -> type[Question]:
        namespace: dict[str, Any] = {
            "__module__": sys._getframe(2).f_globals.get("__name__", __name__),
            "__qualname__": name,
        }
        if question:
            namespace["__doc__"] = question
        # Options may come from catalogs; set them after creation so ids that
        # are not identifiers ("ORP.1.A1") work and are reachable via getattr.
        namespace["__pending_options__"] = dict(options)
        return type(cls)(name, (cls,), namespace)


class Choice(Question):
    """One option out of a closed set (see module docstring)."""

    __root__ = True
    __kind__ = "choice"

    @classmethod
    def from_options(
        cls, name: str, options: Mapping[str, str], *, question: str | None = None
    ) -> type[Choice]:
        """Build a Choice from data, e.g. a catalog: option name -> description."""
        return cls._define(name, options, question)


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


class Checklist(Question):
    """Many yes/no items about the same artifact, answered as one decision.

    Items are declared like Choice options (name = description); the docstring
    is the question asked for every item. The decision carries a ``results``
    entry per item (``yes``, ``no`` or ``UNSURE``) and an outcome: ``failed``
    if any item is ``no``, ``UNSURE`` if any item is unsure, ``passed``
    otherwise. Handles: ``.passed``, ``.failed``, ``.UNSURE``, ``.ANY`` and per
    item ``.<item>`` (yes), ``.<item>.no``, ``.<item>.UNSURE``.
    """

    __root__ = True
    __kind__ = "checklist"

    @classmethod
    def from_items(
        cls, name: str, items: Mapping[str, str], *, question: str | None = None
    ) -> type[Checklist]:
        """Build a Checklist from data, e.g. a control catalog: id -> requirement."""
        return cls._define(name, items, question)


__all__ = [
    "ANY_OPTION",
    "FAILED",
    "MAX_LEVELS",
    "MAX_OPTIONS",
    "PASSED",
    "UNSURE",
    "Checklist",
    "Choice",
    "ChoiceRef",
    "Question",
    "Scale",
    "YesNo",
]
