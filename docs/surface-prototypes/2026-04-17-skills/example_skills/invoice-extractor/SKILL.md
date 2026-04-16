---
name: invoice-extractor
description: Extract structured data from unpaid invoice PDFs with high accuracy on totals and due dates.
license: MIT

flock:
  outputs: flock.examples.schemas.InvoiceExtracted
  demos: ./demos.jsonl
---

## When to use

Use when given a raw invoice PDF or image and asked to extract structured fields.
Prioritize the **total amount due** and **payment due date** — these are the most
frequently-wrong fields in downstream processing.

## How to extract

1. Scan header for vendor name and invoice number
2. Locate the "Total Due" / "Balance Due" field — not "Subtotal"
3. Parse the due date in ISO 8601
4. If line items are present, extract as a list; otherwise leave empty

## Common failure modes

- **Credit memos mistaken for invoices** — check if total is negative
- **Multi-page invoices** where totals are on page 2+
- **Stamped "PAID" invoices** — these shouldn't flow through the unpaid pipeline
