---
name: pdf-extract
description: Extract text from PDF files with layout preservation. Uses pdfplumber for native PDFs and Tesseract for scanned ones.
license: MIT
allowed-tools: [Bash]

flock:
  sandbox: subprocess   # scripts run in isolated subprocess
  scripts:
    extract_text:
      run: python scripts/extract_text.py
      schema: flock.examples.schemas.ExtractTextArgs
    detect_scanned:
      run: python scripts/detect_scanned.py
      schema: flock.examples.schemas.DetectScannedArgs
---

## When to use

Given a PDF path, first call `detect_scanned` to choose the extraction path.
If native: call `extract_text` with `mode=native`.
If scanned: call `extract_text` with `mode=ocr` (slower, requires Tesseract).

## Scripts

- `scripts/extract_text.py` — native text extraction + OCR fallback
- `scripts/detect_scanned.py` — heuristic scanned-vs-native detection

## References

- `references/pdfplumber-cheatsheet.md` — coordinate math, table extraction tricks
- `references/tesseract-tuning.md` — language packs, DPI settings

## Common failure modes

- PDFs with embedded images of text look "native" to `detect_scanned` — fall back to OCR if native extraction returns <100 chars on a page
- Password-protected PDFs require the `password` arg
- Landscape tables need `pdfplumber`'s `extract_tables(table_settings={...})` tuning — see the cheatsheet
