#!/usr/bin/env python3
"""
Zotero Local API Annotations Retriever

This script retrieves all annotations from PDF attachments for a given Zotero item
using the Zotero local API.
"""

import requests
import json
import sys
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin


class ZoteroLocalAPI:
    """Class to interact with Zotero's local API"""

    # Common UTF-8/Latin-1 mojibake replacements (class constant, built once)
    _ENCODING_REPLACEMENTS = {
        # Smart quotes and dashes
        '\u00e2\u0080\u009c': '\u201c',  # left double quotation mark
        '\u00e2\u0080\u009d': '\u201d',  # right double quotation mark
        '\u00e2\u0080\u0098': '\u2018',  # left single quotation mark
        '\u00e2\u0080\u0099': '\u2019',  # right single quotation mark
        '\u00e2\u0080\u0094': '\u2014',  # em dash
        '\u00e2\u0080\u0093': '\u2013',  # en dash
        # Accented characters
        '\u00c3\u00a1': '\u00e1', '\u00c3\u00a9': '\u00e9',
        '\u00c3\u00ad': '\u00ed', '\u00c3\u00b3': '\u00f3',
        '\u00c3\u00ba': '\u00fa', '\u00c3\u00b1': '\u00f1',
        '\u00c3\u0080': '\u00c0', '\u00c3\u00a8': '\u00e8',
        '\u00c3\u00ac': '\u00ec', '\u00c3\u00b2': '\u00f2',
        '\u00c3\u00b9': '\u00f9', '\u00c3\u00a4': '\u00e4',
        '\u00c3\u00ab': '\u00eb', '\u00c3\u00af': '\u00ef',
        '\u00c3\u00b6': '\u00f6', '\u00c3\u00bc': '\u00fc',
        '\u00c3\u00a7': '\u00e7',
        # Symbols
        '\u00e2\u0080\u00a2': '\u2022',  # bullet
        '\u00e2\u0080\u00a6': '\u2026',  # ellipsis
        '\u00c2\u00b0': '\u00b0',        # degree
        '\u00c2\u00b1': '\u00b1',        # plus-minus
        '\u00c2\u00b2': '\u00b2',        # superscript 2
        '\u00c2\u00b3': '\u00b3',        # superscript 3
        '\u00c2\u00bd': '\u00bd',        # 1/2
        '\u00c2\u00bc': '\u00bc',        # 1/4
        '\u00c2\u00be': '\u00be',        # 3/4
        '\u00c2\u00a9': '\u00a9',        # copyright
        '\u00c2\u00ae': '\u00ae',        # registered
        '\u00c2\u00ab': '\u00ab',        # left guillemet
        '\u00c2\u00bb': '\u00bb',        # right guillemet
    }

    # Word-specific corruption fixes (separated from generic encoding fixes)
    _WORD_REPLACEMENTS = {
        'pe\u00c2\u00baple': 'people',
        'pe"\u00baple': 'people',
        'pe\u00baple': 'people',
        'house"hold': 'household',
        'house"wives': 'housewives',
        'single"family': 'single-family',
        'well"publicized': 'well-publicized',
        'car"ried': 'carried',
        'in"dustrialization': 'industrialization',
        'self"sufficient': 'self-sufficient',
        'water"cooled': 'water-cooled',
        'home"places': 'home places',
        'work"places': 'work places',
        'ex"pected': 'expected',
        'contempo\u00e2raries': 'contemporaries',
        'contempo"raries': 'contemporaries',
        'contempo\u2014raries': 'contemporaries',
    }

    def __init__(self, base_url: str = "http://localhost:23119"):
        """
        Initialize the Zotero Local API client

        Args:
            base_url: Base URL for Zotero local API (default: http://localhost:23119)
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self._bbt_client = None
        
    def _make_request(self, endpoint: str) -> Optional[Dict[Any, Any]]:
        """
        Make a GET request to the Zotero local API
        
        Args:
            endpoint: API endpoint (will be joined with base_url)
            
        Returns:
            JSON response as dictionary, or None if request failed
        """
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response from {url}: {e}")
            return None
    
    def get_item(self, item_id: str, library_id: Optional[str] = None) -> Optional[Dict[Any, Any]]:
        """
        Get a single item by ID
        
        Args:
            item_id: Zotero item ID
            library_id: Library/group ID (if None, uses personal library)
            
        Returns:
            Item data as dictionary, or None if not found
        """
        if library_id:
            return self._make_request(f"/api/groups/{library_id}/items/{item_id}")
        else:
            return self._make_request(f"/api/users/0/items/{item_id}")
    
    def get_item_children(self, item_id: str, library_id: Optional[str] = None) -> List[Dict[Any, Any]]:
        """
        Get all children of an item (attachments, notes, etc.)
        
        Args:
            item_id: Zotero item ID
            library_id: Library/group ID (if None, uses personal library)
            
        Returns:
            List of child items
        """
        if library_id:
            response = self._make_request(f"/api/groups/{library_id}/items/{item_id}/children")
        else:
            response = self._make_request(f"/api/users/0/items/{item_id}/children")
        
        # Zotero API returns data directly as a list
        if response and isinstance(response, list):
            return response
        return []
    
    def get_pdf_attachments(self, item_id: str, library_id: Optional[str] = None) -> List[Dict[Any, Any]]:
        """
        Get all PDF attachments for a given item
        
        Args:
            item_id: Zotero item ID
            library_id: Library/group ID (if None, uses personal library)
            
        Returns:
            List of PDF attachment items
        """
        return self.get_file_attachments(item_id, library_id, ['pdf'])
    
    def get_file_attachments(self, item_id: str, library_id: Optional[str] = None, 
                           file_types: List[str] = ['pdf', 'epub']) -> List[Dict[Any, Any]]:
        """
        Get all file attachments of specified types for a given item
        
        Args:
            item_id: Zotero item ID
            library_id: Library/group ID (if None, uses personal library)
            file_types: List of file types to include ('pdf', 'epub')
            
        Returns:
            List of file attachment items
        """
        children = self.get_item_children(item_id, library_id)
        file_attachments = []
        
        # Map file types to MIME types
        content_type_map = {
            'pdf': 'application/pdf',
            'epub': 'application/epub+zip'
        }
        
        allowed_content_types = [content_type_map[ft] for ft in file_types if ft in content_type_map]
        
        for child in children:
            if (child.get('data', {}).get('itemType') == 'attachment' and 
                child.get('data', {}).get('contentType') in allowed_content_types):
                file_attachments.append(child)
        
        return file_attachments
    
    def get_attachment_annotations(self, attachment_id: str, library_id: Optional[str] = None) -> List[Dict[Any, Any]]:
        """
        Get all annotations for a PDF attachment
        
        Args:
            attachment_id: Zotero attachment item ID
            library_id: Library/group ID (if None, uses personal library)
            
        Returns:
            List of annotation items
        """
        # First try the standard approach - get children of the attachment
        if library_id:
            response = self._make_request(f"/api/groups/{library_id}/items/{attachment_id}/children")
        else:
            response = self._make_request(f"/api/users/0/items/{attachment_id}/children")
        
        annotations = []
        if response and isinstance(response, list):
            # Filter for annotation items
            for item in response:
                if item.get('data', {}).get('itemType') == 'annotation':
                    annotations.append(item)
        
        # If no annotations found as children, try alternative approach:
        # Look for annotation items where parentItem matches our attachment_id
        if not annotations:
            # Get annotation items and filter by parent
            annotation_items = self.get_items(library_id=library_id, limit=1000, item_type="annotation")
            for item in annotation_items:
                if item.get('data', {}).get('parentItem') == attachment_id:
                    annotations.append(item)
        
        return annotations
    
    def get_libraries(self) -> List[Dict[str, Any]]:
        """
        Get all libraries (groups) available in Zotero
        
        Returns:
            List of library/group dictionaries
        """
        # Use user ID 0 (wildcard for current logged-in user) as per local API docs
        user_id = 0
        
        response = self._make_request(f"/api/users/{user_id}/groups")
        # Zotero API returns data directly as a list, not wrapped in a 'data' field
        if response and isinstance(response, list):
            return response
        return []
    
    def get_library_info(self, library_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific library/group
        
        Args:
            library_id: Library/group ID
            
        Returns:
            Library information dictionary, or None if not found
        """
        response = self._make_request(f"/api/groups/{library_id}")
        # Zotero API returns data directly, not wrapped in a 'data' field
        if response and isinstance(response, dict):
            return response
        return None
    
    def get_collections(self, library_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all collections from a library
        
        Args:
            library_id: Library/group ID (if None, uses personal library)
            
        Returns:
            List of collection dictionaries
        """
        if library_id:
            # Group library collections
            response = self._make_request(f"/api/groups/{library_id}/collections")
        else:
            # Personal library collections (use user ID 0)
            response = self._make_request(f"/api/users/0/collections")
        
        # Zotero API returns data directly as a list
        if response and isinstance(response, list):
            return response
        return []
    
    def get_items(self, library_id: Optional[str] = None, limit: int = 25, item_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get items from a library
        
        Args:
            library_id: Library/group ID (if None, uses personal library)
            limit: Maximum number of items to return
            item_type: Filter by item type (e.g., 'book', 'journalArticle')
            
        Returns:
            List of item dictionaries
        """
        params = f"?limit={limit}"
        if item_type:
            params += f"&itemType={item_type}"
        
        if library_id:
            # Group library items
            response = self._make_request(f"/api/groups/{library_id}/items{params}")
        else:
            # Personal library items (use user ID 0)
            response = self._make_request(f"/api/users/0/items{params}")
        
        # Zotero API returns data directly as a list
        if response and isinstance(response, list):
            return response
        return []
    
    def get_item_types(self) -> List[Dict[str, Any]]:
        """
        Get all available item types
        
        Returns:
            List of item type dictionaries
        """
        response = self._make_request("/api/itemTypes")
        return response if response is not None else []
    
    def get_top_level_items(self, library_id: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Get top-level items (excluding child items like attachments)
        
        Args:
            library_id: Library/group ID (if None, uses personal library)
            limit: Maximum number of items to return
            
        Returns:
            List of top-level item dictionaries
        """
        params = f"?limit={limit}&top=1"
        
        if library_id:
            response = self._make_request(f"/api/groups/{library_id}/items{params}")
        else:
            response = self._make_request(f"/api/users/0/items{params}")
        
        # Zotero API returns data directly as a list
        if response and isinstance(response, list):
            return response
        return []
    
    def _get_bbt_client(self):
        """Lazily create and cache a BetterBibTexClient."""
        if self._bbt_client is None:
            from zotero_cli.bbt_client import BetterBibTexClient
            self._bbt_client = BetterBibTexClient()
        return self._bbt_client

    def get_all_annotations_for_item(self, item_id: str, library_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all annotations from all PDF attachments for a given item.

        Tries Better BibTeX JSON-RPC first (richer annotation data).
        Falls back to native Zotero local API if BBT is unavailable.
        """
        # Try BBT first
        try:
            bbt = self._get_bbt_client()
            if bbt.is_available():
                lib_id = int(library_id) if library_id else 1
                return bbt.get_annotations_for_item(item_id, lib_id)
        except Exception:
            pass  # Fall through to native API

        # Native API fallback
        item = self.get_item(item_id, library_id)
        if not item:
            return {"error": f"Item {item_id} not found"}

        file_attachments = self.get_file_attachments(item_id, library_id)

        result = {
            "item_id": item_id,
            "item_title": item.get('data', {}).get('title', 'Unknown'),
            "item_type": item.get('data', {}).get('itemType', 'Unknown'),
            "attachments": []
        }

        for attachment in file_attachments:
            attachment_id = attachment['key']
            attachment_title = attachment.get('data', {}).get('title', 'Unknown')
            annotations = self.get_attachment_annotations(attachment_id, library_id)

            attachment_data = {
                "attachment_id": attachment_id,
                "attachment_title": attachment_title,
                "filename": attachment.get('data', {}).get('filename', 'Unknown'),
                "annotations_count": len(annotations),
                "annotations": annotations
            }

            result["attachments"].append(attachment_data)

        return result
    
    def normalize_text_encoding(self, text: str) -> str:
        """
        Fix common UTF-8/Latin-1 encoding issues in annotation text.

        Tries the standard double-encoding fix first (encode as latin-1,
        decode as utf-8). Falls back to the replacement dictionary for
        partial corruption that the standard fix can't handle.
        """
        if not text:
            return text

        # Try the standard double-encoding fix first
        try:
            fixed = text.encode('latin-1').decode('utf-8')
            # Only accept if it actually changed something and looks valid
            if fixed != text:
                return fixed
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass

        # Fall back to dictionary-based replacement
        normalized = text
        for wrong, correct in self._ENCODING_REPLACEMENTS.items():
            normalized = normalized.replace(wrong, correct)
        for wrong, correct in self._WORD_REPLACEMENTS.items():
            normalized = normalized.replace(wrong, correct)

        return normalized
    
    def _sort_annotations(self, annotations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort annotations by annotationSortIndex (ascending = reading order)."""
        def sort_key(ann):
            idx = ann.get('data', {}).get('annotationSortIndex', '')
            if idx:
                return idx
            # Fall back to page label
            page = ann.get('data', {}).get('annotationPageLabel', '0')
            try:
                return f"{int(page):05d}"
            except (ValueError, TypeError):
                return '99999'
        return sorted(annotations, key=sort_key)

    def _get_page_label(self, ann_data: Dict[str, Any]) -> str:
        """Extract page label string from annotation data, for chapter lookup.

        For PDF annotations, returns annotationPageLabel.
        For EPUB annotations (empty page label), extracts the spine index
        from annotationSortIndex (first field, e.g., "00055|001234" → "00055").
        """
        page_label = ann_data.get('annotationPageLabel', '')
        if page_label:
            return page_label
        # EPUB annotations: extract spine index from annotationSortIndex
        sort_index = ann_data.get('annotationSortIndex', '')
        if sort_index and '|' in sort_index:
            spine_idx = sort_index.split('|')[0]
            # Verify it looks like a zero-padded number
            if spine_idx.isdigit():
                return spine_idx
        # Fallback to pageIndex (0-indexed) converted to 1-indexed string
        position = ann_data.get('annotationPosition', {})
        if isinstance(position, str):
            try:
                import json as _json
                position = _json.loads(position)
            except (json.JSONDecodeError, TypeError):
                position = {}
        if isinstance(position, dict) and 'pageIndex' in position:
            return str(position['pageIndex'] + 1)
        return '0'

    def _build_zotero_open_link(self, attachment_id: str, page_label: str,
                                annotation_key: str, library_id: Optional[str] = None) -> str:
        """Build a zotero://open-pdf link for an annotation."""
        link = f"zotero://open-pdf/library/items/{attachment_id}"
        params = []
        if page_label:
            params.append(f"page={page_label}")
        if annotation_key:
            params.append(f"annotation={annotation_key}")
        if params:
            link += "?" + "&".join(params)
        return link

    @staticmethod
    def _is_spine_index(label: str) -> bool:
        """Check if a page label looks like an EPUB spine index (zero-padded digits, 5+ chars)."""
        return bool(label) and label.isdigit() and len(label) >= 5

    def _format_single_annotation_org(self, annotation: Dict[str, Any], attachment_id: str,
                                       citation_key: Optional[str] = None,
                                       library_id: Optional[str] = None) -> List[str]:
        """Format a single annotation as org-mode lines."""
        lines = []
        ann_data = annotation.get('data', {})
        ann_type = ann_data.get('annotationType', 'unknown')
        ann_key = ann_data.get('key', '')
        text = self.normalize_text_encoding(ann_data.get('annotationText', ''))
        comment = self.normalize_text_encoding(ann_data.get('annotationComment', ''))
        page_label = ann_data.get('annotationPageLabel', '')
        sort_index = ann_data.get('annotationSortIndex', '')
        color = ann_data.get('annotationColor', '')
        tags = ann_data.get('tags', [])

        # Page info for display — omit for EPUB annotations (no meaningful page label)
        if page_label and not self._is_spine_index(page_label):
            page_display = f"p. {page_label}"
        elif not page_label and '|' in sort_index:
            # EPUB annotation: no page label but has sort index
            page_display = "annotation"
        elif not page_label:
            page_display = "p. ?"
        else:
            page_display = "annotation"

        # Zotero open-pdf link
        zotero_link = self._build_zotero_open_link(attachment_id, page_label, ann_key, library_id)

        if ann_type == 'highlight' or ann_type == 'underline':
            if text:
                lines.append(f"[[{zotero_link}][{page_display}]]:")
                lines.append("#+begin_quote")
                lines.append(text)
                lines.append("#+end_quote")
                if comment:
                    lines.append("")
                    lines.append(comment)
                if citation_key:
                    page_info = page_label if page_label else "?"
                    lines.append("")
                    lines.append(f"[cite:@{citation_key}, p.{page_info}]")
        elif ann_type == 'note':
            lines.append(f"[[{zotero_link}][{page_display}]]:")
            if comment:
                lines.append("#+begin_comment")
                lines.append(comment)
                lines.append("#+end_comment")
        elif ann_type == 'image':
            lines.append(f"[[{zotero_link}][{page_display}]]:")
            lines.append("#+begin_example")
            lines.append(f"[Image annotation]")
            lines.append("#+end_example")
            if comment:
                lines.append("")
                lines.append(comment)

        # Tags
        if tags:
            tag_names = [t.get('tag', '') for t in tags if t.get('tag')]
            if tag_names:
                tag_str = ":" + ":".join(tag_names) + ":"
                lines.append(tag_str)

        return lines

    def _get_chapter_map_for_attachment(self, attachment: Dict[str, Any]) -> list:
        """Try to get a chapter map for a PDF or EPUB attachment."""
        from zotero_cli.pdf_toc import get_chapter_map_for_epub, get_chapter_map_for_pdf
        file_path = attachment.get('path', '')
        if not file_path:
            return []
        # Resolve storage path if needed
        import os
        if not os.path.isabs(file_path):
            # Try Zotero storage path pattern
            att_id = attachment.get('attachment_id', '')
            zotero_dir = os.path.expanduser("~/Zotero/storage")
            candidate = os.path.join(zotero_dir, att_id, file_path)
            if os.path.exists(candidate):
                file_path = candidate
            else:
                return []
        if not os.path.exists(file_path):
            return []
        try:
            if file_path.lower().endswith('.epub'):
                return get_chapter_map_for_epub(file_path)
            return get_chapter_map_for_pdf(file_path)
        except Exception:
            return []

    def format_as_org_mode(self, annotations_data: Dict[str, Any], citation_key: Optional[str] = None) -> str:
        """
        Format annotation data as org-mode text with per-annotation structure.

        Each annotation gets its own #+begin_quote block with a zotero://open-pdf
        link. Comments are interleaved with their annotations. When the PDF has a
        table of contents, annotations are grouped under chapter headings.
        """
        if "error" in annotations_data:
            return f"# Error: {annotations_data['error']}\n"

        org_content = []

        item_title = self.normalize_text_encoding(annotations_data.get('item_title', 'Unknown'))
        item_type = annotations_data.get('item_type', 'Unknown')
        item_id = annotations_data.get('item_id', 'Unknown')
        # Use citation_key from data if not passed explicitly
        if not citation_key:
            citation_key = annotations_data.get('citation_key')

        org_content.append(f"* {item_title}")
        org_content.append("  :PROPERTIES:")
        org_content.append(f"  :ITEM_TYPE: {item_type}")
        org_content.append(f"  :ZOTERO_KEY: {item_id}")
        if citation_key:
            org_content.append(f"  :CUSTOM_ID: {citation_key}")
        org_content.append("  :END:")
        org_content.append("")

        attachments = annotations_data.get('attachments', [])
        multi_attachment = len(attachments) > 1

        for attachment in attachments:
            attachment_title = self.normalize_text_encoding(attachment.get('attachment_title', 'Unknown PDF'))
            attachment_id = attachment.get('attachment_id', 'Unknown')
            annotations = attachment.get('annotations', [])

            if multi_attachment:
                org_content.append(f"** {attachment_title}")
                org_content.append("")
                chapter_heading_base = "**"
            else:
                chapter_heading_base = "*"

            if not annotations:
                if multi_attachment:
                    org_content.append("   No annotations found.")
                else:
                    org_content.append("No annotations found.")
                org_content.append("")
                continue

            # Sort annotations by sort index
            sorted_anns = self._sort_annotations(annotations)

            # Try to get chapter map for grouping
            chapter_map = self._get_chapter_map_for_attachment(attachment)
            current_chapters = {}  # level -> title

            for annotation in sorted_anns:
                ann_data = annotation.get('data', {})

                # Chapter grouping
                if chapter_map:
                    page_label = self._get_page_label(ann_data)
                    from zotero_cli.pdf_toc import get_chapters_for_page
                    chapters = get_chapters_for_page(chapter_map, page_label)
                    for title, level in chapters:
                        if current_chapters.get(level) != title:
                            current_chapters[level] = title
                            # Reset deeper levels when a shallower heading changes
                            deeper = [k for k in current_chapters if k > level]
                            for k in deeper:
                                del current_chapters[k]
                            heading = chapter_heading_base + "*" * level
                            org_content.append(f"{heading} {title}")
                            org_content.append("")

                ann_lines = self._format_single_annotation_org(
                    annotation, attachment_id, citation_key)
                org_content.extend(ann_lines)
                org_content.append("")

        return "\n".join(org_content)
    
    def _format_single_annotation_md(self, annotation: Dict[str, Any], attachment_id: str,
                                      citation_key: Optional[str] = None) -> List[str]:
        """Format a single annotation as markdown lines."""
        lines = []
        ann_data = annotation.get('data', {})
        ann_type = ann_data.get('annotationType', 'unknown')
        ann_key = ann_data.get('key', '')
        text = self.normalize_text_encoding(ann_data.get('annotationText', ''))
        comment = self.normalize_text_encoding(ann_data.get('annotationComment', ''))
        page_label = ann_data.get('annotationPageLabel', '')
        sort_index = ann_data.get('annotationSortIndex', '')
        tags = ann_data.get('tags', [])

        # Page info for display — omit for EPUB annotations (no meaningful page label)
        if page_label and not self._is_spine_index(page_label):
            page_display = f"p. {page_label}"
        elif not page_label and '|' in sort_index:
            page_display = "annotation"
        elif not page_label:
            page_display = "p. ?"
        else:
            page_display = "annotation"
        zotero_link = self._build_zotero_open_link(attachment_id, page_label, ann_key)

        if ann_type in ('highlight', 'underline'):
            if text:
                lines.append(f"[{page_display}]({zotero_link}):")
                lines.append("")
                lines.append(f"> {text}")
                if comment:
                    lines.append("")
                    lines.append(comment)
                if citation_key:
                    page_info = page_label if page_label else "?"
                    lines.append("")
                    lines.append(f"[cite:@{citation_key}, p.{page_info}]")
        elif ann_type == 'note':
            lines.append(f"[{page_display}]({zotero_link}):")
            if comment:
                lines.append("")
                lines.append(f"*{comment}*")
        elif ann_type == 'image':
            lines.append(f"[{page_display}]({zotero_link}):")
            lines.append("")
            lines.append("`[Image annotation]`")
            if comment:
                lines.append("")
                lines.append(comment)

        if tags:
            tag_names = [t.get('tag', '') for t in tags if t.get('tag')]
            if tag_names:
                lines.append("")
                lines.append("Tags: " + ", ".join(f"`{t}`" for t in tag_names))

        return lines

    def format_as_markdown(self, annotations_data: Dict[str, Any], citation_key: Optional[str] = None) -> str:
        """
        Format annotation data as markdown with per-annotation structure.

        Each annotation gets its own blockquote with a zotero link.
        Comments are interleaved with their annotations.
        """
        if "error" in annotations_data:
            return f"# Error: {annotations_data['error']}\n"

        md_content = []

        item_title = self.normalize_text_encoding(annotations_data.get('item_title', 'Unknown'))
        item_type = annotations_data.get('item_type', 'Unknown')
        item_id = annotations_data.get('item_id', 'Unknown')
        if not citation_key:
            citation_key = annotations_data.get('citation_key')

        md_content.append(f"# {item_title}")
        md_content.append("")
        md_content.append(f"**Item Type:** {item_type}")
        md_content.append(f"**Zotero Key:** {item_id}")
        if citation_key:
            md_content.append(f"**Citation Key:** {citation_key}")
        md_content.append("")

        attachments = annotations_data.get('attachments', [])
        multi_attachment = len(attachments) > 1

        for attachment in attachments:
            attachment_title = self.normalize_text_encoding(attachment.get('attachment_title', 'Unknown PDF'))
            attachment_id = attachment.get('attachment_id', 'Unknown')
            annotations = attachment.get('annotations', [])

            if multi_attachment:
                md_content.append(f"## {attachment_title}")
                md_content.append("")

            if not annotations:
                md_content.append("No annotations found.")
                md_content.append("")
                continue

            sorted_anns = self._sort_annotations(annotations)

            chapter_map = self._get_chapter_map_for_attachment(attachment)
            current_chapters = {}  # level -> title
            chapter_heading_base = "#" + ("#" if multi_attachment else "")

            for annotation in sorted_anns:
                ann_data = annotation.get('data', {})

                if chapter_map:
                    page_label = self._get_page_label(ann_data)
                    from zotero_cli.pdf_toc import get_chapters_for_page
                    chapters = get_chapters_for_page(chapter_map, page_label)
                    for title, level in chapters:
                        if current_chapters.get(level) != title:
                            current_chapters[level] = title
                            deeper = [k for k in current_chapters if k > level]
                            for k in deeper:
                                del current_chapters[k]
                            heading = chapter_heading_base + "#" * level
                            md_content.append(f"{heading} {title}")
                            md_content.append("")

                ann_lines = self._format_single_annotation_md(
                    annotation, attachment_id, citation_key)
                md_content.extend(ann_lines)
                md_content.append("")

        return "\n".join(md_content)
    
    def get_citation_key_for_item(self, item_id: str, library_id: Optional[str] = None) -> Optional[str]:
        """
        Get the BibTeX citation key for a Zotero item.

        Tries BBT JSON-RPC first (fast, direct). Falls back to exporting
        BibTeX via native API and parsing the key with regex.
        """
        # Try BBT first
        try:
            bbt = self._get_bbt_client()
            if bbt.is_available():
                lib_id = int(library_id) if library_id else 1
                key = bbt.get_citation_key(item_id, lib_id)
                if key:
                    return key
        except Exception:
            pass

        # Fall back to native BibTeX export
        try:
            bibtex_data = self.export_item_bibtex(item_id, library_id)
            if not bibtex_data:
                return None

            import re
            match = re.search(r'@\w+\s*{\s*([^,\s]+)\s*,', bibtex_data)
            if match:
                return match.group(1)

            return None

        except Exception as e:
            print(f"Error getting citation key for item {item_id}: {e}")
            return None
    
    def export_item_bibtex(self, item_id: str, library_id: Optional[str] = None) -> Optional[str]:
        """
        Export a single item as BibTeX.
        
        Args:
            item_id: Zotero item ID
            library_id: Optional library ID for group libraries
            
        Returns:
            BibTeX string or None if export failed
        """
        try:
            if library_id:
                url = f"{self.base_url}/api/groups/{library_id}/items/{item_id}?format=bibtex"
            else:
                url = f"{self.base_url}/api/users/0/items/{item_id}?format=bibtex"
            
            response = requests.get(url)
            if response.status_code == 200:
                return response.text.strip()
            else:
                return None
                
        except Exception as e:
            return None
    
    def download_attachment_file(self, attachment_id: str, target_path: str, library_id: Optional[str] = None) -> bool:
        """
        Download an attachment file to the local filesystem.
        
        Args:
            attachment_id: Zotero attachment item ID
            target_path: Local file path where attachment should be saved
            library_id: Optional library ID for group libraries
            
        Returns:
            True if download successful, False otherwise
        """
        try:
            import os
            import shutil
            import urllib.parse
            import re
            
            # Get attachment details to check if file is available locally
            attachment_details = self.get_item(attachment_id, library_id)
            if not attachment_details:
                print(f"Could not retrieve attachment details for {attachment_id}")
                return False
            
            # Construct file download URL
            if library_id:
                url = f"{self.base_url}/api/groups/{library_id}/items/{attachment_id}/file"
            else:
                url = f"{self.base_url}/api/users/0/items/{attachment_id}/file"
            
            # Create target directory if it doesn't exist
            target_dir = os.path.dirname(target_path)
            if target_dir:  # Only create directory if there is one
                os.makedirs(target_dir, exist_ok=True)
            
            # Try HEAD request first to check if endpoint exists and get redirect
            head_response = requests.head(url, allow_redirects=False)
            
            # Check if we got a redirect with a file:// URL
            if head_response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = head_response.headers.get('Location', '')
                
                if redirect_url.startswith('file://'):
                    # Extract local file path from file:// URL
                    local_path = urllib.parse.unquote(redirect_url[7:])  # Remove 'file://' prefix
                    
                    if os.path.exists(local_path):
                        shutil.copy2(local_path, target_path)
                        return os.path.exists(target_path)
                    else:
                        print(f"Warning: Local file does not exist: {local_path}")
                        return False
            
            # If no redirect or not a file:// redirect, try direct download
            try:
                response = requests.get(url, stream=True, allow_redirects=True)
                
                if response.status_code == 200:
                    with open(target_path, 'wb') as f:
                        shutil.copyfileobj(response.raw, f)
                    return os.path.exists(target_path)
                else:
                    print(f"Failed to download attachment {attachment_id}: HTTP {response.status_code}")
                    return False
                    
            except requests.exceptions.InvalidSchema as e:
                # This happens when we get redirected to file:// but requests follows it
                # Extract the file path from the error message
                error_str = str(e)
                if 'file://' in error_str:
                    file_match = re.search(r"file://([^']+)", error_str)
                    if file_match:
                        local_path = urllib.parse.unquote(file_match.group(1))
                        
                        if os.path.exists(local_path):
                            shutil.copy2(local_path, target_path)
                            return os.path.exists(target_path)
                return False
                
        except Exception as e:
            print(f"Error downloading attachment {attachment_id}: {e}")
            return False
    
    def get_attachment_metadata(self, item_id: str, library_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract metadata for a Zotero item suitable for YAML frontmatter.
        
        Args:
            item_id: Zotero item ID
            library_id: Optional library ID for group libraries
            
        Returns:
            Dictionary with metadata fields
        """
        try:
            item_data = self.get_item(item_id, library_id)
            if not item_data:
                return {}
            
            data = item_data.get('data', {})
            
            # Extract basic metadata
            metadata = {
                'title': self.normalize_text_encoding(data.get('title', 'Unknown Title')),
                'zotero_key': item_id,
                'item_type': data.get('itemType', 'unknown')
            }
            
            # Extract authors
            creators = data.get('creators', [])
            if creators:
                authors = []
                for creator in creators:
                    if creator.get('creatorType') in ['author', 'editor']:
                        first_name = creator.get('firstName', '')
                        last_name = creator.get('lastName', '')
                        if first_name and last_name:
                            authors.append(f"{first_name} {last_name}")
                        elif last_name:
                            authors.append(last_name)
                        elif creator.get('name'):  # Organization name
                            authors.append(creator.get('name'))
                
                if authors:
                    metadata['author'] = authors[0] if len(authors) == 1 else authors
            
            # Extract year
            date = data.get('date', '')
            if date:
                # Try to extract year from various date formats
                import re
                year_match = re.search(r'\b(19|20)\d{2}\b', date)
                if year_match:
                    metadata['year'] = int(year_match.group())
            
            # Get citation key
            citation_key = self.get_citation_key_for_item(item_id, library_id)
            if citation_key:
                metadata['citation_key'] = citation_key
            
            # Add publication details if available
            if data.get('publicationTitle'):
                metadata['publication'] = self.normalize_text_encoding(data['publicationTitle'])
            if data.get('volume'):
                metadata['volume'] = data['volume']
            if data.get('issue'):
                metadata['issue'] = data['issue']
            if data.get('pages'):
                metadata['pages'] = data['pages']
            if data.get('DOI'):
                metadata['doi'] = data['DOI']
            if data.get('url'):
                metadata['url'] = data['url']
            
            return metadata
            
        except Exception as e:
            print(f"Error extracting metadata for item {item_id}: {e}")
            return {}
    
    def get_collection_items(self, collection_id: str, library_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all items from a specific collection
        
        Args:
            collection_id: Zotero collection ID
            library_id: Library/group ID (if None, uses personal library)
            limit: Maximum number of items to return (default: 100)
            
        Returns:
            List of item dictionaries from the collection
        """
        params = f"?limit={limit}"
        
        if library_id:
            response = self._make_request(f"/api/groups/{library_id}/collections/{collection_id}/items{params}")
        else:
            response = self._make_request(f"/api/users/0/collections/{collection_id}/items{params}")
        
        # Zotero API returns data directly as a list
        if response and isinstance(response, list):
            return response
        return []
    
    def get_collection_info(self, collection_id: str, library_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific collection
        
        Args:
            collection_id: Zotero collection ID
            library_id: Library/group ID (if None, uses personal library)
            
        Returns:
            Collection information dictionary, or None if not found
        """
        if library_id:
            response = self._make_request(f"/api/groups/{library_id}/collections/{collection_id}")
        else:
            response = self._make_request(f"/api/users/0/collections/{collection_id}")
        
        if response and isinstance(response, dict):
            return response
        return None
    
    def get_all_collection_annotations(self, collection_id: str, library_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all annotations from all items in a collection
        
        Args:
            collection_id: Zotero collection ID
            library_id: Library/group ID (if None, uses personal library)
            
        Returns:
            Dictionary containing collection info and all annotations organized by item
        """
        # Get collection information
        collection_info = self.get_collection_info(collection_id, library_id)
        if not collection_info:
            return {"error": f"Collection {collection_id} not found"}
        
        # Get all items in the collection
        collection_items = self.get_collection_items(collection_id, library_id, limit=1000)
        
        result = {
            "collection_id": collection_id,
            "collection_name": collection_info.get('data', {}).get('name', 'Unknown'),
            "collection_parent": collection_info.get('data', {}).get('parentCollection', None),
            "library_id": library_id,
            "items_count": len(collection_items),
            "items": []
        }
        
        # Process each item in the collection
        for item in collection_items:
            item_id = item['key']
            item_data = item.get('data', {})
            item_type = item_data.get('itemType', 'unknown')
            
            # Skip attachments and annotations - we only want top-level items
            if item_type in ['attachment', 'note', 'annotation']:
                continue
            
            # Get annotations for this item
            item_annotations = self.get_all_annotations_for_item(item_id, library_id)
            
            # Only include items that have annotations
            if "error" not in item_annotations and item_annotations.get('attachments'):
                total_annotations = sum(att['annotations_count'] for att in item_annotations['attachments'])
                if total_annotations > 0:
                    result["items"].append(item_annotations)
        
        return result
    
    def format_collection_annotations_as_org(self, collection_data: Dict[str, Any]) -> str:
        """
        Format collection annotation data as org-mode text
        
        Args:
            collection_data: Result from get_all_collection_annotations
            
        Returns:
            Formatted org-mode string
        """
        if "error" in collection_data:
            return f"# Error: {collection_data['error']}\n"
        
        org_content = []
        
        # Main collection header
        collection_name = self.normalize_text_encoding(collection_data.get('collection_name', 'Unknown'))
        collection_id = collection_data.get('collection_id', 'Unknown')
        library_id = collection_data.get('library_id', 'Personal Library')
        items_count = collection_data.get('items_count', 0)
        items_with_annotations = len(collection_data.get('items', []))
        
        org_content.append(f"* Collection: {collection_name}")
        org_content.append(f"  :PROPERTIES:")
        org_content.append(f"  :COLLECTION_ID: {collection_id}")
        if library_id:
            org_content.append(f"  :LIBRARY_ID: {library_id}")
        org_content.append(f"  :TOTAL_ITEMS: {items_count}")
        org_content.append(f"  :ITEMS_WITH_ANNOTATIONS: {items_with_annotations}")
        org_content.append(f"  :END:")
        org_content.append("")
        
        if not collection_data.get('items'):
            org_content.append("No items with annotations found in this collection.")
            org_content.append("")
            return "\n".join(org_content)
        
        # Process each item with annotations
        for item_data in collection_data['items']:
            # Get citation key for org-cite format
            citation_key = self.get_citation_key_for_item(item_data['item_id'], library_id)
            
            # Format item annotations (use existing function but at sub-level)
            item_org = self.format_as_org_mode(item_data, citation_key)
            
            # Adjust heading levels (add one * to each heading)
            adjusted_lines = []
            for line in item_org.split('\n'):
                if line.startswith('*'):
                    adjusted_lines.append('*' + line)
                else:
                    adjusted_lines.append(line)
            
            org_content.extend(adjusted_lines)
            org_content.append("")
        
        return "\n".join(org_content)
    
    def format_collection_annotations_as_markdown(self, collection_data: Dict[str, Any]) -> str:
        """
        Format collection annotation data as markdown text
        
        Args:
            collection_data: Result from get_all_collection_annotations
            
        Returns:
            Formatted markdown string
        """
        if "error" in collection_data:
            return f"# Error: {collection_data['error']}\n"
        
        md_content = []
        
        # Main collection header
        collection_name = self.normalize_text_encoding(collection_data.get('collection_name', 'Unknown'))
        collection_id = collection_data.get('collection_id', 'Unknown')
        library_id = collection_data.get('library_id', 'Personal Library')
        items_count = collection_data.get('items_count', 0)
        items_with_annotations = len(collection_data.get('items', []))
        
        md_content.append(f"# Collection: {collection_name}")
        md_content.append("")
        md_content.append(f"**Collection ID:** {collection_id}")
        if library_id:
            md_content.append(f"**Library ID:** {library_id}")
        md_content.append(f"**Total Items:** {items_count}")
        md_content.append(f"**Items with Annotations:** {items_with_annotations}")
        md_content.append("")
        
        if not collection_data.get('items'):
            md_content.append("No items with annotations found in this collection.")
            md_content.append("")
            return "\n".join(md_content)
        
        # Process each item with annotations
        for item_data in collection_data['items']:
            # Get citation key for citations
            citation_key = self.get_citation_key_for_item(item_data['item_id'], library_id)
            
            # Format item annotations (use existing function but at sub-level)
            item_md = self.format_as_markdown(item_data, citation_key)
            
            # Adjust heading levels (add one # to each heading)
            adjusted_lines = []
            for line in item_md.split('\n'):
                if line.startswith('#'):
                    adjusted_lines.append('#' + line)
                else:
                    adjusted_lines.append(line)
            
            md_content.extend(adjusted_lines)
            md_content.append("")
        
        return "\n".join(md_content)
    
    def export_library_attachments(self, library_id: Optional[str] = None, target_folder: str = "zotero_export", 
                                 file_types: List[str] = ['pdf', 'epub'], convert_to_markdown: bool = True) -> Dict[str, Any]:
        """
        Export all file attachments from a library to a local folder.
        
        Args:
            library_id: Library ID (None for personal library)
            target_folder: Target folder for export
            file_types: List of file types to export ('pdf', 'epub')
            convert_to_markdown: Whether to convert files to markdown using markitdown
            
        Returns:
            Summary dictionary with export statistics
        """
        import os
        from pathlib import Path
        
        try:
            from markitdown import MarkItDown
            import yaml
        except ImportError:
            print("Error: markitdown and pyyaml libraries are required. Install with: pip install markitdown pyyaml")
            return {'error': 'Missing dependencies'}
        
        md = MarkItDown()
        
        # Create directory structure
        target_path = Path(target_folder)
        originals_path = target_path / "originals"
        markdown_path = target_path / "markdown"
        
        originals_path.mkdir(parents=True, exist_ok=True)
        if convert_to_markdown:
            markdown_path.mkdir(parents=True, exist_ok=True)
        
        # Get all items from library
        items = self.get_items(library_id, limit=1000)
        
        exported_files = []
        failed_downloads = []
        
        print(f"Processing {len(items)} items from library...")
        
        for item in items:
            item_id = item.get('key')
            if not item_id:
                continue
                
            # Get file attachments for this item
            attachments = self.get_file_attachments(item_id, library_id, file_types)
            
            if not attachments:
                continue
                
            # Get metadata for the parent item
            metadata = self.get_attachment_metadata(item_id, library_id)
            citation_key = metadata.get('citation_key', item_id)
            
            print(f"Processing item: {metadata.get('title', 'Unknown')} ({citation_key})")
            
            for attachment in attachments:
                attachment_id = attachment.get('key')
                attachment_data = attachment.get('data', {})
                filename = attachment_data.get('filename', 'unknown')
                content_type = attachment_data.get('contentType', '')
                
                # Determine file extension
                if content_type == 'application/pdf':
                    ext = '.pdf'
                elif content_type == 'application/epub+zip':
                    ext = '.epub'
                else:
                    continue
                
                # Create safe filename using citation key
                safe_filename = f"{citation_key}{ext}"
                original_file_path = originals_path / safe_filename
                
                # Download original file
                print(f"  Downloading {filename} -> {safe_filename}")
                if self.download_attachment_file(attachment_id, str(original_file_path), library_id):
                    exported_files.append({
                        'item_id': item_id,
                        'attachment_id': attachment_id,
                        'original_filename': filename,
                        'exported_filename': safe_filename,
                        'citation_key': citation_key,
                        'file_type': ext[1:]  # Remove the dot
                    })
                    
                    # Convert to markdown if requested
                    if convert_to_markdown:
                        markdown_file_path = markdown_path / f"{citation_key}.md"
                        print(f"  Converting to markdown: {markdown_file_path.name}")
                        
                        try:
                            # Convert file to markdown
                            result = md.convert(str(original_file_path))
                            markdown_content = result.text_content
                            
                            # Add YAML frontmatter
                            yaml_metadata = metadata.copy()
                            yaml_metadata['original_file'] = f"../originals/{safe_filename}"
                            
                            # Create full markdown content with frontmatter
                            yaml_frontmatter = yaml.dump(yaml_metadata, default_flow_style=False, allow_unicode=True)
                            full_content = f"---\n{yaml_frontmatter}---\n\n{markdown_content}"
                            
                            # Write markdown file
                            with open(markdown_file_path, 'w', encoding='utf-8') as f:
                                f.write(full_content)
                                
                        except Exception as e:
                            print(f"  Warning: Failed to convert {safe_filename} to markdown: {e}")
                    
                else:
                    failed_downloads.append({
                        'item_id': item_id,
                        'attachment_id': attachment_id,
                        'filename': filename,
                        'citation_key': citation_key
                    })
        
        # Return summary
        summary = {
            'total_files_exported': len(exported_files),
            'failed_downloads': len(failed_downloads),
            'target_folder': str(target_path),
            'file_types': file_types,
            'converted_to_markdown': convert_to_markdown,
            'exported_files': exported_files
        }
        
        if failed_downloads:
            summary['failed_downloads_list'] = failed_downloads
        
        print(f"\n✅ Export complete!")
        print(f"   Exported {len(exported_files)} files to {target_path}")
        if failed_downloads:
            print(f"   ⚠️  {len(failed_downloads)} downloads failed")
        
        return summary
    
    def export_collection_attachments(self, collection_id: str, library_id: Optional[str] = None, 
                                    target_folder: str = "zotero_collection_export", 
                                    file_types: List[str] = ['pdf', 'epub'], 
                                    convert_to_markdown: bool = True) -> Dict[str, Any]:
        """
        Export all file attachments from a collection to a local folder.
        
        Args:
            collection_id: Collection ID
            library_id: Library ID (None for personal library)
            target_folder: Target folder for export
            file_types: List of file types to export ('pdf', 'epub')
            convert_to_markdown: Whether to convert files to markdown using markitdown
            
        Returns:
            Summary dictionary with export statistics
        """
        import os
        from pathlib import Path
        
        try:
            from markitdown import MarkItDown
            import yaml
        except ImportError:
            print("Error: markitdown and pyyaml libraries are required. Install with: pip install markitdown pyyaml")
            return {'error': 'Missing dependencies'}
        
        md = MarkItDown()
        
        # Get collection info
        collection_info = self.get_collection_info(collection_id, library_id)
        collection_name = collection_info.get('data', {}).get('name', 'Unknown Collection') if collection_info else 'Unknown Collection'
        
        print(f"Exporting attachments from collection: {collection_name}")
        
        # Create directory structure
        target_path = Path(target_folder)
        originals_path = target_path / "originals"
        markdown_path = target_path / "markdown"
        
        originals_path.mkdir(parents=True, exist_ok=True)
        if convert_to_markdown:
            markdown_path.mkdir(parents=True, exist_ok=True)
        
        # Get all items from collection
        items = self.get_collection_items(collection_id, library_id)
        
        exported_files = []
        failed_downloads = []
        
        print(f"Processing {len(items)} items from collection...")
        
        for item in items:
            item_id = item.get('key')
            if not item_id:
                continue
                
            # Get file attachments for this item
            attachments = self.get_file_attachments(item_id, library_id, file_types)
            
            if not attachments:
                continue
                
            # Get metadata for the parent item
            metadata = self.get_attachment_metadata(item_id, library_id)
            citation_key = metadata.get('citation_key', item_id)
            
            print(f"Processing item: {metadata.get('title', 'Unknown')} ({citation_key})")
            
            for attachment in attachments:
                attachment_id = attachment.get('key')
                attachment_data = attachment.get('data', {})
                filename = attachment_data.get('filename', 'unknown')
                content_type = attachment_data.get('contentType', '')
                
                # Determine file extension
                if content_type == 'application/pdf':
                    ext = '.pdf'
                elif content_type == 'application/epub+zip':
                    ext = '.epub'
                else:
                    continue
                
                # Create safe filename using citation key
                safe_filename = f"{citation_key}{ext}"
                original_file_path = originals_path / safe_filename
                
                # Download original file
                print(f"  Downloading {filename} -> {safe_filename}")
                if self.download_attachment_file(attachment_id, str(original_file_path), library_id):
                    exported_files.append({
                        'item_id': item_id,
                        'attachment_id': attachment_id,
                        'original_filename': filename,
                        'exported_filename': safe_filename,
                        'citation_key': citation_key,
                        'file_type': ext[1:]  # Remove the dot
                    })
                    
                    # Convert to markdown if requested
                    if convert_to_markdown:
                        markdown_file_path = markdown_path / f"{citation_key}.md"
                        print(f"  Converting to markdown: {markdown_file_path.name}")
                        
                        try:
                            # Convert file to markdown
                            result = md.convert(str(original_file_path))
                            markdown_content = result.text_content
                            
                            # Add YAML frontmatter
                            yaml_metadata = metadata.copy()
                            yaml_metadata['original_file'] = f"../originals/{safe_filename}"
                            yaml_metadata['collection'] = collection_name
                            yaml_metadata['collection_id'] = collection_id
                            
                            # Create full markdown content with frontmatter
                            yaml_frontmatter = yaml.dump(yaml_metadata, default_flow_style=False, allow_unicode=True)
                            full_content = f"---\n{yaml_frontmatter}---\n\n{markdown_content}"
                            
                            # Write markdown file
                            with open(markdown_file_path, 'w', encoding='utf-8') as f:
                                f.write(full_content)
                                
                        except Exception as e:
                            print(f"  Warning: Failed to convert {safe_filename} to markdown: {e}")
                    
                else:
                    failed_downloads.append({
                        'item_id': item_id,
                        'attachment_id': attachment_id,
                        'filename': filename,
                        'citation_key': citation_key
                    })
        
        # Return summary
        summary = {
            'collection_name': collection_name,
            'collection_id': collection_id,
            'total_files_exported': len(exported_files),
            'failed_downloads': len(failed_downloads),
            'target_folder': str(target_path),
            'file_types': file_types,
            'converted_to_markdown': convert_to_markdown,
            'exported_files': exported_files
        }
        
        if failed_downloads:
            summary['failed_downloads_list'] = failed_downloads
        
        print(f"\n✅ Export complete!")
        print(f"   Exported {len(exported_files)} files from '{collection_name}' to {target_path}")
        if failed_downloads:
            print(f"   ⚠️  {len(failed_downloads)} downloads failed")
        
        return summary


def main():
    """Main function to demonstrate usage"""
    args = sys.argv[1:]

    if not args or '--help' in args or '-h' in args:
        print("Usage: zotero-get-annots <item_id> [--org|--markdown] [--stdout]")
        print("Example: zotero-get-annots ABCD1234")
        print("Example: zotero-get-annots ABCD1234 --org")
        print("Example: zotero-get-annots ABCD1234 --org --stdout")
        sys.exit(1)

    item_id = args[0]
    flags = set(args[1:])
    org_mode = '--org' in flags
    markdown_mode = '--markdown' in flags
    stdout_mode = '--stdout' in flags

    # When --stdout, send status messages to stderr so stdout is clean
    def status(msg):
        if stdout_mode:
            print(msg, file=sys.stderr)
        else:
            print(msg)

    # Initialize API client
    api = ZoteroLocalAPI()

    # Get all annotations for the item
    status(f"Retrieving annotations for item: {item_id}")
    result = api.get_all_annotations_for_item(item_id)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    total_annotations = sum(att['annotations_count'] for att in result['attachments'])

    # Handle formatted output
    if org_mode or markdown_mode:
        # Brief status line
        status(f"Item: {result['item_title']} | {len(result['attachments'])} attachment(s) | {total_annotations} annotation(s)")

        citation_key = api.get_citation_key_for_item(item_id)
        if citation_key:
            status(f"Citation key: {citation_key}")

        if org_mode:
            content = api.format_as_org_mode(result, citation_key)
            file_ext = "org"
        else:
            content = api.format_as_markdown(result, citation_key)
            file_ext = "md"

        if stdout_mode:
            print(content)
        else:
            output_file = f"annotations_{item_id}.{file_ext}"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Saved to: {output_file}")
    else:
        # JSON mode: print detailed summary for debugging
        status(f"\nItem: {result['item_title']} ({result['item_type']})")
        status(f"PDF Attachments: {len(result['attachments'])}")
        status(f"Total Annotations: {total_annotations}")

        for i, attachment in enumerate(result['attachments'], 1):
            status(f"\n--- Attachment {i}: {attachment['attachment_title']} ---")
            status(f"File: {attachment['filename']}")
            status(f"Annotations: {attachment['annotations_count']}")

            for j, annotation in enumerate(attachment['annotations'], 1):
                ann_data = annotation.get('data', {})
                ann_type = ann_data.get('annotationType', 'unknown')
                text = ann_data.get('annotationText', '')
                comment = ann_data.get('annotationComment', '')

                status(f"  {j}. Type: {ann_type}")
                if text:
                    status(f"     Text: {text[:100]}{'...' if len(text) > 100 else ''}")
                if comment:
                    status(f"     Comment: {comment[:100]}{'...' if len(comment) > 100 else ''}")

        if stdout_mode:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            output_file = f"annotations_{item_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\nFull results saved to: {output_file}")


if __name__ == "__main__":
    main()


# Example usage as a module:
# 
# from get_annots import ZoteroLocalAPI
# 
# api = ZoteroLocalAPI()
# 
# # Get all libraries
# libraries = api.get_libraries()
# print("Available libraries:", json.dumps(libraries, indent=2))
# 
# # Get specific library info
# if libraries:
#     lib_info = api.get_library_info(libraries[0]['id'])
#     print("Library info:", json.dumps(lib_info, indent=2))
# 
# # Get annotations for an item
# annotations = api.get_all_annotations_for_item("YOUR_ITEM_ID")
# print(json.dumps(annotations, indent=2))
