"""
PII detector: combines regex patterns and spaCy NER to identify personal data.

Detection strategy for names:
  1. Explicit label "Prénom: X"  → mark X as PRENOM_SKIP (do not redact)
  2. Explicit label "Nom: X"     → redact X
  3. spaCy PERSON entity tokens:
       - All-uppercase token (e.g. DUPONT, DUPONT-MARTIN) → NOM → redact
       - Mixed-case token (e.g. Jean, Jean-Pierre)        → PRENOM → keep
  4. Ambiguous PERSON entity (no label, non-uniform case):
       - First mixed-case token → presumed PRENOM → keep
       - Remaining tokens → redact
"""
from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from .models import OcrWord, PiiMatch, PiiType

# ---------------------------------------------------------------------------
# Regex patterns for structured PII
# ---------------------------------------------------------------------------

PATTERNS: Dict[str, str] = {
    "EMAIL": r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    "PHONE": r"(?:(?:\+|00)33[\s.\-]?|0)[1-9](?:[\s.\-]?\d{2}){4}",
    # French social security number (13 digits + 2-digit key, spaces allowed)
    "SSN": r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b",
    # Credit card (4×4 digits, spaces or dashes optional)
    "CB": r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
    # French CNI: 12 digits or 2 letters + 6 digits (old format)
    "CNI": r"\b\d{12}\b|\b[A-Z]{2}\d{6}\b",
}

# Patterns that are triggered by a French label keyword
LABEL_PATTERNS: Dict[str, Tuple[str, PiiType]] = {
    "NOM": (
        r"(?i)nom\s*(?:de\s*famille)?\s*[:\-]\s*"
        r"([A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ][A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸA-zàâæçéèêëîïôœùûüÿ\-\s]+)",
        PiiType.NOM,
    ),
    "PRENOM": (
        r"(?i)pr[eé]nom\s*[:\-]\s*(\S+(?:\-\S+)*)",
        PiiType.NOM,  # type ignored — marked PRENOM_SKIP during detection
    ),
    "ADRESSE": (
        r"(?i)adresse\s*(?:postale|mail|e-?mail)?\s*[:\-]\s*(.+?)(?=\n|$)",
        PiiType.ADRESSE,
    ),
    "TEL": (
        r"(?i)t[eé]l[eé](?:phone)?\s*[:\-]\s*([\d\s\.\-\+]+)",
        PiiType.TELEPHONE,
    ),
}

# Titles that may precede a full name across one or two lines
NAME_TITLES = re.compile(
    r"(?i)\b(M\.|Mme\.?|Monsieur|Madame|Dr\.?|Docteur|Me\.?|Ma[îi]tre)\b"
)

# A token that is a compound last name: all-uppercase, optionally hyphenated
_COMPOUND_NOM_RE = re.compile(
    r"^[A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ][A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ]+"
    r"(?:-[A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ][A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ]+)*$"
)

# A typical French first name: starts with uppercase, rest lowercase, optionally hyphenated
_FIRSTNAME_RE = re.compile(
    r"^[A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ][a-zàâæçéèêëîïôœùûüÿ]{1,}"
    r"(?:-[A-ZÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ][a-zàâæçéèêëîïôœùûüÿ]+)*$"
)

# Particles that can appear inside a compound last name (DE, DU, DE LA …)
_PARTICLE_RE = re.compile(r"^(DE|DU|DES|D|LE|LA|LES)$")


def load_nlp_model():
    """Load the spaCy French model. Called once at startup."""
    import spacy  # type: ignore
    try:
        return spacy.load("fr_core_news_lg")
    except OSError:
        return spacy.load("fr_core_news_sm")


def classify_name_token(token: str) -> str:
    """
    Classify a name token as 'NOM' or 'PRENOM'.

    Convention: French last names are written in ALL CAPS.
    Compound last names like DUPONT-MARTIN are also all-caps.
    First names are in mixed case: Jean, Jean-Pierre.
    """
    # Strip punctuation for comparison
    clean = token.strip(".,;:!?\"'()")
    if not clean:
        return "PRENOM"
    if _COMPOUND_NOM_RE.match(clean):
        return "NOM"
    return "PRENOM"


def group_multiline_names(ocr_words: List[OcrWord]) -> List[List[OcrWord]]:
    """
    Find groups of OcrWords that form a multi-line name.

    Pattern: a civility title (M., Mme, etc.) followed on the next line
    by all-caps tokens within the same Tesseract block.

    Returns a list of word groups that should be treated as one name entity.
    """
    groups: List[List[OcrWord]] = []
    i = 0
    while i < len(ocr_words):
        word = ocr_words[i]
        if NAME_TITLES.match(word.text):
            group = [word]
            j = i + 1
            # Gather remaining words on the same line
            while j < len(ocr_words) and ocr_words[j].line_num == word.line_num:
                group.append(ocr_words[j])
                j += 1
            # Check next line in the same block for all-caps continuation
            if j < len(ocr_words):
                next_word = ocr_words[j]
                same_block = next_word.block_num == word.block_num
                next_line = next_word.line_num == word.line_num + 1
                # Also allow close proximity: vertical gap < 1.5× line height
                close_proximity = abs(
                    next_word.img_y - (word.img_y + word.img_h)
                ) < word.img_h * 1.5
                if same_block or (next_line and close_proximity):
                    while j < len(ocr_words) and ocr_words[j].line_num == next_word.line_num:
                        group.append(ocr_words[j])
                        j += 1
            if len(group) > 1:
                groups.append(group)
            i = j
        else:
            i += 1
    return groups


def regex_detect(full_text: str) -> Tuple[List[PiiMatch], List[Tuple[int, int]]]:
    """
    Apply all regex patterns to the full OCR text.

    Returns:
        matches: list of PiiMatch (words list is empty — resolved later via char_to_word)
        prenom_spans: list of (start, end) character spans to exclude from NOM redaction
    """
    matches: List[PiiMatch] = []
    prenom_spans: List[Tuple[int, int]] = []

    # Structured PII patterns
    pii_type_map = {
        "EMAIL": PiiType.EMAIL,
        "PHONE": PiiType.TELEPHONE,
        "SSN": PiiType.SECU,
        "CB": PiiType.CB,
        "CNI": PiiType.CNI,
    }
    for key, pattern in PATTERNS.items():
        for m in re.finditer(pattern, full_text):
            matches.append(PiiMatch(
                pii_type=pii_type_map[key],
                words=[],
                raw_text=m.group(0),
                char_start=m.start(),
                char_end=m.end(),
            ))

    # Label-based patterns
    for key, (pattern, pii_type) in LABEL_PATTERNS.items():
        for m in re.finditer(pattern, full_text, re.MULTILINE):
            # Group 1 is the actual value after the label
            value_start = m.start(1)
            value_end = m.end(1)
            value_text = m.group(1).strip()
            if not value_text:
                continue
            if key == "PRENOM":
                # Record as a span to exclude but do not add as a redaction match
                prenom_spans.append((value_start, value_end))
            else:
                matches.append(PiiMatch(
                    pii_type=pii_type,
                    words=[],
                    raw_text=value_text,
                    char_start=value_start,
                    char_end=value_end,
                ))

    return matches, prenom_spans


def ner_detect(
    full_text: str,
    ocr_words: List[OcrWord],
    char_to_word: Dict[int, int],
    nlp,
    prenom_spans: List[Tuple[int, int]],
) -> List[PiiMatch]:
    """
    Run spaCy NER and extract PERSON and LOC entities as PiiMatch objects.

    For PERSON entities, classifies each token as NOM or PRENOM and only
    returns NOM tokens (PRENOM tokens are kept).
    """
    matches: List[PiiMatch] = []
    doc = nlp(full_text)

    def is_in_prenom_span(start: int, end: int) -> bool:
        return any(s <= start and end <= e for s, e in prenom_spans)

    for ent in doc.ents:
        if ent.label_ == "PER":
            # Split entity into tokens and classify each
            nom_words: List[OcrWord] = []
            nom_text_parts: List[str] = []
            first_mixed_case_seen = False

            for token in ent:
                if token.is_space or token.is_punct:
                    continue
                t_start = token.idx
                t_end = token.idx + len(token.text)

                if is_in_prenom_span(t_start, t_end):
                    continue

                classification = classify_name_token(token.text)

                if classification == "PRENOM":
                    if not first_mixed_case_seen:
                        # First mixed-case token: presumed first name → keep
                        first_mixed_case_seen = True
                        continue
                    # Subsequent mixed-case tokens after a first name → also keep
                    continue
                else:
                    # NOM: all-uppercase → redact
                    word_indices: Set[int] = set()
                    for char_idx in range(t_start, t_end):
                        if char_idx in char_to_word:
                            word_indices.add(char_to_word[char_idx])
                    if word_indices:
                        token_words = [ocr_words[i] for i in sorted(word_indices)]
                        nom_words.extend(token_words)
                        nom_text_parts.append(token.text)

            if nom_words:
                matches.append(PiiMatch(
                    pii_type=PiiType.NOM,
                    words=nom_words,
                    raw_text=" ".join(nom_text_parts),
                    char_start=ent.start_char,
                    char_end=ent.end_char,
                ))

        elif ent.label_ in ("LOC", "GPE"):
            # Only redact LOC if it follows an address label — skip standalone cities
            # (to avoid redacting e.g. "Paris" in general context)
            # Here we only act on multi-word locations to reduce false positives
            if len(ent.text.split()) >= 2:
                word_indices: Set[int] = set()
                for char_idx in range(ent.start_char, ent.end_char):
                    if char_idx in char_to_word:
                        word_indices.add(char_to_word[char_idx])
                if word_indices:
                    loc_words = [ocr_words[i] for i in sorted(word_indices)]
                    matches.append(PiiMatch(
                        pii_type=PiiType.ADRESSE,
                        words=loc_words,
                        raw_text=ent.text,
                        char_start=ent.start_char,
                        char_end=ent.end_char,
                    ))

    return matches


def _remove_overlapping(matches: List[PiiMatch]) -> List[PiiMatch]:
    """Remove duplicate / overlapping matches (keep the one with the largest span)."""
    if not matches:
        return []
    sorted_matches = sorted(matches, key=lambda m: m.char_start)
    result: List[PiiMatch] = [sorted_matches[0]]
    for match in sorted_matches[1:]:
        prev = result[-1]
        if match.char_start < prev.char_end:
            # Overlapping: keep the one covering more characters
            if (match.char_end - match.char_start) > (prev.char_end - prev.char_start):
                result[-1] = match
        else:
            result.append(match)
    return result


def _word_char_range(char_to_word: Dict[int, int]) -> Dict[int, Tuple[int, int]]:
    """Build a word_idx → (char_start, char_end) mapping from char_to_word."""
    buckets: Dict[int, List[int]] = {}
    for char_idx, word_idx in char_to_word.items():
        buckets.setdefault(word_idx, []).append(char_idx)
    return {idx: (min(chars), max(chars) + 1) for idx, chars in buckets.items()}


def rule_based_name_detect(
    ocr_words: List[OcrWord],
    char_to_word: Dict[int, int],
) -> List[PiiMatch]:
    """
    Fallback rule-based name detection.

    Pattern: a mixed-case token (first name) followed by one or more ALL-CAPS
    tokens (last names), optionally separated by particles (DE, DU …).

    This catches cases where spaCy fails to recognise the PERSON entity
    (common in email-header contexts with uncommon names).
    """
    wcr = _word_char_range(char_to_word)
    matches: List[PiiMatch] = []
    n = len(ocr_words)

    _STRIP = str.maketrans("", "", ".,;:!?\"'<>()[]")

    for i, word in enumerate(ocr_words):
        clean = word.text.translate(_STRIP)
        if not _FIRSTNAME_RE.match(clean):
            continue

        j = i + 1
        nom_group: List[Tuple[int, OcrWord]] = []  # (word_idx_in_list, word)

        while j < n:
            w = ocr_words[j]
            wclean = w.text.translate(_STRIP).strip()

            # Require at least 4 chars to avoid false positives on "RE", "GO", etc.
            if _COMPOUND_NOM_RE.match(wclean) and len(wclean) >= 4:
                nom_group.append((j, w))
                j += 1
            elif _PARTICLE_RE.match(wclean):
                if nom_group:
                    # Particle after a confirmed NOM — always include (handles
                    # "PONCELIN DE" even when what follows is an email or comma)
                    nom_group.append((j, w))
                    j += 1
                elif j + 1 < n:
                    # Particle at the start: only include if followed by ALL-CAPS
                    next_clean = ocr_words[j + 1].text.translate(_STRIP).strip()
                    if _COMPOUND_NOM_RE.match(next_clean) and len(next_clean) >= 4:
                        nom_group.append((j, w))
                        j += 1
                    else:
                        break
                else:
                    break
            else:
                break

        for word_idx, nw in nom_group:
            cs, ce = wcr.get(word_idx, (0, 0))
            matches.append(PiiMatch(
                pii_type=PiiType.NOM,
                words=[nw],
                raw_text=nw.text,
                char_start=cs,
                char_end=ce,
            ))

    return matches


def word_level_phone_detect(
    ocr_words: List[OcrWord],
    char_to_word: Dict[int, int],
) -> List[PiiMatch]:
    """
    Detect phone numbers split across OCR tokens.

    Joins up to 6 consecutive same-block tokens and scans for the phone pattern.
    Handles e.g. '06' + '12' + '34' + '56' + '78' as separate tokens.
    """
    PHONE_RE = re.compile(
        r"(?:(?:\+|00)33[\s.\-]?|0)[1-9](?:[\s.\-]?\d{2}){4}"
    )
    wcr = _word_char_range(char_to_word)
    matches: List[PiiMatch] = []
    n = len(ocr_words)
    seen_word_sets: List[frozenset] = []

    for i in range(n):
        for end in range(i + 1, min(i + 7, n + 1)):
            group = ocr_words[i:end]
            # Only join tokens from the same block
            if len({w.block_num for w in group}) > 1:
                break

            joined = " ".join(w.text for w in group)
            m = PHONE_RE.search(joined)
            if not m:
                continue

            word_idx_set = frozenset(range(i, end))
            if any(word_idx_set <= s for s in seen_word_sets):
                continue
            seen_word_sets.append(word_idx_set)

            ranges = [wcr[wi] for wi in range(i, end) if wi in wcr]
            if ranges:
                cs = min(r[0] for r in ranges)
                ce = max(r[1] for r in ranges)
            else:
                cs, ce = 0, 0

            matches.append(PiiMatch(
                pii_type=PiiType.TELEPHONE,
                words=list(group),
                raw_text=m.group(0),
                char_start=cs,
                char_end=ce,
            ))
            break

    return matches


def word_level_email_detect(
    ocr_words: List[OcrWord],
    char_to_word: Dict[int, int],
) -> List[PiiMatch]:
    """
    Detect email addresses that Tesseract split across multiple tokens.

    Tries joining up to 3 consecutive same-line tokens and scanning for
    the email regex (handles splits like ``<alain.bare`` + ``@ima.eu>``).
    """
    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    wcr = _word_char_range(char_to_word)
    matches: List[PiiMatch] = []
    n = len(ocr_words)
    seen_word_sets: List[frozenset] = []

    for i in range(n):
        for end in range(i + 1, min(i + 4, n + 1)):
            group = ocr_words[i:end]
            # Only join tokens on the same block+line
            if len({(w.block_num, w.line_num) for w in group}) > 1:
                break

            joined = "".join(w.text for w in group)
            if "@" not in joined:
                continue

            m = EMAIL_RE.search(joined)
            if not m:
                continue

            word_idx_set = frozenset(range(i, end))
            # Skip if already covered by a previous (larger) group
            if any(word_idx_set <= s for s in seen_word_sets):
                continue
            seen_word_sets.append(word_idx_set)

            ranges = [wcr[wi] for wi in range(i, end) if wi in wcr]
            if ranges:
                cs = min(r[0] for r in ranges)
                ce = max(r[1] for r in ranges)
            else:
                cs, ce = 0, 0

            matches.append(PiiMatch(
                pii_type=PiiType.EMAIL,
                words=list(group),
                raw_text=m.group(0),
                char_start=cs,
                char_end=ce,
            ))
            break  # one email match per starting word is enough

    return matches


def detect_pii(
    ocr_words: List[OcrWord],
    full_text: str,
    char_to_word: Dict[int, int],
    nlp,
) -> List[PiiMatch]:
    """
    Main PII detection entry point.

    Combines regex detection (structured PII) and NER (names, addresses).
    Deduplicates overlapping matches.
    """
    regex_matches, prenom_spans = regex_detect(full_text)
    ner_matches = ner_detect(full_text, ocr_words, char_to_word, nlp, prenom_spans)
    rule_matches = rule_based_name_detect(ocr_words, char_to_word)
    email_matches = word_level_email_detect(ocr_words, char_to_word)
    phone_matches = word_level_phone_detect(ocr_words, char_to_word)

    all_matches = regex_matches + ner_matches + rule_matches + email_matches + phone_matches
    return _remove_overlapping(all_matches)
