"""Tests for text encoding normalization in ZoteroLocalAPI."""

import pytest

from zotero_cli.api import ZoteroLocalAPI


@pytest.fixture
def api():
    """Create API instance for testing."""
    return ZoteroLocalAPI()


class TestNormalizeTextEncoding:
    """Tests for the normalize_text_encoding method."""

    def test_empty_string(self, api):
        assert api.normalize_text_encoding("") == ""

    def test_none_input(self, api):
        assert api.normalize_text_encoding(None) is None

    def test_plain_text_unchanged(self, api):
        text = "This is plain ASCII text."
        assert api.normalize_text_encoding(text) == text

    def test_preserves_valid_unicode(self, api):
        text = "Already valid: \u00e9 \u00f1 \u00fc \u00a9 \u00b0 \u00b1"
        assert api.normalize_text_encoding(text) == text

    def test_standard_double_encoding_fix(self, api):
        """Test that the encode('latin-1').decode('utf-8') path works."""
        # Create a double-encoded string: take UTF-8 bytes, interpret as latin-1
        original = "\u201cleft quote\u201d"  # "left quote"
        double_encoded = original.encode("utf-8").decode("latin-1")
        result = api.normalize_text_encoding(double_encoded)
        assert result == original

    def test_degree_symbol_via_dict(self, api):
        """Test dictionary fallback for partial corruption."""
        assert api.normalize_text_encoding("\u00c2\u00b0") == "\u00b0"

    def test_copyright_symbol_via_dict(self, api):
        assert api.normalize_text_encoding("\u00c2\u00a9") == "\u00a9"

    def test_fraction_half_via_dict(self, api):
        assert api.normalize_text_encoding("\u00c2\u00bd") == "\u00bd"

    def test_superscript_numbers(self, api):
        assert api.normalize_text_encoding("\u00c2\u00b2") == "\u00b2"
        assert api.normalize_text_encoding("\u00c2\u00b3") == "\u00b3"

    def test_registered_trademark(self, api):
        assert api.normalize_text_encoding("\u00c2\u00ae") == "\u00ae"

    def test_plus_minus_sign(self, api):
        assert api.normalize_text_encoding("\u00c2\u00b1") == "\u00b1"

    def test_guillemets(self, api):
        assert api.normalize_text_encoding("\u00c2\u00ab") == "\u00ab"
        assert api.normalize_text_encoding("\u00c2\u00bb") == "\u00bb"

    def test_word_specific_corruptions(self, api):
        test_cases = [
            ('house"hold', "household"),
            ('house"wives', "housewives"),
            ('ex"pected', "expected"),
        ]
        for corrupted, expected in test_cases:
            assert api.normalize_text_encoding(corrupted) == expected

    def test_multiple_corruptions_in_text(self, api):
        """Test that multiple issues in one string all get fixed."""
        text = "The \u00c3\u00a9lite \u00c2\u00a9 2023 reported \u00c2\u00b15\u00c2\u00b0 variance."
        result = api.normalize_text_encoding(text)
        assert "\u00e9lite" in result
        assert "\u00a9" in result
        assert "\u00b1" in result
        assert "\u00b0" in result
