"""Sections: a long text field decided in parts.

``.decides(Controls, sections=Sections(field="text", max_chars=4000))`` splits
the field into sections at paragraph boundaries, asks every question about
each section and combines the answers: a checklist item is yes if any section
shows it, a choice takes the most confident section.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field


_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


class Sections(BaseModel):
    """How a decider splits a long text field into sections."""

    model_config = ConfigDict(frozen=True)

    field: str = Field(description="Text field of the decided artifact to split")
    max_chars: int = Field(
        default=4000, gt=0, description="Longest section, in characters"
    )
    max_sections: int = Field(
        default=100,
        gt=0,
        description="Most sections per text; a longer text fails before any request",
    )


def _paragraphs(text: str) -> list[tuple[int, int]]:
    """Spans of the paragraphs, without their surrounding whitespace."""
    spans, start = [], 0
    for match in [*_PARAGRAPH_BREAK.finditer(text), None]:
        end = match.start() if match else len(text)
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((start, end))
        if match:
            start = match.end()
    return spans


def _hard_split(
    start: int, end: int, text: str, max_chars: int
) -> list[tuple[int, int]]:
    """A paragraph longer than the limit, cut at whitespace where possible."""
    spans = []
    while end - start > max_chars:
        cut = text.rfind(" ", start + 1, start + max_chars + 1)
        cut = cut if cut > start else start + max_chars
        stop = cut
        while stop > start and text[stop - 1].isspace():  # no trailing blanks
            stop -= 1
        spans.append((start, stop))
        start = cut
        while start < end and text[start].isspace():  # skip the whole separator
            start += 1
    if start < end:  # trailing blanks leave nothing
        spans.append((start, end))
    return spans


def split_sections(text: str, max_chars: int) -> list[tuple[int, int]]:
    """Spans ``(start, end)`` of sections of at most ``max_chars`` characters.

    Paragraphs (separated by blank lines) are packed into sections in order; a
    paragraph longer than the limit is split on its own. A text without
    content is one empty section.
    """
    if max_chars <= 0:
        raise ValueError(f"max_chars must be positive, got {max_chars}")
    sections: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None
    for start, end in _paragraphs(text):
        if end - start > max_chars:
            if current is not None:
                sections.append(current)
                current = None
            sections.extend(_hard_split(start, end, text, max_chars))
        elif current is None:
            current = (start, end)
        elif end - current[0] <= max_chars:
            current = (current[0], end)
        else:
            sections.append(current)
            current = (start, end)
    if current is not None:
        sections.append(current)
    return sections or [(0, len(text))]


__all__ = ["Sections", "split_sections"]
