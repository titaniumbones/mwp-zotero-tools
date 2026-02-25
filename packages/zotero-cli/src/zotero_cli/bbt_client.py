"""
Better BibTeX JSON-RPC client for Zotero.

Provides access to Zotero's annotations and citation keys via the
Better BibTeX plugin's JSON-RPC API. Adapted from the zotero-mcp
server implementation.
"""

import json
import os
from typing import Any, Dict, List, Optional

import requests


class BetterBibTexClient:
    """Client for Better BibTeX JSON-RPC API."""

    def __init__(self, port: str = "23119"):
        self.port = port
        self.base_url = f"http://127.0.0.1:{self.port}/better-bibtex/json-rpc"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _make_request(self, method: str, params: List[Any]) -> Any:
        """Make a JSON-RPC request to BBT."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        response = requests.post(
            self.base_url,
            headers=self.headers,
            data=json.dumps(payload),
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            error_msg = str(data["error"].get("message", "Unknown error"))
            error_data = data["error"].get("data", "")
            if error_data:
                error_msg += f": {error_data}"
            raise RuntimeError(f"BBT API error: {error_msg}")

        return data.get("result", {})

    def is_available(self) -> bool:
        """Check if BBT is running and accessible."""
        try:
            response = requests.get(
                f"http://127.0.0.1:{self.port}/better-bibtex/cayw?probe=true",
                timeout=5,
            )
            return response.text == "ready"
        except Exception:
            return False

    def get_citation_key(self, item_key: str, library_id: int = 1) -> Optional[str]:
        """Resolve a Zotero item key to its BBT citation key."""
        item_keys = [f"{library_id}:{item_key}"]
        mapping = self._make_request("item.citationkey", [item_keys])
        if not mapping:
            return None
        full_key = f"{library_id}:{item_key}"
        return mapping.get(full_key)

    def search_item(self, citekey: str) -> Optional[Dict[str, Any]]:
        """Search for an item by citekey, returning basic item data."""
        results = self._make_request("item.search", [citekey])
        if not results:
            return None
        return next((r for r in results if r.get("citekey") == citekey), None)

    def get_attachments(self, citekey: str, library_id: int = 1) -> List[Dict[str, Any]]:
        """Get all attachments (with annotations) for an item by citekey."""
        return self._make_request("item.attachments", [citekey, library_id])

    def get_annotations_for_item(self, item_key: str, library_id: int = 1) -> Dict[str, Any]:
        """
        Get all annotations for a Zotero item via BBT.

        Returns a dict in the same shape as ZoteroLocalAPI.get_all_annotations_for_item():
        {
            "item_id": str,
            "item_title": str,
            "item_type": str,
            "attachments": [
                {
                    "attachment_id": str,
                    "attachment_title": str,
                    "filename": str,
                    "annotations_count": int,
                    "annotations": [...]
                }
            ]
        }
        """
        # Get citation key
        citekey = self.get_citation_key(item_key, library_id)
        if not citekey:
            raise RuntimeError(f"No citation key found for item {item_key}")

        # Search to get item metadata
        item_info = self.search_item(citekey)
        if not item_info:
            raise RuntimeError(f"Item not found for citekey {citekey}")

        # Get attachments with embedded annotations
        attachments = self.get_attachments(citekey, library_id)

        result = {
            "item_id": item_key,
            "item_title": item_info.get("title", "Unknown"),
            "item_type": item_info.get("itemType", "Unknown"),
            "citation_key": citekey,
            "attachments": [],
        }

        for attachment in attachments:
            att_path = attachment.get("path", "")
            raw_annotations = attachment.get("annotations", [])

            # Extract attachment ID: try 'open' URL, then first annotation's parentItem
            att_id = ""
            open_url = attachment.get("open", "")
            if "/items/" in open_url:
                att_id = open_url.rsplit("/items/", 1)[-1].split("?")[0]
            if not att_id and raw_annotations:
                att_id = raw_annotations[0].get("parentItem", "")

            # Normalize BBT annotations to match native API shape
            normalized = []
            for ann in raw_annotations:
                normalized.append(_normalize_bbt_annotation(ann, attachment))

            filename = os.path.basename(att_path)
            att_title = attachment.get("title") or filename or "Unknown"
            att_data = {
                "attachment_id": att_id,
                "attachment_title": att_title,
                "filename": filename,
                "path": att_path,
                "annotations_count": len(normalized),
                "annotations": normalized,
            }
            result["attachments"].append(att_data)

        return result


# Color mapping for Zotero's default annotation colors
COLOR_MAP = {
    "#ffd400": "Yellow",
    "#ff6666": "Red",
    "#5fb236": "Green",
    "#2ea8e5": "Blue",
    "#a28ae5": "Purple",
    "#e56eee": "Magenta",
    "#f19837": "Orange",
    "#aaaaaa": "Gray",
}


def get_color_category(hex_color: str) -> str:
    """Map hex annotation color to a category name."""
    return COLOR_MAP.get(hex_color.lower(), "") if hex_color else ""


def _normalize_bbt_annotation(annotation: Dict[str, Any], attachment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a BBT annotation into the same dict shape used by the native API path.

    The native Zotero API wraps annotation fields in a 'data' sub-dict with
    'annotationType', 'annotationText', etc. BBT returns them at the top level
    with the same field names. We wrap them so downstream formatters work
    identically regardless of source.
    """
    position = annotation.get("annotationPosition", {})
    if isinstance(position, str):
        try:
            position = json.loads(position)
        except (json.JSONDecodeError, TypeError):
            position = {}

    page_label = annotation.get("annotationPageLabel", "")
    sort_index = annotation.get("annotationSortIndex", "")

    # Build the 'data' wrapper matching native API shape
    data = {
        "key": annotation.get("key", ""),
        "itemType": "annotation",
        "annotationType": annotation.get("annotationType", "unknown"),
        "annotationText": annotation.get("annotationText", ""),
        "annotationComment": annotation.get("annotationComment", ""),
        "annotationColor": annotation.get("annotationColor", ""),
        "annotationPageLabel": page_label,
        "annotationSortIndex": sort_index,
        "annotationPosition": position,
        "tags": annotation.get("tags", []),
        "dateAdded": annotation.get("dateAdded", ""),
        "dateModified": annotation.get("dateModified", ""),
    }

    if annotation.get("annotationImagePath"):
        data["annotationImagePath"] = annotation["annotationImagePath"]

    return {
        "key": annotation.get("key", ""),
        "data": data,
    }
