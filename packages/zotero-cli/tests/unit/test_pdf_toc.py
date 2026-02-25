"""Tests for PDF TOC chapter mapping with page labels."""

from unittest.mock import MagicMock, patch

import fitz as _fitz
import pytest

from zotero_cli.pdf_toc import (
    build_chapter_map,
    build_chapter_map_from_pdf,
    get_chapter_for_page,
    get_chapter_map_for_pdf,
    get_chapters_for_page,
)


class TestBuildChapterMap:
    """Tests for the legacy build_chapter_map (physical pages)."""

    def test_empty_toc(self):
        assert build_chapter_map([]) == []

    def test_filters_by_level(self):
        toc = [
            (1, "Part One", 1),
            (2, "Chapter 1", 5),
            (3, "Section 1.1", 6),
        ]
        result = build_chapter_map(toc, max_level=2)
        assert len(result) == 2
        assert result[0] == ("Part One", 1)
        assert result[1] == ("Chapter 1", 5)

    def test_deduplicates_consecutive(self):
        toc = [
            (1, "Chapter 1", 1),
            (1, "Chapter 1", 2),
            (1, "Chapter 2", 10),
        ]
        result = build_chapter_map(toc)
        assert len(result) == 2


class TestGetChapterForPage:
    """Tests for get_chapter_for_page with string page labels."""

    def test_empty_map(self):
        assert get_chapter_for_page([], "5") is None

    def test_numeric_labels(self):
        chapter_map = [
            ("Intro", "1", 1),
            ("Chapter 1", "10", 1),
            ("Chapter 2", "50", 1),
            ("Chapter 3", "100", 1),
        ]
        assert get_chapter_for_page(chapter_map, "1") == "Intro"
        assert get_chapter_for_page(chapter_map, "5") == "Intro"
        assert get_chapter_for_page(chapter_map, "10") == "Chapter 1"
        assert get_chapter_for_page(chapter_map, "25") == "Chapter 1"
        assert get_chapter_for_page(chapter_map, "50") == "Chapter 2"
        assert get_chapter_for_page(chapter_map, "99") == "Chapter 2"
        assert get_chapter_for_page(chapter_map, "100") == "Chapter 3"
        assert get_chapter_for_page(chapter_map, "200") == "Chapter 3"

    def test_page_before_first_chapter(self):
        chapter_map = [("Chapter 1", "10", 1)]
        assert get_chapter_for_page(chapter_map, "5") is None

    def test_roman_numeral_label(self):
        chapter_map = [
            ("Preface", "iii", 1),
            ("Chapter 1", "1", 1),
        ]
        # Roman numeral page — matches exact label
        assert get_chapter_for_page(chapter_map, "iii") == "Preface"
        # Non-matching roman numeral
        assert get_chapter_for_page(chapter_map, "vii") is None

    def test_numeric_with_offset(self):
        """Simulate a book with 87-page front matter offset."""
        chapter_map = [
            ("Foreword", "vii", 1),
            ("Chapter 1", "1", 1),
            ("Chapter 2", "50", 1),
            ("Chapter 12", "308", 1),
        ]
        # Annotation on printed page 334 should be in Chapter 12
        assert get_chapter_for_page(chapter_map, "334") == "Chapter 12"
        # Annotation on printed page 25 should be in Chapter 1
        assert get_chapter_for_page(chapter_map, "25") == "Chapter 1"

    def test_with_subsections_returns_deepest(self):
        """Legacy wrapper returns the deepest (most specific) heading."""
        chapter_map = [
            ("Chapter 1", "13", 1),
            ("Section 1.1", "19", 2),
            ("Chapter 2", "60", 1),
        ]
        # Page 20 is in Section 1.1 under Chapter 1 — returns Section 1.1
        assert get_chapter_for_page(chapter_map, "20") == "Section 1.1"
        # Page 60 is in Chapter 2 only
        assert get_chapter_for_page(chapter_map, "60") == "Chapter 2"

    def test_legacy_2tuple_format(self):
        """Legacy 2-tuple chapter map still works."""
        chapter_map = [
            ("Chapter 1", "10"),
            ("Chapter 2", "50"),
        ]
        assert get_chapter_for_page(chapter_map, "25") == "Chapter 1"
        assert get_chapter_for_page(chapter_map, "55") == "Chapter 2"


class TestGetChaptersForPage:
    """Tests for get_chapters_for_page returning hierarchical results."""

    def test_empty_map(self):
        assert get_chapters_for_page([], "5") == []

    def test_single_level(self):
        chapter_map = [
            ("Chapter 1", "10", 1),
            ("Chapter 2", "50", 1),
        ]
        result = get_chapters_for_page(chapter_map, "25")
        assert result == [("Chapter 1", 1)]

    def test_hierarchical_returns_both_levels(self):
        """Page in a subsection returns both parent chapter and subsection."""
        chapter_map = [
            ("Chapter 1. The Commodity", "13", 1),
            ("2. The Double Character of the Labor", "19", 2),
            ("Chapter 2. The Exchange Process", "60", 1),
        ]
        # Page 20: under Chapter 1 (L1) and subsection (L2)
        result = get_chapters_for_page(chapter_map, "20")
        assert len(result) == 2
        assert ("Chapter 1. The Commodity", 1) in result
        assert ("2. The Double Character of the Labor", 2) in result

    def test_chapter_without_subsection(self):
        """Page in a chapter with no active subsection returns only L1."""
        chapter_map = [
            ("Chapter 1. The Commodity", "13", 1),
            ("Section 1.1", "19", 2),
            ("Chapter 2. The Exchange Process", "60", 1),
        ]
        # Page 65: in Chapter 2, no subsection yet
        result = get_chapters_for_page(chapter_map, "65")
        assert result == [("Chapter 2. The Exchange Process", 1)]

    def test_page_before_first_chapter(self):
        chapter_map = [("Chapter 1", "10", 1)]
        assert get_chapters_for_page(chapter_map, "5") == []

    def test_new_l1_resets_l2(self):
        """When a new L1 chapter starts, previous L2 is cleared."""
        chapter_map = [
            ("Chapter 1", "10", 1),
            ("Section 1.1", "20", 2),
            ("Chapter 2", "50", 1),
        ]
        # Page 55: new chapter, no subsection
        result = get_chapters_for_page(chapter_map, "55")
        assert result == [("Chapter 2", 1)]

    def test_legacy_2tuple_format(self):
        """Legacy 2-tuple chapter map treated as all level 1."""
        chapter_map = [
            ("Chapter 1", "10"),
            ("Chapter 2", "50"),
        ]
        result = get_chapters_for_page(chapter_map, "25")
        assert result == [("Chapter 1", 1)]

    def test_roman_numeral(self):
        chapter_map = [
            ("Preface", "iii", 1),
            ("Chapter 1", "1", 1),
        ]
        result = get_chapters_for_page(chapter_map, "iii")
        assert result == [("Preface", 1)]


class TestBuildChapterMapFromPdf:
    """Tests for build_chapter_map_from_pdf using mocked fitz."""

    def test_no_fitz_returns_empty(self):
        with patch.dict("sys.modules", {"fitz": None}):
            # Force reimport failure
            import importlib
            from zotero_cli import pdf_toc
            # Simulate ImportError by patching the import inside the function
            with patch("builtins.__import__", side_effect=ImportError):
                result = build_chapter_map_from_pdf("/fake/path.pdf")
                assert result == []

    def test_with_mock_fitz(self):
        """Test that physical pages get converted to page labels with levels."""
        page_labels = {
            0: "i",      # phys page 1
            87: "1",     # phys page 88
            99: "13",    # phys page 100
            394: "308",  # phys page 395
        }

        def make_page(label):
            page = MagicMock()
            page.get_label.return_value = label
            return page

        def getitem(idx):
            if idx in page_labels:
                return make_page(page_labels[idx])
            return make_page(str(idx + 1))

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=500)
        mock_doc.__getitem__ = MagicMock(side_effect=getitem)
        mock_doc.get_toc.return_value = [
            (1, "Foreword", 1),
            (1, "Chapter 1", 88),
            (2, "Section 1.1", 100),
            (1, "Chapter 12", 395),
        ]

        with patch.object(_fitz, "open", return_value=mock_doc):
            result = build_chapter_map_from_pdf("/fake/capital.pdf", max_level=2)

        assert len(result) == 4
        assert result[0] == ("Foreword", "i", 1)
        assert result[1] == ("Chapter 1", "1", 1)
        assert result[2] == ("Section 1.1", "13", 2)
        assert result[3] == ("Chapter 12", "308", 1)

    def test_chapter_lookup_with_label_map(self):
        """End-to-end: build map then look up annotations."""
        chapter_map = [
            ("Foreword", "i", 1),
            ("Chapter 1", "1", 1),
            ("Section 1.1", "13", 2),
            ("Chapter 12", "308", 1),
        ]
        # Annotation on printed page 334 → Chapter 12
        assert get_chapter_for_page(chapter_map, "334") == "Chapter 12"
        # Annotation on printed page 5 → Chapter 1
        assert get_chapter_for_page(chapter_map, "5") == "Chapter 1"
        # Annotation on printed page 15 → Section 1.1
        assert get_chapter_for_page(chapter_map, "15") == "Section 1.1"
        # Roman numeral page
        assert get_chapter_for_page(chapter_map, "i") == "Foreword"

    def test_hierarchical_lookup_with_label_map(self):
        """Hierarchical lookup returns ancestor headings."""
        chapter_map = [
            ("Foreword", "i", 1),
            ("Chapter 1", "1", 1),
            ("Section 1.1", "13", 2),
            ("Chapter 12", "308", 1),
        ]
        # Page 15: both Chapter 1 and Section 1.1
        result = get_chapters_for_page(chapter_map, "15")
        assert len(result) == 2
        assert ("Chapter 1", 1) in result
        assert ("Section 1.1", 2) in result

        # Page 334: only Chapter 12 (no subsection)
        result = get_chapters_for_page(chapter_map, "334")
        assert result == [("Chapter 12", 1)]


class TestGetChapterMapForPdf:
    """Test the convenience function."""

    def test_delegates_to_build_chapter_map_from_pdf(self):
        with patch("zotero_cli.pdf_toc.build_chapter_map_from_pdf", return_value=[("Ch1", "1", 1)]) as mock:
            result = get_chapter_map_for_pdf("/some/path.pdf", max_level=3)
            mock.assert_called_once_with("/some/path.pdf", 3)
            assert result == [("Ch1", "1", 1)]
