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

# The systemone protocol accepts at most 255 options per choice question.
MAX_OPTIONS = 255


@dataclass(frozen=True)
class ChoiceRef:
    """Subscription handle for one option of a :class:`Choice`."""

    choice: type[Choice]
    option: str

    def matches(self, decision: BaseModel) -> bool:
        """Return True if ``decision`` selects this handle's option."""
        if self.option == ANY_OPTION:
            return True
        return getattr(decision, "choice", None) == self.option

    def __repr__(self) -> str:
        return f"{self.choice.__name__}.{self.option}"


class ChoiceMeta(type):
    """Collects option attributes and replaces them with :class:`ChoiceRef`."""

    def __new__(
        mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> ChoiceMeta:
        options: dict[str, str] = {}
        for key, value in namespace.items():
            if key.startswith("_") or not isinstance(value, str):
                continue
            if key in _RESERVED:
                raise TypeError(
                    f"Choice '{name}' cannot declare an option named '{key}': "
                    f"{key} is reserved for {name}.{key}."
                )
            options[key] = value

        cls = super().__new__(mcls, name, bases, namespace)
        if not bases:  # The Choice base class itself declares no options.
            cls.__options__ = {}
            cls.__question__ = ""
            return cls

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
        cls.__question__ = (
            inspect.cleandoc(doc) if doc else f"Which {name} option applies?"
        )
        for option in options:
            setattr(cls, option, ChoiceRef(cls, option))
        cls.UNSURE = ChoiceRef(cls, UNSURE)
        cls.ANY = ChoiceRef(cls, ANY_OPTION)
        return cls


class Choice(metaclass=ChoiceMeta):
    """Base class for a closed option set (see module docstring)."""

    __options__: dict[str, str]
    __question__: str

    def __init__(self) -> None:
        raise TypeError(
            "Choice classes are not instantiated; use their options as handles."
        )


__all__ = ["ANY_OPTION", "MAX_OPTIONS", "UNSURE", "Choice", "ChoiceRef"]
