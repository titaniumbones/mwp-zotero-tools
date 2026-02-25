"""Tests for PDF/EPUB TOC chapter mapping with page labels."""

import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import fitz as _fitz
import pytest

from zotero_cli.pdf_toc import (
    build_chapter_map,
    build_chapter_map_from_epub,
    build_chapter_map_from_pdf,
    get_chapter_for_page,
    get_chapter_map_for_epub,
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


def _make_epub_bytes(nav_body: str, spine_items: list = None) -> bytes:
    """Build a minimal EPUB ZIP in memory for testing.

    Args:
        nav_body: The <body> content of the XHTML nav document.
        spine_items: List of (id, filename) tuples for OPF manifest/spine.
            If None, uses a default set of 60 items.
    """
    if spine_items is None:
        spine_items = [(f"item{i}", f"text/chapter{i}.xhtml") for i in range(60)]

    manifest_xml = ""
    spine_xml = ""
    for item_id, href in spine_items:
        props = ' properties="nav"' if href == "text/nav.xhtml" else ""
        manifest_xml += f'    <item id="{item_id}" href="{href}" media-type="application/xhtml+xml"{props}/>\n'
        spine_xml += f'    <itemref idref="{item_id}"/>\n'

    # Add nav item to manifest if not already included
    if not any(href == "text/nav.xhtml" for _, href in spine_items):
        manifest_xml += '    <item id="nav" href="text/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>\n'

    container_xml = '<?xml version="1.0"?>\n<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">\n  <rootfiles>\n    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>\n  </rootfiles>\n</container>'

    opf_xml = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test Book</dc:title>
  </metadata>
  <manifest>
{manifest_xml}  </manifest>
  <spine>
{spine_xml}  </spine>
</package>"""

    nav_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Navigation</title></head>
{nav_body}
</html>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("content.opf", opf_xml)
        zf.writestr("text/nav.xhtml", nav_xhtml)
        # Create dummy spine files
        for _, href in spine_items:
            if href != "text/nav.xhtml":
                zf.writestr(href, "<html><body></body></html>")
    return buf.getvalue()


class TestBuildChapterMapFromEpub:
    """Tests for build_chapter_map_from_epub using in-memory EPUBs."""

    def test_basic_toc(self, tmp_path):
        """Extract TOC entries with correct spine indices."""
        spine = [(f"ch{i}", f"text/ch{i}.xhtml") for i in range(60)]
        nav_body = """<body>
<nav epub:type="toc">
  <ol>
    <li><a href="ch0.xhtml">Introduction</a></li>
    <li><a href="ch10.xhtml">Chapter 1</a></li>
    <li><a href="ch55.xhtml">Notes</a></li>
  </ol>
</nav>
</body>"""
        epub_file = tmp_path / "test.epub"
        epub_file.write_bytes(_make_epub_bytes(nav_body, spine))

        result = build_chapter_map_from_epub(str(epub_file))
        assert len(result) == 3
        assert result[0] == ("Introduction", "00000", 1)
        assert result[1] == ("Chapter 1", "00010", 1)
        assert result[2] == ("Notes", "00055", 1)

    def test_hierarchical_toc(self, tmp_path):
        """Nested TOC entries get correct levels."""
        spine = [(f"ch{i}", f"text/ch{i}.xhtml") for i in range(60)]
        nav_body = """<body>
<nav epub:type="toc">
  <ol>
    <li><a href="ch0.xhtml">Part One</a>
      <ol>
        <li><a href="ch1.xhtml">Chapter 1</a></li>
        <li><a href="ch10.xhtml">Chapter 2</a></li>
      </ol>
    </li>
    <li><a href="ch30.xhtml">Part Two</a>
      <ol>
        <li><a href="ch31.xhtml">Chapter 3</a></li>
      </ol>
    </li>
  </ol>
</nav>
</body>"""
        epub_file = tmp_path / "test.epub"
        epub_file.write_bytes(_make_epub_bytes(nav_body, spine))

        result = build_chapter_map_from_epub(str(epub_file), max_level=2)
        assert len(result) == 5
        assert result[0] == ("Part One", "00000", 1)
        assert result[1] == ("Chapter 1", "00001", 2)
        assert result[2] == ("Chapter 2", "00010", 2)
        assert result[3] == ("Part Two", "00030", 1)
        assert result[4] == ("Chapter 3", "00031", 2)

    def test_max_level_filtering(self, tmp_path):
        """Entries deeper than max_level are excluded."""
        spine = [(f"ch{i}", f"text/ch{i}.xhtml") for i in range(10)]
        nav_body = """<body>
<nav epub:type="toc">
  <ol>
    <li><a href="ch0.xhtml">Part One</a>
      <ol>
        <li><a href="ch1.xhtml">Chapter 1</a>
          <ol>
            <li><a href="ch2.xhtml">Section 1.1</a></li>
          </ol>
        </li>
      </ol>
    </li>
  </ol>
</nav>
</body>"""
        epub_file = tmp_path / "test.epub"
        epub_file.write_bytes(_make_epub_bytes(nav_body, spine))

        result = build_chapter_map_from_epub(str(epub_file), max_level=1)
        assert len(result) == 1
        assert result[0][0] == "Part One"

    def test_invalid_epub_returns_empty(self, tmp_path):
        """Non-EPUB file returns empty list."""
        bad_file = tmp_path / "bad.epub"
        bad_file.write_text("not a zip")
        assert build_chapter_map_from_epub(str(bad_file)) == []

    def test_no_nav_returns_empty(self, tmp_path):
        """EPUB without nav document returns empty list."""
        buf = io.BytesIO()
        container_xml = '<?xml version="1.0"?>\n<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">\n  <rootfiles>\n    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>\n  </rootfiles>\n</container>'
        opf_xml = '<?xml version="1.0"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="3.0">\n  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>T</dc:title></metadata>\n  <manifest><item id="ch0" href="ch0.xhtml" media-type="application/xhtml+xml"/></manifest>\n  <spine><itemref idref="ch0"/></spine>\n</package>'
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/container.xml", container_xml)
            zf.writestr("content.opf", opf_xml)
            zf.writestr("ch0.xhtml", "<html><body></body></html>")
        epub_file = tmp_path / "no_nav.epub"
        epub_file.write_bytes(buf.getvalue())
        assert build_chapter_map_from_epub(str(epub_file)) == []

    def test_chapter_lookup_with_spine_indices(self):
        """get_chapters_for_page works with zero-padded spine index strings."""
        chapter_map = [
            ("Introduction", "00000", 1),
            ("Chapter 1", "00010", 1),
            ("Section 1.1", "00015", 2),
            ("Notes", "00055", 1),
        ]
        # Annotation at spine 12 → Chapter 1
        assert get_chapter_for_page(chapter_map, "00012") == "Chapter 1"
        # Annotation at spine 16 → Section 1.1
        result = get_chapters_for_page(chapter_map, "00016")
        assert ("Chapter 1", 1) in result
        assert ("Section 1.1", 2) in result
        # Annotation at spine 55 → Notes
        assert get_chapter_for_page(chapter_map, "00055") == "Notes"

    def test_deduplicates_consecutive(self, tmp_path):
        """Consecutive entries with same title are deduplicated."""
        spine = [(f"ch{i}", f"text/ch{i}.xhtml") for i in range(5)]
        nav_body = """<body>
<nav epub:type="toc">
  <ol>
    <li><a href="ch0.xhtml">Chapter 1</a></li>
    <li><a href="ch1.xhtml">Chapter 1</a></li>
    <li><a href="ch2.xhtml">Chapter 2</a></li>
  </ol>
</nav>
</body>"""
        epub_file = tmp_path / "test.epub"
        epub_file.write_bytes(_make_epub_bytes(nav_body, spine))

        result = build_chapter_map_from_epub(str(epub_file))
        assert len(result) == 2


class TestGetChapterMapForEpub:
    """Test the EPUB convenience function."""

    def test_delegates_to_build_chapter_map_from_epub(self):
        with patch("zotero_cli.pdf_toc.build_chapter_map_from_epub", return_value=[("Notes", "00055", 1)]) as mock:
            result = get_chapter_map_for_epub("/some/path.epub", max_level=3)
            mock.assert_called_once_with("/some/path.epub", 3)
            assert result == [("Notes", "00055", 1)]
