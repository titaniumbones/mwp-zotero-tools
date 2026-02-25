"""
PDF Table of Contents extraction for chapter grouping of annotations.

Uses PyMuPDF (fitz) to extract bookmarks/outline from PDF files,
enabling annotation grouping by chapter. Degrades gracefully if
PyMuPDF is not installed or the PDF has no TOC.

Page numbers use the PDF's page labels (printed page numbers) rather
than physical page indices, so they match annotationPageLabel values.
"""

from bisect import bisect_right
from typing import Dict, List, Optional, Tuple


def extract_toc(pdf_path: str) -> List[Tuple[int, str, int]]:
    """
    Extract Table of Contents from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of (level, title, page_num) tuples from PDF bookmarks.
        Returns empty list if PyMuPDF not installed or PDF has no TOC.
    """
    try:
        import fitz
    except ImportError:
        return []

    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()
        doc.close()
        return toc
    except Exception:
        return []


def build_chapter_map(toc: List[Tuple[int, str, int]], max_level: int = 2) -> List[Tuple[str, int]]:
    """
    Convert a TOC into a sorted list of (chapter_title, start_page) pairs.

    Uses physical page numbers. For page-label-aware mapping, use
    build_chapter_map_from_pdf() instead.

    Args:
        toc: TOC entries from extract_toc().
        max_level: Maximum heading depth to include.

    Returns:
        Sorted list of (title, page_number) pairs.
    """
    if not toc:
        return []

    entries = [(title.strip(), page) for level, title, page in toc if level <= max_level and title.strip()]

    # Deduplicate consecutive entries with same title
    deduped = []
    for title, page in entries:
        if not deduped or deduped[-1][0] != title:
            deduped.append((title, page))

    return deduped


def build_chapter_map_from_pdf(pdf_path: str, max_level: int = 2) -> List[Tuple[str, str, int]]:
    """
    Build a chapter map using page labels instead of physical page numbers.

    Page labels are the printed page numbers embedded in the PDF (e.g., "308"
    for a page that is physically page 395 due to front matter). This ensures
    chapter boundaries match annotationPageLabel values from Zotero.

    Args:
        pdf_path: Path to the PDF file.
        max_level: Maximum heading depth to include.

    Returns:
        Sorted list of (title, page_label, level) tuples. Page labels are strings.
        Returns empty list if PyMuPDF not installed or PDF has no TOC.
    """
    try:
        import fitz
    except ImportError:
        return []

    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()

        if not toc:
            doc.close()
            return []

        entries = []
        for level, title, phys_page in toc:
            if level > max_level or not title.strip():
                continue
            # Convert physical page number to page label
            # fitz pages are 0-indexed, TOC pages are 1-indexed
            page_idx = phys_page - 1
            if 0 <= page_idx < len(doc):
                label = doc[page_idx].get_label()
            else:
                label = str(phys_page)
            entries.append((title.strip(), label, level))

        doc.close()

        # Deduplicate consecutive entries with same title
        deduped = []
        for title, label, level in entries:
            if not deduped or deduped[-1][0] != title:
                deduped.append((title, label, level))

        return deduped
    except Exception:
        return []


def get_chapters_for_page(chapter_map, page_label: str) -> List[Tuple[str, int]]:
    """
    Find all ancestor chapter headings for a given page.

    Returns the nearest preceding entry at each TOC level, giving a
    hierarchical path. For example, a page in subsection "2. The Double
    Character..." (L2) will return both its parent "Chapter 1" (L1) and
    the L2 entry itself.

    Args:
        chapter_map: Sorted list of (title, page_label, level) from
            build_chapter_map_from_pdf(). Also accepts legacy 2-tuples
            (title, page_label) which are treated as level 1.
        page_label: The page label to look up (from annotationPageLabel).

    Returns:
        List of (title, level) tuples sorted by level, or empty list if
        page is before the first chapter.
    """
    if not chapter_map:
        return []

    # Normalize to 3-tuples if legacy 2-tuple format
    normalized = []
    for entry in chapter_map:
        if len(entry) == 2:
            normalized.append((entry[0], entry[1], 1))
        else:
            normalized.append((entry[0], entry[1], entry[2]))

    # Try numeric comparison
    try:
        target = int(page_label)
        return _get_chapters_numeric(normalized, target)
    except (ValueError, TypeError):
        return _get_chapters_nonnumeric(normalized, page_label)


def _get_chapters_numeric(chapter_map: List[Tuple[str, str, int]], target: int) -> List[Tuple[str, int]]:
    """Find hierarchical chapters for a numeric page label."""
    # Build numeric entries preserving level
    numeric_entries = []
    for title, lbl, level in chapter_map:
        try:
            numeric_entries.append((title, int(lbl), level))
        except (ValueError, TypeError):
            continue

    if not numeric_entries:
        return []

    # Find the nearest preceding entry at each level
    nearest_by_level: Dict[int, str] = {}
    for title, page_num, level in numeric_entries:
        if page_num <= target:
            nearest_by_level[level] = title
            # When a new entry at this level appears, clear deeper levels
            deeper = [k for k in nearest_by_level if k > level]
            for k in deeper:
                del nearest_by_level[k]

    if not nearest_by_level:
        return []

    return sorted([(title, level) for level, title in nearest_by_level.items()], key=lambda x: x[1])


def _get_chapters_nonnumeric(chapter_map: List[Tuple[str, str, int]], page_label: str) -> List[Tuple[str, int]]:
    """Find chapters for a non-numeric page label (e.g., roman numerals)."""
    for title, lbl, level in chapter_map:
        if lbl == page_label:
            return [(title, level)]
    return []


def get_chapter_for_page(chapter_map, page_label: str) -> Optional[str]:
    """
    Find which chapter a given page falls in.

    Legacy wrapper around get_chapters_for_page() — returns the deepest
    (most specific) chapter title only.

    Args:
        chapter_map: Sorted list of (title, page_label[, level]) tuples.
        page_label: The page label to look up.

    Returns:
        Chapter title, or None if page is before the first chapter.
    """
    chapters = get_chapters_for_page(chapter_map, page_label)
    if not chapters:
        return None
    # Return the deepest (highest level number) entry
    return max(chapters, key=lambda x: x[1])[0]


def get_chapter_map_for_pdf(pdf_path: str, max_level: int = 2) -> List[Tuple[str, str, int]]:
    """
    Convenience: extract TOC and build chapter map with page labels.

    Args:
        pdf_path: Path to the PDF file.
        max_level: Maximum heading depth to include.

    Returns:
        Sorted list of (title, page_label, level) tuples, or empty list.
    """
    return build_chapter_map_from_pdf(pdf_path, max_level)
