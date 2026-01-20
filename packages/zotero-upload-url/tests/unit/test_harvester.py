"""Tests for reference harvesting functions."""

import pytest

from zotero_upload_url.harvester import (
    BatchImportResult,
    BatchImporter,
    ExtractedReference,
    ReferenceExtractor,
    read_input,
)


class TestExtractedReference:
    """Tests for the ExtractedReference dataclass."""

    def test_url_get_save_url(self):
        """Test get_save_url returns URL directly."""
        ref = ExtractedReference(
            original_text="https://example.com",
            ref_type="url",
            url="https://example.com"
        )
        assert ref.get_save_url() == "https://example.com"

    def test_doi_get_save_url(self):
        """Test get_save_url converts DOI to URL."""
        ref = ExtractedReference(
            original_text="doi:10.1038/nature12373",
            ref_type="doi",
            doi="10.1038/nature12373"
        )
        assert ref.get_save_url() == "https://doi.org/10.1038/nature12373"

    def test_arxiv_get_save_url(self):
        """Test get_save_url converts arXiv ID to URL."""
        ref = ExtractedReference(
            original_text="arXiv:2301.00001",
            ref_type="arxiv",
            arxiv_id="2301.00001"
        )
        assert ref.get_save_url() == "https://arxiv.org/abs/2301.00001"

    def test_display_str_with_title(self):
        """Test display_str includes title when available."""
        ref = ExtractedReference(
            original_text="[Paper Title](https://example.com)",
            ref_type="markdown_link",
            url="https://example.com",
            title="Paper Title"
        )
        display = ref.display_str()
        assert "Paper Title" in display
        assert "https://example.com" in display

    def test_display_str_without_title(self):
        """Test display_str shows URL when no title."""
        ref = ExtractedReference(
            original_text="https://example.com",
            ref_type="url",
            url="https://example.com"
        )
        display = ref.display_str()
        assert "https://example.com" in display
        assert "[url]" in display


class TestReferenceExtractor:
    """Tests for the ReferenceExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a ReferenceExtractor instance."""
        return ReferenceExtractor()

    class TestExtractUrls:
        """Tests for URL extraction."""

        def test_simple_url(self, extractor):
            """Test extracting a simple URL."""
            text = "Check out https://example.com for more info."
            refs = extractor.extract_urls(text)
            assert len(refs) == 1
            assert refs[0].url == "https://example.com"
            assert refs[0].ref_type == "url"

        def test_https_and_http(self, extractor):
            """Test both HTTPS and HTTP URLs are extracted."""
            text = "See https://secure.com and http://insecure.com"
            refs = extractor.extract_urls(text)
            assert len(refs) == 2
            urls = [r.url for r in refs]
            assert "https://secure.com" in urls
            assert "http://insecure.com" in urls

        def test_url_with_path(self, extractor):
            """Test URL with path is fully captured."""
            text = "Article at https://example.com/articles/2024/my-article"
            refs = extractor.extract_urls(text)
            assert len(refs) == 1
            assert refs[0].url == "https://example.com/articles/2024/my-article"

        def test_url_with_query_params(self, extractor):
            """Test URL with query parameters."""
            text = "Search: https://example.com/search?q=test&page=1"
            refs = extractor.extract_urls(text)
            assert len(refs) == 1
            assert "q=test" in refs[0].url

        def test_trailing_punctuation_stripped(self, extractor):
            """Test trailing punctuation is stripped from URLs."""
            text = "Visit https://example.com."
            refs = extractor.extract_urls(text)
            assert refs[0].url == "https://example.com"

        def test_multiple_urls(self, extractor):
            """Test multiple URLs in same text."""
            text = """
            First: https://first.com
            Second: https://second.com
            Third: https://third.com
            """
            refs = extractor.extract_urls(text)
            assert len(refs) == 3

        def test_no_urls(self, extractor):
            """Test text without URLs returns empty list."""
            text = "This text has no URLs in it."
            refs = extractor.extract_urls(text)
            assert refs == []

    class TestExtractMarkdownLinks:
        """Tests for markdown link extraction."""

        def test_simple_markdown_link(self, extractor):
            """Test extracting a markdown link."""
            text = "Check [this article](https://example.com/article)"
            refs = extractor.extract_markdown_links(text)
            assert len(refs) == 1
            assert refs[0].url == "https://example.com/article"
            assert refs[0].title == "this article"
            assert refs[0].ref_type == "markdown_link"

        def test_multiple_markdown_links(self, extractor):
            """Test multiple markdown links."""
            text = """
            [First](https://first.com) and [Second](https://second.com)
            """
            refs = extractor.extract_markdown_links(text)
            assert len(refs) == 2

        def test_markdown_with_complex_title(self, extractor):
            """Test markdown link with complex title."""
            text = "[A Paper: With Subtitle (2024)](https://example.com)"
            refs = extractor.extract_markdown_links(text)
            assert len(refs) == 1
            assert refs[0].title == "A Paper: With Subtitle (2024)"

        def test_no_markdown_links(self, extractor):
            """Test text without markdown links."""
            text = "Just a plain https://example.com URL"
            refs = extractor.extract_markdown_links(text)
            assert refs == []

    class TestExtractDois:
        """Tests for DOI extraction."""

        def test_doi_prefix(self, extractor):
            """Test extracting DOI with doi: prefix."""
            text = "Reference: doi:10.1038/nature12373"
            refs = extractor.extract_dois(text)
            assert len(refs) == 1
            assert refs[0].doi == "10.1038/nature12373"
            assert refs[0].ref_type == "doi"

        def test_doi_url(self, extractor):
            """Test extracting DOI from doi.org URL."""
            text = "Link: https://doi.org/10.1038/nature12373"
            refs = extractor.extract_dois(text)
            assert len(refs) == 1
            assert refs[0].doi == "10.1038/nature12373"

        def test_dx_doi_url(self, extractor):
            """Test extracting DOI from dx.doi.org URL."""
            text = "Link: https://dx.doi.org/10.1038/nature12373"
            refs = extractor.extract_dois(text)
            assert len(refs) == 1
            assert refs[0].doi == "10.1038/nature12373"

        def test_doi_with_slashes(self, extractor):
            """Test DOI with multiple slashes in suffix."""
            text = "doi:10.1000/xyz/abc/123"
            refs = extractor.extract_dois(text)
            assert len(refs) == 1
            assert refs[0].doi == "10.1000/xyz/abc/123"

        def test_trailing_punctuation_stripped(self, extractor):
            """Test trailing punctuation stripped from DOI."""
            text = "See doi:10.1038/nature12373."
            refs = extractor.extract_dois(text)
            assert refs[0].doi == "10.1038/nature12373"

        def test_multiple_dois(self, extractor):
            """Test multiple DOIs in text."""
            text = "First doi:10.1038/nature12373 and second doi:10.1000/test123"
            refs = extractor.extract_dois(text)
            assert len(refs) == 2

        def test_no_dois(self, extractor):
            """Test text without DOIs."""
            text = "No DOIs here, just https://example.com"
            refs = extractor.extract_dois(text)
            assert refs == []

    class TestExtractArxiv:
        """Tests for arXiv extraction."""

        def test_arxiv_prefix(self, extractor):
            """Test extracting arXiv with arXiv: prefix."""
            text = "Paper: arXiv:2301.00001"
            refs = extractor.extract_arxiv(text)
            assert len(refs) == 1
            assert refs[0].arxiv_id == "2301.00001"
            assert refs[0].ref_type == "arxiv"

        def test_arxiv_url(self, extractor):
            """Test extracting arXiv from URL."""
            text = "Link: https://arxiv.org/abs/2301.00001"
            refs = extractor.extract_arxiv(text)
            assert len(refs) == 1
            assert refs[0].arxiv_id == "2301.00001"

        def test_arxiv_with_version(self, extractor):
            """Test arXiv ID with version number."""
            text = "arXiv:2301.00001v2"
            refs = extractor.extract_arxiv(text)
            assert len(refs) == 1
            assert refs[0].arxiv_id == "2301.00001v2"

        def test_arxiv_case_insensitive(self, extractor):
            """Test arXiv prefix is case insensitive."""
            text = "ARXIV:2301.00001"
            refs = extractor.extract_arxiv(text)
            assert len(refs) == 1

        def test_no_arxiv(self, extractor):
            """Test text without arXiv refs."""
            text = "No arXiv papers here"
            refs = extractor.extract_arxiv(text)
            assert refs == []

    class TestExtractAll:
        """Tests for extract_all method."""

        def test_extracts_all_types(self, extractor):
            """Test all reference types are extracted."""
            text = """
            Here are some references:
            - [A Paper](https://example.com/paper)
            - doi:10.1038/nature12373
            - arXiv:2301.00001
            - https://plain-url.com
            """
            refs = extractor.extract_all(text)
            types = {r.ref_type for r in refs}
            assert "markdown_link" in types
            assert "doi" in types
            assert "arxiv" in types
            assert "url" in types

        def test_deduplication(self, extractor):
            """Test URLs are deduplicated."""
            text = """
            [Link](https://example.com)
            Same URL: https://example.com
            """
            refs = extractor.extract_all(text)
            urls = [r.get_save_url() for r in refs]
            assert len(urls) == 1
            # Markdown link should win (has title)
            assert refs[0].ref_type == "markdown_link"

        def test_markdown_link_takes_precedence(self, extractor):
            """Test markdown links take precedence over plain URLs."""
            text = """
            First: https://example.com
            Then: [With Title](https://example.com)
            """
            refs = extractor.extract_all(text)
            assert len(refs) == 1
            assert refs[0].title == "With Title"

        def test_empty_text(self, extractor):
            """Test empty text returns empty list."""
            refs = extractor.extract_all("")
            assert refs == []

        def test_real_world_example(self, extractor):
            """Test with realistic LLM output."""
            text = """
            Here are some relevant papers on transformer architectures:

            1. [Attention Is All You Need](https://arxiv.org/abs/1706.03762) - The original transformer paper
            2. BERT paper: https://arxiv.org/abs/1810.04805
            3. GPT-3: doi:10.48550/arXiv.2005.14165

            For more context, see https://example.com/transformers-overview
            """
            refs = extractor.extract_all(text)
            # Should find unique references
            assert len(refs) >= 3


class TestBatchImportResult:
    """Tests for BatchImportResult dataclass."""

    def test_default_values(self):
        """Test default values are initialized."""
        result = BatchImportResult()
        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.errors == []

    def test_errors_list(self):
        """Test errors list can be populated."""
        result = BatchImportResult()
        ref = ExtractedReference(
            original_text="test",
            ref_type="url",
            url="https://example.com"
        )
        result.errors.append((ref, "Test error"))
        assert len(result.errors) == 1


class TestBatchImporter:
    """Tests for BatchImporter class."""

    def test_initialization(self):
        """Test importer initializes with default values."""
        importer = BatchImporter()
        assert importer.port == 23119
        assert importer.delay == 8.0
        assert importer.shortcut == "option+cmd+s"

    def test_custom_initialization(self):
        """Test importer with custom values."""
        importer = BatchImporter(port=9999, delay=5.0, shortcut="cmd+shift+s")
        assert importer.port == 9999
        assert importer.delay == 5.0
        assert importer.shortcut == "cmd+shift+s"

    def test_dry_run_returns_result(self):
        """Test dry run returns result without importing."""
        importer = BatchImporter()
        refs = [
            ExtractedReference(
                original_text="test",
                ref_type="url",
                url="https://example.com"
            )
        ]
        result = importer.import_references(refs, dry_run=True)
        assert result.total == 1
        assert result.skipped == 1
        assert result.succeeded == 0

    def test_empty_refs_list(self):
        """Test importing empty list."""
        importer = BatchImporter()
        result = importer.import_references([], dry_run=True)
        assert result.total == 0


class TestReadInput:
    """Tests for read_input function."""

    def test_read_from_file(self, tmp_path):
        """Test reading from a file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Test content")
        content = read_input(str(test_file))
        assert content == "Test content"

    def test_file_not_found(self):
        """Test FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            read_input("/nonexistent/file.md")


# Fixtures for nested test classes
@pytest.fixture
def extractor():
    """Create a ReferenceExtractor instance."""
    return ReferenceExtractor()
