"""
Scenario 1 — Typed-Output Skill (compile-time, happy path)

Proposed developer experience. Nothing behind this is wired yet.
Read alongside ../example_skills/invoice-extractor/SKILL.md
and WALKTHROUGH.md.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from flock import Flock


class RawInvoice(BaseModel):
    pdf_bytes: bytes
    filename: str | None = None


class InvoiceExtracted(BaseModel):
    vendor: str
    invoice_number: str
    total_due: float = Field(description="Amount in vendor's currency")
    due_date: str = Field(description="ISO 8601 date")
    line_items: list[dict] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


async def main() -> None:
    flock = Flock()

    extractor = (
        flock.agent("invoice-extractor")
        .consumes(RawInvoice)
        .publishes(InvoiceExtracted)
        # === THE ONLY NEW API SURFACE ===
        .with_skills("./example_skills/invoice-extractor/")
    )

    async with flock.run() as session:
        await session.publish(
            RawInvoice(
                pdf_bytes=Path("sample-invoice.pdf").read_bytes(),
                filename="sample-invoice.pdf",
            )
        )
        await session.run_until_idle()

        result = session.query(InvoiceExtracted).one()
        print(f"Vendor: {result.vendor}")
        print(f"Total Due: ${result.total_due:,.2f}")
        print(f"Due Date: {result.due_date}")
        print(f"Confidence: {result.confidence:.2%}")


# Key surface properties demonstrated:
#   1. .with_skills() takes a directory path — recursive SKILL.md discovery
#   2. Skill becomes invisible at runtime — agent usage is identical to skill-less agents
#   3. Typed publish (InvoiceExtracted) still works via blackboard cascade —
#      any downstream agent consuming InvoiceExtracted fires automatically
#   4. The skill body is compiled into the agent's dspy.Signature at registration,
#      not loaded at runtime. Zero tool-call overhead per invocation.
