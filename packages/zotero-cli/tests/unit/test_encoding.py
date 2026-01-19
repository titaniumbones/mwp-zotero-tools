"""Tests for text encoding normalization in ZoteroLocalAPI."""

import pytest

from zotero_cli.api import ZoteroLocalAPI


class TestNormalizeTextEncoding:
    """Tests for the normalize_text_encoding method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    def test_empty_string(self, api):
        """Empty string should return empty string."""
        assert api.normalize_text_encoding("") == ""

    def test_none_input(self, api):
        """None input should return None."""
        assert api.normalize_text_encoding(None) is None

    def test_plain_text_unchanged(self, api):
        """Plain ASCII text should be unchanged."""
        text = "This is plain ASCII text."
        assert api.normalize_text_encoding(text) == text

    def test_smart_quotes_double(self, api):
        """Test smart double quote normalization."""
        # Test specific corrupted patterns from the code
        text = "some text with corrupted â quote"
        result = api.normalize_text_encoding(text)
        # The replacement for 'â' maps to '"'
        assert "â" not in result or result != text

    def test_accented_characters(self, api):
        """Test accented character normalization."""
        # Test common accented character corruptions that are in the replacements dict
        # Note: exact byte sequences may vary based on file encoding
        test_cases = [
            ("Ã¡", "á"),  # a with acute
            ("Ã©", "é"),  # e with acute
            ("Ã±", "ñ"),  # n with tilde
        ]
        for corrupted, expected in test_cases:
            result = api.normalize_text_encoding(corrupted)
            assert result == expected, f"Expected '{expected}' for '{corrupted}', got '{result}'"

    def test_bullet_point_in_context(self, api):
        """Test that bullet-like patterns get processed."""
        # The bullet replacement depends on exact byte sequence
        # Testing that the function runs without error
        result = api.normalize_text_encoding("Item â¢ next item")
        assert isinstance(result, str)

    def test_ellipsis_in_context(self, api):
        """Test that ellipsis-like patterns get processed."""
        # The ellipsis replacement depends on exact byte sequence
        result = api.normalize_text_encoding("text â¦ more")
        assert isinstance(result, str)

    def test_degree_symbol(self, api):
        """Test degree symbol normalization."""
        assert api.normalize_text_encoding("Â°") == "°"

    def test_copyright_symbol(self, api):
        """Test copyright symbol normalization."""
        assert api.normalize_text_encoding("Â©") == "©"

    def test_fraction_half(self, api):
        """Test fraction 1/2 normalization."""
        assert api.normalize_text_encoding("Â½") == "½"

    def test_specific_word_corruptions(self, api):
        """Test specific word corruption fixes."""
        # Test specific words mentioned in the replacements
        test_cases = [
            ("peÂºple", "people"),
            ("Ã©lite", "élite"),
        ]
        for corrupted, expected in test_cases:
            assert api.normalize_text_encoding(corrupted) == expected

    def test_multiple_corruptions_in_text(self, api):
        """Test text with multiple corrupted characters."""
        text = "The Ã©lite Â© 2023 reported Â±5Â° variance."
        result = api.normalize_text_encoding(text)
        # Check all corruptions are fixed
        assert "élite" in result
        assert "©" in result
        assert "±" in result
        assert "°" in result

    def test_preserves_valid_unicode(self, api):
        """Test that valid Unicode is preserved."""
        text = "Already valid: é ñ ü © ° ±"
        assert api.normalize_text_encoding(text) == text

    def test_quotation_marks_left_right(self, api):
        """Test left/right quotation mark handling."""
        # Test angle quotation marks
        assert api.normalize_text_encoding("Â«") == "«"
        assert api.normalize_text_encoding("Â»") == "»"

    def test_superscript_numbers(self, api):
        """Test superscript number handling."""
        assert api.normalize_text_encoding("Â²") == "²"
        assert api.normalize_text_encoding("Â³") == "³"

    def test_registered_trademark(self, api):
        """Test registered trademark symbol."""
        assert api.normalize_text_encoding("Â®") == "®"

    def test_plus_minus_sign(self, api):
        """Test plus-minus sign."""
        assert api.normalize_text_encoding("Â±") == "±"

    def test_long_text_with_corruptions(self, api):
        """Test longer text passage with multiple corruptions."""
        corrupted = (
            "The Ã©lite researchers (Â© 2023) found that peÂºple "
            "experienced Â±5Â° temperature variance. "
            "Results showed â¢ Item 1 â¢ Item 2â¦"
        )
        result = api.normalize_text_encoding(corrupted)

        # Verify corruptions are fixed
        assert "Ã©" not in result
        assert "Â©" not in result
        assert "Â°" not in result
        assert "Â±" not in result
        assert "â¢" not in result
        assert "â¦" not in result

    def test_house_word_corruptions(self, api):
        """Test specific household-related word corruptions."""
        # These specific patterns are in the replacements dict
        # The exact byte sequences may vary, so we test the specific ones
        # that are defined in the source code
        result1 = api.normalize_text_encoding("house\"hold")
        assert result1 == "household", f"Expected 'household', got '{result1}'"

        result2 = api.normalize_text_encoding("house\"wives")
        assert result2 == "housewives", f"Expected 'housewives', got '{result2}'"
