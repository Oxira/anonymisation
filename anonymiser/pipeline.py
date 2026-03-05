"""
Pipeline: orchestrates the full PDF anonymisation workflow.

For each page:
  1. Render page to PIL image (300 DPI)
  2. Run OCR → List[OcrWord]
  3. Extract full text + char→word map
  4. Detect PII (regex + NER)
  5. Map PII bounding boxes to PDF coordinates
  6. Apply redactions (black rectangles, pixel-level)

Final save uses garbage=4 to ensure no residual data.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

import fitz  # PyMuPDF

from .coordinate_mapper import get_scale, pii_to_zones
from .detector import detect_pii
from .models import RedactionZone
from .ocr import extract_full_text, render_page_to_image, run_ocr
from .redactor import apply_redactions, save_redacted_pdf

ProgressCallback = Optional[Callable[[int, int], None]]


def process_pdf(
    input_path: str,
    output_path: str,
    nlp,
    dpi: int = 300,
    ocr_engine: str = "auto",
    progress_cb: ProgressCallback = None,
) -> int:
    """
    Anonymise a PDF by detecting and redacting all PII.

    Args:
        input_path:  path to the source image-based PDF
        output_path: path where the anonymised PDF will be saved
        nlp:         spaCy language model (loaded once externally)
        dpi:         render resolution for OCR (higher = better accuracy)
        ocr_engine:  'tesseract' | 'easyocr' | 'auto'
        progress_cb: optional callback(current_page, total_pages)

    Returns:
        total number of redaction zones applied across all pages
    """
    doc = fitz.open(input_path)
    total_pages = doc.page_count
    total_redactions = 0

    for page_num in range(total_pages):
        if progress_cb:
            progress_cb(page_num, total_pages)

        page = doc[page_num]

        # Step 1: render page to PIL image
        image = render_page_to_image(page, dpi=dpi)

        # Step 2: OCR
        ocr_words = run_ocr(image, page_num=page_num, engine=ocr_engine)
        if not ocr_words:
            continue

        # Step 3: reconstruct text + character→word mapping
        full_text, char_to_word = extract_full_text(ocr_words)
        if not full_text.strip():
            continue

        # Step 4: detect PII
        pii_matches = detect_pii(ocr_words, full_text, char_to_word, nlp)
        if not pii_matches:
            continue

        # Step 5: convert to PDF coordinate zones
        scale_x, scale_y = get_scale(page, image)
        zones = pii_to_zones(
            pii_matches, char_to_word, ocr_words, scale_x, scale_y, page_num
        )

        # Step 6: apply redactions
        n = apply_redactions(page, zones)
        total_redactions += n

    if progress_cb:
        progress_cb(total_pages, total_pages)

    # Save with full garbage collection — never incremental
    save_redacted_pdf(doc, output_path)
    doc.close()

    return total_redactions


def process_directory(
    input_dir: str,
    output_dir: str,
    nlp,
    dpi: int = 300,
    ocr_engine: str = "auto",
    suffix: str = "_anonymise",
    progress_cb: ProgressCallback = None,
) -> dict:
    """
    Process all PDF files in input_dir and save results to output_dir.

    Returns a dict mapping filename → number of redactions applied.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(input_path.glob("*.pdf"))
    results = {}

    for pdf_file in pdf_files:
        out_file = output_path / (pdf_file.stem + suffix + ".pdf")
        n = process_pdf(
            str(pdf_file),
            str(out_file),
            nlp,
            dpi=dpi,
            ocr_engine=ocr_engine,
            progress_cb=progress_cb,
        )
        results[pdf_file.name] = n

    return results
