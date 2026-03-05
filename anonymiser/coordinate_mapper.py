"""
Coordinate mapper: converts OCR pixel coordinates to PDF point coordinates.

OCR bounding boxes are in pixels on the rendered image.
PyMuPDF works in PDF points (72 pt/inch, origin at top-left of page).

Scale factors:
    scale_x = page.rect.width  / image.width
    scale_y = page.rect.height / image.height
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import fitz  # PyMuPDF
from PIL import Image

from .models import OcrWord, PiiMatch, RedactionZone

# Small padding added around each redaction rectangle (in PDF points)
REDACTION_PADDING = 1.5


def get_scale(page: fitz.Page, image: Image.Image) -> Tuple[float, float]:
    """
    Return (scale_x, scale_y) to convert pixel coordinates → PDF points.
    """
    scale_x = page.rect.width / image.width
    scale_y = page.rect.height / image.height
    return scale_x, scale_y


def words_to_pdf_rect(
    words: List[OcrWord],
    scale_x: float,
    scale_y: float,
    padding: float = REDACTION_PADDING,
) -> fitz.Rect:
    """
    Compute the union bounding box of a list of OcrWords in PDF point coordinates.
    Adds a small padding to ensure the rectangle fully covers the text.
    """
    x0 = min(w.img_x for w in words)
    y0 = min(w.img_y for w in words)
    x1 = max(w.img_x + w.img_w for w in words)
    y1 = max(w.img_y + w.img_h for w in words)

    return fitz.Rect(
        x0 * scale_x - padding,
        y0 * scale_y - padding,
        x1 * scale_x + padding,
        y1 * scale_y + padding,
    )


def pii_to_zones(
    pii_matches: List[PiiMatch],
    char_to_word: Dict[int, int],
    ocr_words: List[OcrWord],
    scale_x: float,
    scale_y: float,
    page_num: int,
) -> List[RedactionZone]:
    """
    Convert a list of PiiMatch objects to RedactionZone objects in PDF coordinates.

    PiiMatches that already have .words populated (from NER) are used directly.
    PiiMatches with char_start/char_end (from regex) are resolved via char_to_word.
    """
    zones: List[RedactionZone] = []

    for match in pii_matches:
        # Determine which OcrWords to cover
        if match.words:
            target_words = match.words
        else:
            # Resolve from char_start/char_end using char_to_word map
            word_indices = set()
            for char_idx in range(match.char_start, match.char_end):
                if char_idx in char_to_word:
                    word_indices.add(char_to_word[char_idx])
            if not word_indices:
                continue
            target_words = [ocr_words[i] for i in sorted(word_indices)]

        if not target_words:
            continue

        rect = words_to_pdf_rect(target_words, scale_x, scale_y)
        zones.append(RedactionZone(
            page_num=page_num,
            x0=rect.x0,
            y0=rect.y0,
            x1=rect.x1,
            y1=rect.y1,
        ))

    return zones
