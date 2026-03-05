"""
Unit tests for the PII detector module.

Tests regex patterns and name classification without requiring spaCy.
"""
import pytest

from anonymiser.detector import classify_name_token, regex_detect
from anonymiser.models import PiiType


class TestClassifyNameToken:
    def test_all_caps_is_nom(self):
        assert classify_name_token("DUPONT") == "NOM"

    def test_compound_all_caps_is_nom(self):
        assert classify_name_token("DUPONT-MARTIN") == "NOM"

    def test_mixed_case_is_prenom(self):
        assert classify_name_token("Jean") == "PRENOM"

    def test_compound_mixed_case_is_prenom(self):
        assert classify_name_token("Jean-Pierre") == "PRENOM"

    def test_empty_is_prenom(self):
        assert classify_name_token("") == "PRENOM"

    def test_punctuation_stripped(self):
        assert classify_name_token("DUPONT.") == "NOM"

    def test_accented_caps_is_nom(self):
        assert classify_name_token("LÉGÈRE") == "NOM"


class TestRegexDetect:
    def test_email_detected(self):
        text = "Contactez-moi à jean.dupont@example.com pour plus d'info."
        matches, _ = regex_detect(text)
        emails = [m for m in matches if m.pii_type == PiiType.EMAIL]
        assert len(emails) == 1
        assert emails[0].raw_text == "jean.dupont@example.com"

    def test_french_phone_detected(self):
        text = "Mon numéro : 06 12 34 56 78"
        matches, _ = regex_detect(text)
        phones = [m for m in matches if m.pii_type == PiiType.TELEPHONE]
        assert len(phones) == 1

    def test_phone_with_country_code(self):
        text = "Tel: +33 6 12 34 56 78"
        matches, _ = regex_detect(text)
        phones = [m for m in matches if m.pii_type == PiiType.TELEPHONE]
        assert len(phones) == 1

    def test_ssn_detected(self):
        text = "N° sécu : 1 85 12 75 123 456 78"
        matches, _ = regex_detect(text)
        ssns = [m for m in matches if m.pii_type == PiiType.SECU]
        assert len(ssns) == 1

    def test_credit_card_detected(self):
        text = "CB : 4111 1111 1111 1111"
        matches, _ = regex_detect(text)
        cbs = [m for m in matches if m.pii_type == PiiType.CB]
        assert len(cbs) == 1

    def test_nom_label_detected(self):
        text = "Nom : DUPONT\nPrénom : Jean"
        matches, prenom_spans = regex_detect(text)
        noms = [m for m in matches if m.pii_type == PiiType.NOM]
        assert len(noms) >= 1
        assert "DUPONT" in noms[0].raw_text

    def test_prenom_not_redacted(self):
        text = "Nom : DUPONT\nPrénom : Jean"
        matches, prenom_spans = regex_detect(text)
        # Prénom should be captured as a skip span, NOT as a match
        prenom_matches = [m for m in matches if "Jean" in m.raw_text]
        assert len(prenom_matches) == 0
        # But a prenom_span should be recorded
        assert len(prenom_spans) == 1

    def test_address_label_detected(self):
        text = "Adresse : 12 rue de la Paix, 75001 Paris"
        matches, _ = regex_detect(text)
        addrs = [m for m in matches if m.pii_type == PiiType.ADRESSE]
        assert len(addrs) == 1

    def test_no_false_positive_email(self):
        text = "L'identifiant système est config.local"
        matches, _ = regex_detect(text)
        emails = [m for m in matches if m.pii_type == PiiType.EMAIL]
        assert len(emails) == 0

    def test_multiple_pii_types(self):
        text = (
            "Nom : MARTIN\n"
            "Email : alice.martin@mail.fr\n"
            "Tél : 01 23 45 67 89\n"
        )
        matches, _ = regex_detect(text)
        types = {m.pii_type for m in matches}
        assert PiiType.NOM in types
        assert PiiType.EMAIL in types
        assert PiiType.TELEPHONE in types

    def test_char_spans_correct(self):
        text = "Email : test@example.com fin"
        matches, _ = regex_detect(text)
        emails = [m for m in matches if m.pii_type == PiiType.EMAIL]
        assert emails
        m = emails[0]
        assert text[m.char_start:m.char_end] == "test@example.com"
