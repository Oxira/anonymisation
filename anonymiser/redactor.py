"""
Redactor: applies irreversible black rectangle redactions to PDF pages.

Uses PyMuPDF's redaction annotation API which:
  1. Adds a redact annotation over the target area
  2. Calls apply_redactions() which burns the annotation into the page content,
     replacing underlying pixels with the fill colour

The PDF is saved with garbage=4 and deflate=True to ensure no residual data
is retained in the file's cross-reference table. Never use incremental saves.
"""
from __future__ import annotations

from typing import List

import fitz  # PyMuPDF

from .models import RedactionZone

# Solid black fill colour (R, G, B) in 0.0–1.0 range
BLACK = (0.0, 0.0, 0.0)


def apply_redactions(page: fitz.Page, zones: List[RedactionZone]) -> int:
    """
    Apply black rectangle redactions to a PDF page.

    For image-based PDFs, this replaces the pixels under each zone with black,
    making the original content unrecoverable.

    Returns the number of redaction zones applied.
    """
    if not zones:
        return 0

    for zone in zones:
        rect = fitz.Rect(zone.x0, zone.y0, zone.x1, zone.y1)
        page.add_redact_annot(rect, fill=BLACK)

    # PDF_REDACT_IMAGE_PIXELS ensures image pixel data is also overwritten,
    # not just the annotation drawn on top.
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
    return len(zones)


def save_redacted_pdf(doc: fitz.Document, output_path: str) -> None:
    """
    Save the document to output_path with full garbage collection.

    garbage=4: removes all unreferenced objects and cross-references
    deflate=True: compresses streams
    NEVER use incremental=True as it may preserve original data.
    """
    doc.save(
        output_path,
        garbage=4,
        deflate=True,
        incremental=False,
    )
