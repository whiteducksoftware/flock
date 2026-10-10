"""Tournaments: asking a choice with many options in rounds.

Decision models accept at most 255 options per choice question, and long
option descriptions make every request heavier. A tournament splits the
options into groups, asks about all groups of a round in one request (one
choice question per group), keeps the ``keep`` most probable options of each
group and repeats with the survivors until they fit into one final question.

Survivors are picked per group (relative top-k), because probabilities are
normalized within each group and cannot be compared across groups.
"""

from __future__ import annotations

from dataclasses import dataclass

from flock.decisions.choice import MAX_OPTIONS


@dataclass(frozen=True)
class Tournament:
    """How to ask a large Choice: ``group_size`` options per question,
    ``keep`` survivors per group."""

    group_size: int = 20
    keep: int = 3

    def __post_init__(self) -> None:
        if not 2 <= self.group_size <= MAX_OPTIONS:
            raise ValueError(
                f"Tournament group_size must be between 2 and {MAX_OPTIONS}, "
                f"got {self.group_size}."
            )
        if not 1 <= self.keep < self.group_size:
            raise ValueError(
                f"Tournament keep must be at least 1 and below group_size "
                f"({self.group_size}), got {self.keep}."
            )


__all__ = ["Tournament"]
