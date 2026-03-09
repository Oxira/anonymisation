"""
Unit tests for the coordinate mapper module.
"""
import pytest

from anonymiser.coordinate_mapper import get_scale, words_to_pdf_rect
from anonymiser.models import OcrWord


def make_word(text="test", img_x=100, img_y=200, img_w=50, img_h=20, page_num=0):
    return OcrWord(
        text=text,
        page_num=page_num,
        img_x=img_x,
        img_y=img_y,
        img_w=img_w,
        img_h=img_h,
        confidence=90.0,
    )


class TestWordsToRect:
    def test_single_word(self):
        word = make_word(img_x=100, img_y=200, img_w=50, img_h=20)
        rect = words_to_pdf_rect([word], scale_x=0.24, scale_y=0.24, padding=0)
        # 100 * 0.24 = 24.0, 200 * 0.24 = 48.0, 150 * 0.24 = 36.0, 220 * 0.24 = 52.8
        assert abs(rect.x0 - 24.0) < 0.01
        assert abs(rect.y0 - 48.0) < 0.01
        assert abs(rect.x1 - 36.0) < 0.01
        assert abs(rect.y1 - 52.8) < 0.01

    def test_multiple_words_union(self):
        w1 = make_word(img_x=10, img_y=20, img_w=30, img_h=10)  # right edge 40
        w2 = make_word(img_x=50, img_y=20, img_w=30, img_h=10)  # right edge 80
        rect = words_to_pdf_rect([w1, w2], scale_x=1.0, scale_y=1.0, padding=0)
        assert rect.x0 == 10.0
        assert rect.x1 == 80.0

    def test_padding_applied(self):
        word = make_word(img_x=100, img_y=100, img_w=50, img_h=20)
        rect_no_pad = words_to_pdf_rect([word], scale_x=1.0, scale_y=1.0, padding=0)
        rect_pad = words_to_pdf_rect([word], scale_x=1.0, scale_y=1.0, padding=2)
        assert rect_pad.x0 == rect_no_pad.x0 - 2
        assert rect_pad.y0 == rect_no_pad.y0 - 2
        assert rect_pad.x1 == rect_no_pad.x1 + 2
        assert rect_pad.y1 == rect_no_pad.y1 + 2


class TestOcrExtraction:
    """Test extract_full_text from ocr module."""

    def test_basic_text(self):
        from anonymiser.ocr import extract_full_text

        words = [
            OcrWord("Bonjour", 0, 0, 0, 50, 15, 95.0, line_num=1, block_num=1),
            OcrWord("monde", 0, 60, 0, 40, 15, 95.0, line_num=1, block_num=1),
        ]
        text, char_map = extract_full_text(words)
        assert "Bonjour" in text
        assert "monde" in text

    def test_char_to_word_mapping(self):
        from anonymiser.ocr import extract_full_text

        words = [
            OcrWord("Hello", 0, 0, 0, 30, 15, 95.0, line_num=1, block_num=1),
            OcrWord("World", 0, 40, 0, 30, 15, 95.0, line_num=1, block_num=1),
        ]
        text, char_map = extract_full_text(words)
        # First character of "Hello" → word index 0
        assert char_map[0] == 0
        # First character of "World" → word index 1
        world_start = text.index("World")
        assert char_map[world_start] == 1

    def test_empty_words(self):
        from anonymiser.ocr import extract_full_text

        text, char_map = extract_full_text([])
        assert text == ""
        assert char_map == {}
