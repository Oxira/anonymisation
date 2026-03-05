"""
OCR module: renders PDF pages to PIL images and extracts word-level bounding boxes.

Supports Tesseract (CPU, default) and EasyOCR (GPU with ROCm/CUDA if available).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import fitz  # PyMuPDF
from PIL import Image

from .models import OcrWord

RENDER_DPI = 300
TESSERACT_LANG = "fra"
TESSERACT_CONFIG = "--oem 3 --psm 3"
MIN_CONFIDENCE = 30.0


def detect_ocr_engine() -> str:
    """Return 'easyocr' if a ROCm/CUDA-capable GPU is detected, else 'tesseract'."""
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            return "easyocr"
    except ImportError:
        pass
    return "tesseract"


def render_page_to_image(page: fitz.Page, dpi: int = RENDER_DPI) -> Image.Image:
    """
    Render a PyMuPDF page to a PIL RGB image at the given DPI.

    The zoom factor dpi/72 converts PDF points (72pt/inch) to pixels.
    """
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def run_ocr_tesseract(image: Image.Image, page_num: int,
                       min_confidence: float = MIN_CONFIDENCE) -> List[OcrWord]:
    """Run Tesseract OCR on a PIL image and return word-level OcrWord list."""
    import pytesseract  # type: ignore
    from pytesseract import Output  # type: ignore

    data = pytesseract.image_to_data(
        image,
        lang=TESSERACT_LANG,
        config=TESSERACT_CONFIG,
        output_type=Output.DICT,
    )

    words: List[OcrWord] = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        if not text or conf < min_confidence:
            continue
        words.append(OcrWord(
            text=text,
            page_num=page_num,
            img_x=int(data["left"][i]),
            img_y=int(data["top"][i]),
            img_w=int(data["width"][i]),
            img_h=int(data["height"][i]),
            confidence=conf,
            line_num=int(data["line_num"][i]),
            block_num=int(data["block_num"][i]),
        ))
    return words


def run_ocr_easyocr(image: Image.Image, page_num: int,
                     min_confidence: float = MIN_CONFIDENCE) -> List[OcrWord]:
    """Run EasyOCR on a PIL image and return word-level OcrWord list."""
    import easyocr  # type: ignore
    import numpy as np

    reader = easyocr.Reader(["fr"], gpu=True)
    img_array = np.array(image)
    results = reader.readtext(img_array, detail=1, paragraph=False)

    words: List[OcrWord] = []
    for bbox, text, conf in results:
        text = text.strip()
        if not text or conf * 100 < min_confidence:
            continue
        # bbox is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] (polygon)
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
        words.append(OcrWord(
            text=text,
            page_num=page_num,
            img_x=x0,
            img_y=y0,
            img_w=x1 - x0,
            img_h=y1 - y0,
            confidence=conf * 100,
        ))
    return words


def run_ocr(image: Image.Image, page_num: int,
            engine: str = "auto",
            min_confidence: float = MIN_CONFIDENCE) -> List[OcrWord]:
    """
    Run OCR on a PIL image.

    engine: 'tesseract' | 'easyocr' | 'auto' (auto-detects GPU)
    """
    if engine == "auto":
        engine = detect_ocr_engine()
    if engine == "easyocr":
        try:
            return run_ocr_easyocr(image, page_num, min_confidence)
        except Exception:
            # Fallback to Tesseract if EasyOCR fails
            return run_ocr_tesseract(image, page_num, min_confidence)
    return run_ocr_tesseract(image, page_num, min_confidence)


def extract_full_text(words: List[OcrWord]) -> Tuple[str, Dict[int, int]]:
    """
    Reconstruct a flat string from the OCR word list.

    Returns:
        full_text: space/newline separated string preserving line structure
        char_to_word: mapping from character offset in full_text to word index in words list
    """
    if not words:
        return "", {}

    parts: List[str] = []
    char_to_word: Dict[int, int] = {}
    offset = 0

    prev_line = words[0].line_num
    prev_block = words[0].block_num

    for idx, word in enumerate(words):
        # Insert newline between lines or blocks
        if word.block_num != prev_block or word.line_num != prev_line:
            parts.append("\n")
            offset += 1
            prev_line = word.line_num
            prev_block = word.block_num
        elif parts:
            parts.append(" ")
            offset += 1

        for _ in word.text:
            char_to_word[offset] = idx
            offset += 1
        parts.append(word.text)

    full_text = "".join(parts)
    return full_text, char_to_word
