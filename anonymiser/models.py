"""
Shared data models for the PDF anonymisation pipeline.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class PiiType(Enum):
    NOM = "nom"
    EMAIL = "email"
    ADRESSE = "adresse"
    TELEPHONE = "telephone"
    SECU = "securite_sociale"
    CNI = "carte_identite"
    CB = "carte_bancaire"
    OTHER = "other"


@dataclass
class OcrWord:
    """A single word extracted by OCR with its pixel bounding box."""
    text: str
    page_num: int
    img_x: int       # left edge in pixels on the rendered image
    img_y: int       # top edge in pixels on the rendered image
    img_w: int       # width in pixels
    img_h: int       # height in pixels
    confidence: float  # Tesseract confidence 0-100
    line_num: int = 0   # Tesseract line index within block
    block_num: int = 0  # Tesseract block index


@dataclass
class PiiMatch:
    """A detected piece of personally identifiable information."""
    pii_type: PiiType
    words: List[OcrWord]   # one or more consecutive OcrWords forming the match
    raw_text: str          # joined text of matched words
    char_start: int = 0    # character offset in the full_text string
    char_end: int = 0      # character offset end in the full_text string


@dataclass
class RedactionZone:
    """A rectangular area in PDF point coordinates to be redacted."""
    page_num: int
    x0: float
    y0: float
    x1: float
    y1: float
