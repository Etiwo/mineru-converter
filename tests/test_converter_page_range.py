"""Tests for converter module page range parsing."""

import pytest
from scripts.converter import _parse_page_range


class TestParsePageRange:
    """Test _parse_page_range utility function."""

    def test_range_3_to_5(self):
        """'3-5' should return (2, 4) — 0-indexed."""
        start, end = _parse_page_range("3-5")
        assert start == 2
        assert end == 4

    def test_single_page(self):
        """'3' (no dash) should return (2, 2) — 0-indexed single page."""
        start, end = _parse_page_range("3")
        assert start == 2
        assert end == 2

    def test_full_document_range(self):
        """'1-100' should return (0, 99)."""
        start, end = _parse_page_range("1-100")
        assert start == 0
        assert end == 99

    def test_empty_string(self):
        """Empty string should return (None, None)."""
        start, end = _parse_page_range("")
        assert start is None
        assert end is None

    def test_none_input(self):
        """None or empty string returns (None, None)."""
        start, end = _parse_page_range(None)
        assert start is None
        assert end is None

    def test_range_with_spaces(self):
        """' 3 - 5 ' should handle whitespace."""
        start, end = _parse_page_range(" 3 - 5 ")
        assert start == 2
        assert end == 4

    def test_same_start_end(self):
        """'5-5' should return (4, 4)."""
        start, end = _parse_page_range("5-5")
        assert start == 4
        assert end == 4

    def test_invalid_format(self):
        """'3x5' should raise ValueError."""
        with pytest.raises(ValueError):
            _parse_page_range("3x5")
