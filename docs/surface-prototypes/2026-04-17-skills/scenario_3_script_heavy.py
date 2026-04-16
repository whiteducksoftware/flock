"""
Scenario 3 — Script-Heavy Skill (scripts/ + references/)

Demonstrates skill with executable helpers. Scripts auto-surface as
Flock tools; references/ stay lazy (read_skill_resource tool).
Engine auto-upgrades to dspy.ReAct because scripts are present.

Read alongside ../example_skills/pdf-extract/SKILL.md.
"""
from __future__ import annotations

from pydantic import BaseModel

from flock import Flock


class PDFPath(BaseModel):
    path: str
    password: str | None = None


class ExtractedText(BaseModel):
    text: str
    page_count: int
    extraction_method: str  # "native" | "ocr"
    tables: list[dict] = []


async def main() -> None:
    flock = Flock()

    extractor = (
        flock.agent("pdf-extractor")
        .consumes(PDFPath)
        .publishes(ExtractedText)
        .with_skills("./example_skills/pdf-extract/")
    )

    async with flock.run() as session:
        await session.publish(PDFPath(path="/tmp/some-invoice.pdf"))
        await session.run_until_idle()

        result = session.query(ExtractedText).one()
        print(f"Extracted {len(result.text)} chars from {result.page_count} pages "
              f"via {result.extraction_method}")


# Key surface properties demonstrated:
#   1. scripts/*.py in a SKILL.md are auto-surfaced as Flock tools.
#      The agent sees: pdf-extract__extract_text, pdf-extract__detect_scanned
#   2. Engine silently upgrades Predict → ReAct because scripts are present
#   3. references/ stay lazy — loaded only if agent calls read_skill_resource
#   4. flock.sandbox: subprocess in frontmatter opts into subprocess isolation;
#      default is in-process (cheap, trusted).
#   5. Tool names are namespaced (<skill>__<script>) to prevent collisions when
#      multiple skills define similarly-named scripts
