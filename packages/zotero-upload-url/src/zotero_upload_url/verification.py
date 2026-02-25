"""Zotero save verification service.

Provides functions to verify that items have been saved to Zotero
by polling the Zotero API.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import requests

ZOTERO_API_BASE = "http://localhost:23119/api/users/0"


@dataclass
class VerificationResult:
    """Result of a save verification attempt."""

    found: bool
    item_key: Optional[str] = None
    item_type: Optional[str] = None
    title: Optional[str] = None
    has_attachment: bool = False
    attachment_type: Optional[str] = None
    error: Optional[str] = None


class ZoteroVerificationService:
    """Service for verifying items were saved to Zotero."""

    def __init__(
        self,
        base_url: str = ZOTERO_API_BASE,
        timeout: float = 5.0,
    ):
        """Initialize the verification service.

        Args:
            base_url: Base URL for Zotero API (default: local API)
            timeout: HTTP request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def get_item_count(self, collection_key: Optional[str] = None) -> int:
        """Get the current item count in library or collection.

        Args:
            collection_key: Optional collection key to count items in

        Returns:
            Number of items
        """
        if collection_key:
            url = f"{self.base_url}/collections/{collection_key}/items"
        else:
            url = f"{self.base_url}/items"

        try:
            resp = self._session.get(
                url,
                params={"limit": 0},  # Just get count from headers
                timeout=self.timeout,
            )
            resp.raise_for_status()
            # Zotero returns total count in Total-Results header
            return int(resp.headers.get("Total-Results", 0))
        except requests.RequestException:
            return 0

    def get_recent_items(
        self,
        limit: int = 10,
        collection_key: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get recently added items.

        Args:
            limit: Maximum number of items to return
            collection_key: Optional collection key to filter by

        Returns:
            List of item data dictionaries
        """
        if collection_key:
            url = f"{self.base_url}/collections/{collection_key}/items"
        else:
            url = f"{self.base_url}/items"

        try:
            resp = self._session.get(
                url,
                params={
                    "limit": limit,
                    "sort": "dateAdded",
                    "direction": "desc",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return []

    def find_item_by_url(
        self,
        url: str,
        since: Optional[datetime] = None,
        collection_key: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Find an item by its URL.

        Args:
            url: URL to search for
            since: Only consider items added after this time
            collection_key: Optional collection key to search in

        Returns:
            Item data if found, None otherwise
        """
        # Get recent items to search through
        items = self.get_recent_items(limit=25, collection_key=collection_key)

        # Normalize the search URL
        search_url = self._normalize_url(url)

        for item in items:
            data = item.get("data", {})

            # Check dateAdded if since is specified
            if since:
                date_added_str = data.get("dateAdded", "")
                if date_added_str:
                    try:
                        # Zotero uses ISO format: 2024-01-15T10:30:00Z
                        date_added = datetime.fromisoformat(
                            date_added_str.replace("Z", "+00:00")
                        )
                        if date_added < since:
                            continue  # Skip items added before our save attempt
                    except ValueError:
                        pass

            # Check the URL field
            item_url = data.get("url", "")
            if item_url and self._urls_match(search_url, item_url):
                return item

            # Also check DOI if present
            item_doi = data.get("DOI", "")
            if item_doi and item_doi in url:
                return item

        return None

    def verify_attachment_downloaded(
        self,
        item_key: str,
        timeout: float = 30.0,
        poll_interval: float = 1.0,
    ) -> bool:
        """Verify that an attachment (PDF) has been downloaded for an item.

        Args:
            item_key: Key of the parent item
            timeout: Maximum time to wait for attachment
            poll_interval: Time between checks

        Returns:
            True if attachment found, False otherwise
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            children = self._get_item_children(item_key)

            for child in children:
                child_data = child.get("data", {})
                item_type = child_data.get("itemType", "")

                # Check for PDF attachment
                if item_type == "attachment":
                    content_type = child_data.get("contentType", "")
                    link_mode = child_data.get("linkMode", "")

                    # Imported file or linked URL with PDF content
                    if content_type == "application/pdf":
                        return True

                    # Also accept HTML snapshots
                    if link_mode == "imported_url":
                        return True

            time.sleep(poll_interval)

        return False

    def verify_save(
        self,
        url: str,
        timeout: float = 15.0,
        poll_interval: float = 1.0,
        check_attachment: bool = True,
        collection_key: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> VerificationResult:
        """Verify that a URL was saved to Zotero.

        Polls the Zotero API until the item is found or timeout.

        Args:
            url: URL that was saved
            timeout: Maximum time to wait for item to appear
            poll_interval: Time between API checks
            check_attachment: Whether to verify attachment download
            collection_key: Optional collection to search in
            progress_callback: Optional callback for progress updates

        Returns:
            VerificationResult with success/failure details
        """
        start_time = time.time()
        since = datetime.now(timezone.utc)

        if progress_callback:
            progress_callback(f"Waiting for item to appear in Zotero...")

        while time.time() - start_time < timeout:
            item = self.find_item_by_url(url, since=since, collection_key=collection_key)

            if item:
                data = item.get("data", {})
                # key is at top level of item, not in data
                item_key = item.get("key", "") or data.get("key", "")

                result = VerificationResult(
                    found=True,
                    item_key=item_key,
                    item_type=data.get("itemType"),
                    title=data.get("title"),
                )

                if check_attachment and item_key:
                    if progress_callback:
                        progress_callback("Item found, checking for attachment...")

                    remaining_time = timeout - (time.time() - start_time)
                    if remaining_time > 0:
                        result.has_attachment = self.verify_attachment_downloaded(
                            item_key,
                            timeout=min(remaining_time, 15.0),
                            poll_interval=poll_interval,
                        )
                        if result.has_attachment:
                            result.attachment_type = "PDF"

                return result

            time.sleep(poll_interval)

        return VerificationResult(
            found=False,
            error=f"Item not found within {timeout}s timeout",
        )

    def _get_item_children(self, item_key: str) -> list[dict[str, Any]]:
        """Get child items (attachments, notes) for an item.

        Args:
            item_key: Parent item key

        Returns:
            List of child item data
        """
        url = f"{self.base_url}/items/{item_key}/children"
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return []

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL for comparison.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL
        """
        parsed = urlparse(url)
        # Remove common tracking parameters
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}".lower()

    def _urls_match(self, url1: str, url2: str) -> bool:
        """Check if two URLs match (accounting for variations).

        Args:
            url1: First URL
            url2: Second URL

        Returns:
            True if URLs match
        """
        norm1 = self._normalize_url(url1)
        norm2 = self._normalize_url(url2)

        if norm1 == norm2:
            return True

        # Check if one contains the other (for proxy URLs)
        parsed1 = urlparse(url1)
        parsed2 = urlparse(url2)

        # Same path on possibly different hosts (proxy case)
        # Only match if one host is a subdomain/proxy variation of the other
        if parsed1.path == parsed2.path and parsed1.path:
            host1 = parsed1.netloc.lower()
            host2 = parsed2.netloc.lower()
            # Check if one host contains the other (proxy rewriting case)
            # e.g., "arxiv.org" in "arxiv.org.proxy.library.edu"
            if host1 in host2 or host2 in host1:
                return True

        return False

    def check_zotero_running(self) -> bool:
        """Check if Zotero is running and accessible.

        Returns:
            True if Zotero API is accessible
        """
        try:
            resp = self._session.get(
                f"{self.base_url}/items",
                params={"limit": 1},
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
