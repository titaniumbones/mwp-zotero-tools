"""
PDF Table of Contents extraction for chapter grouping of annotations.

Uses PyMuPDF (fitz) to extract bookmarks/outline from PDF files,
enabling annotation grouping by chapter. Degrades gracefully if
PyMuPDF is not installed or the PDF has no TOC.

Page numbers use the PDF's page labels (printed page numbers) rather
than physical page indices, so they match annotationPageLabel values.
"""

import os
import re
import xml.etree.ElementTree as ET
import zipfile
from bisect import bisect_right
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse


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


def _parse_epub_spine(zf: zipfile.ZipFile) -> List[str]:
    """
    Parse an EPUB's container.xml → OPF → spine to get ordered hrefs.

    Returns a list of hrefs (relative to the OPF directory) in spine order.
    """
    # Find OPF path from container.xml
    container = ET.fromstring(zf.read("META-INF/container.xml"))
    ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfile = container.find(".//c:rootfile", ns)
    if rootfile is None:
        return []
    opf_path = rootfile.get("full-path", "")
    if not opf_path:
        return []

    opf_dir = os.path.dirname(opf_path)

    # Parse OPF
    opf = ET.fromstring(zf.read(opf_path))
    opf_ns = {"opf": "http://www.idpf.org/2007/opf"}

    # Build manifest id → href map
    manifest = {}
    for item in opf.findall(".//opf:manifest/opf:item", opf_ns):
        item_id = item.get("id", "")
        href = item.get("href", "")
        if item_id and href:
            # Normalize to full zip path
            full_href = os.path.normpath(os.path.join(opf_dir, href)) if opf_dir else href
            manifest[item_id] = full_href

    # Build spine order
    spine_hrefs = []
    for itemref in opf.findall(".//opf:spine/opf:itemref", opf_ns):
        idref = itemref.get("idref", "")
        if idref in manifest:
            spine_hrefs.append(manifest[idref])

    return spine_hrefs


def _find_epub_nav(zf: zipfile.ZipFile) -> Optional[str]:
    """Find the EPUB3 nav document path from the OPF manifest."""
    container = ET.fromstring(zf.read("META-INF/container.xml"))
    ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfile = container.find(".//c:rootfile", ns)
    if rootfile is None:
        return None
    opf_path = rootfile.get("full-path", "")
    if not opf_path:
        return None

    opf_dir = os.path.dirname(opf_path)
    opf = ET.fromstring(zf.read(opf_path))
    opf_ns = {"opf": "http://www.idpf.org/2007/opf"}

    for item in opf.findall(".//opf:manifest/opf:item", opf_ns):
        props = item.get("properties", "")
        if "nav" in props.split():
            href = item.get("href", "")
            if href:
                return os.path.normpath(os.path.join(opf_dir, href)) if opf_dir else href
    return None


def _parse_nav_toc(zf: zipfile.ZipFile, nav_path: str) -> List[Tuple[str, str, int]]:
    """
    Parse an EPUB3 nav document to extract TOC entries.

    Returns list of (title, href, level) tuples where href is the
    full zip path (relative to EPUB root) and level is the nesting depth.
    """
    nav_dir = os.path.dirname(nav_path)
    nav_content = zf.read(nav_path)

    # Parse as XML, handling XHTML namespace
    root = ET.fromstring(nav_content)
    xhtml_ns = {"x": "http://www.w3.org/1999/xhtml", "epub": "http://www.idpf.org/2007/ops"}

    # Find the nav element with epub:type="toc"
    nav_elem = None
    for nav in root.iter("{http://www.w3.org/1999/xhtml}nav"):
        epub_type = nav.get("{http://www.idpf.org/2007/ops}type", "")
        if epub_type == "toc":
            nav_elem = nav
            break

    if nav_elem is None:
        return []

    entries = []

    def walk_ol(ol_elem, depth):
        for li in ol_elem.findall("x:li", xhtml_ns):
            # Get the <a> element
            a_elem = li.find("x:a", xhtml_ns)
            if a_elem is not None:
                title = "".join(a_elem.itertext()).strip()
                href = a_elem.get("href", "")
                if title and href:
                    # Strip fragment, resolve relative to nav dir
                    href_base = href.split("#")[0]
                    if href_base:
                        full_href = os.path.normpath(os.path.join(nav_dir, unquote(href_base)))
                    else:
                        full_href = ""
                    entries.append((title, full_href, depth))

            # Recurse into nested <ol>
            nested_ol = li.find("x:ol", xhtml_ns)
            if nested_ol is not None:
                walk_ol(nested_ol, depth + 1)

    top_ol = nav_elem.find("x:ol", xhtml_ns)
    if top_ol is not None:
        walk_ol(top_ol, 1)

    return entries


def build_chapter_map_from_epub(epub_path: str, max_level: int = 2) -> List[Tuple[str, str, int]]:
    """
    Build a chapter map from an EPUB file using spine indices.

    Maps TOC entries to zero-padded spine index strings (e.g., "00055")
    which correspond to the first field of annotationSortIndex.

    Args:
        epub_path: Path to the EPUB file.
        max_level: Maximum heading depth to include.

    Returns:
        Sorted list of (title, spine_index_str, level) tuples.
        Returns empty list if EPUB has no nav document or TOC.
    """
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            # Get spine order
            spine_hrefs = _parse_epub_spine(zf)
            if not spine_hrefs:
                return []

            # Build href → spine index map
            href_to_spine = {}
            for idx, href in enumerate(spine_hrefs):
                href_to_spine[href] = idx

            # Find and parse nav document
            nav_path = _find_epub_nav(zf)
            if not nav_path:
                return []

            toc_entries = _parse_nav_toc(zf, nav_path)
            if not toc_entries:
                return []

            # Map TOC entries to spine indices
            entries = []
            for title, href, level in toc_entries:
                if level > max_level or not title.strip():
                    continue
                if href in href_to_spine:
                    spine_idx = f"{href_to_spine[href]:05d}"
                    entries.append((title.strip(), spine_idx, level))

            # Deduplicate consecutive entries with same title
            deduped = []
            for title, spine_idx, level in entries:
                if not deduped or deduped[-1][0] != title:
                    deduped.append((title, spine_idx, level))

            return deduped
    except Exception:
        return []


def get_chapter_map_for_epub(epub_path: str, max_level: int = 2) -> List[Tuple[str, str, int]]:
    """
    Convenience: extract TOC and build chapter map from EPUB with spine indices.

    Args:
        epub_path: Path to the EPUB file.
        max_level: Maximum heading depth to include.

    Returns:
        Sorted list of (title, spine_index_str, level) tuples, or empty list.
    """
    return build_chapter_map_from_epub(epub_path, max_level)


def main():
    """CLI entry point: print chapter map as JSON for a PDF or EPUB file."""
    import json
    import sys

    if len(sys.argv) != 2:
        print("Usage: zotero-chapter-map <file-path>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    try:
        if file_path.lower().endswith(".epub"):
            chapter_map = get_chapter_map_for_epub(file_path)
        else:
            chapter_map = get_chapter_map_for_pdf(file_path)
        # Output as JSON array of [title, page_label, level] arrays
        print(json.dumps([list(entry) for entry in chapter_map], ensure_ascii=False))
    except Exception:
        print("[]")
