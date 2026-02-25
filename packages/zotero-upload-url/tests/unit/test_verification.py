"""Tests for the Zotero verification service."""

import pytest
import responses
from datetime import datetime, timezone

from zotero_upload_url.verification import (
    VerificationResult,
    ZoteroVerificationService,
    ZOTERO_API_BASE,
)


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_successful_result(self):
        """Successful verification result."""
        result = VerificationResult(
            found=True,
            item_key="ABC123",
            item_type="journalArticle",
            title="Test Article",
            has_attachment=True,
            attachment_type="PDF",
        )

        assert result.found is True
        assert result.item_key == "ABC123"
        assert result.error is None

    def test_failed_result(self):
        """Failed verification result."""
        result = VerificationResult(
            found=False,
            error="Item not found within 15s timeout",
        )

        assert result.found is False
        assert result.item_key is None
        assert result.error is not None


class TestUrlNormalization:
    """Tests for URL normalization and matching."""

    def test_normalize_url_basic(self):
        """Basic URL normalization."""
        service = ZoteroVerificationService()

        normalized = service._normalize_url("https://Example.Com/path/")
        assert normalized == "https://example.com/path"

    def test_normalize_url_with_trailing_slash(self):
        """Trailing slash is removed."""
        service = ZoteroVerificationService()

        normalized = service._normalize_url("https://example.com/article/")
        assert normalized == "https://example.com/article"

    def test_urls_match_identical(self):
        """Identical URLs match."""
        service = ZoteroVerificationService()

        assert service._urls_match(
            "https://example.com/article",
            "https://example.com/article",
        ) is True

    def test_urls_match_case_insensitive(self):
        """URL matching is case-insensitive for host."""
        service = ZoteroVerificationService()

        assert service._urls_match(
            "https://EXAMPLE.COM/article",
            "https://example.com/article",
        ) is True

    def test_urls_match_same_path_different_host(self):
        """Same path on different hosts (proxy case) matches."""
        service = ZoteroVerificationService()

        # This handles proxy URLs where host changes but path stays same
        assert service._urls_match(
            "https://arxiv.org/abs/2301.00001",
            "https://arxiv.org.proxy.library.edu/abs/2301.00001",
        ) is True


class TestZoteroVerificationService:
    """Tests for ZoteroVerificationService API calls."""

    @responses.activate
    def test_get_item_count(self):
        """get_item_count returns count from header."""
        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=[],
            headers={"Total-Results": "42"},
        )

        service = ZoteroVerificationService()
        count = service.get_item_count()

        assert count == 42

    @responses.activate
    def test_get_item_count_collection(self):
        """get_item_count with collection key."""
        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/collections/ABC123/items",
            json=[],
            headers={"Total-Results": "10"},
        )

        service = ZoteroVerificationService()
        count = service.get_item_count(collection_key="ABC123")

        assert count == 10

    @responses.activate
    def test_get_item_count_error(self):
        """get_item_count returns 0 on error."""
        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            status=500,
        )

        service = ZoteroVerificationService()
        count = service.get_item_count()

        assert count == 0

    @responses.activate
    def test_get_recent_items(self):
        """get_recent_items returns items sorted by dateAdded."""
        items = [
            {"key": "A", "data": {"title": "Article A", "dateAdded": "2024-01-02T00:00:00Z"}},
            {"key": "B", "data": {"title": "Article B", "dateAdded": "2024-01-01T00:00:00Z"}},
        ]

        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=items,
        )

        service = ZoteroVerificationService()
        result = service.get_recent_items(limit=5)

        assert len(result) == 2
        assert result[0]["key"] == "A"

    @responses.activate
    def test_find_item_by_url_found(self):
        """find_item_by_url returns item when URL matches."""
        items = [
            {
                "key": "FOUND123",
                "data": {
                    "title": "Test Article",
                    "url": "https://example.com/article",
                    "dateAdded": "2024-01-15T10:00:00Z",
                },
            },
        ]

        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=items,
        )

        service = ZoteroVerificationService()
        result = service.find_item_by_url("https://example.com/article")

        assert result is not None
        assert result["key"] == "FOUND123"

    @responses.activate
    def test_find_item_by_url_not_found(self):
        """find_item_by_url returns None when no match."""
        items = [
            {
                "key": "OTHER",
                "data": {
                    "title": "Other Article",
                    "url": "https://other.com/article",
                    "dateAdded": "2024-01-15T10:00:00Z",
                },
            },
        ]

        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=items,
        )

        service = ZoteroVerificationService()
        result = service.find_item_by_url("https://example.com/article")

        assert result is None

    @responses.activate
    def test_find_item_by_url_with_since_filter(self):
        """find_item_by_url filters by since time."""
        items = [
            {
                "key": "OLD",
                "data": {
                    "title": "Old Article",
                    "url": "https://example.com/article",
                    "dateAdded": "2024-01-01T10:00:00Z",  # Before since
                },
            },
        ]

        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=items,
        )

        service = ZoteroVerificationService()
        since = datetime(2024, 1, 10, tzinfo=timezone.utc)
        result = service.find_item_by_url("https://example.com/article", since=since)

        assert result is None  # Filtered out by since

    @responses.activate
    def test_find_item_by_doi(self):
        """find_item_by_url matches DOI in URL."""
        items = [
            {
                "key": "DOI123",
                "data": {
                    "title": "DOI Article",
                    "url": "",
                    "DOI": "10.1234/test",
                    "dateAdded": "2024-01-15T10:00:00Z",
                },
            },
        ]

        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=items,
        )

        service = ZoteroVerificationService()
        result = service.find_item_by_url("https://doi.org/10.1234/test")

        assert result is not None
        assert result["key"] == "DOI123"

    @responses.activate
    def test_check_zotero_running_true(self):
        """check_zotero_running returns True when accessible."""
        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=[],
        )

        service = ZoteroVerificationService()
        assert service.check_zotero_running() is True

    @responses.activate
    def test_check_zotero_running_false(self):
        """check_zotero_running returns False on error."""
        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            status=500,
        )

        service = ZoteroVerificationService()
        assert service.check_zotero_running() is False

    @responses.activate
    def test_get_item_children(self):
        """_get_item_children returns child items."""
        children = [
            {
                "key": "ATTACH1",
                "data": {
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                },
            },
        ]

        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items/PARENT123/children",
            json=children,
        )

        service = ZoteroVerificationService()
        result = service._get_item_children("PARENT123")

        assert len(result) == 1
        assert result[0]["data"]["contentType"] == "application/pdf"


class TestVerificationPolling:
    """Tests for verification polling behavior."""

    @responses.activate
    def test_verify_save_found_immediately(self):
        """verify_save finds item on first poll."""
        # Use a future date so it passes the since filter
        future_date = "2099-01-15T10:00:00Z"
        items = [
            {
                "key": "NEW123",
                "data": {
                    "key": "NEW123",
                    "title": "New Article",
                    "url": "https://example.com/article",
                    "dateAdded": future_date,
                },
            },
        ]

        # First poll finds the item (may be called multiple times)
        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=items,
        )

        service = ZoteroVerificationService()
        result = service.verify_save(
            "https://example.com/article",
            timeout=1.0,
            poll_interval=0.1,
            check_attachment=False,
        )

        assert result.found is True
        assert result.item_key == "NEW123"

    @responses.activate
    def test_verify_save_with_attachment(self):
        """verify_save detects PDF attachment."""
        # Use a future date so it passes the since filter
        future_date = "2099-01-15T10:00:00Z"
        items = [
            {
                "key": "PDF123",
                "data": {
                    "key": "PDF123",
                    "title": "PDF Article",
                    "url": "https://example.com/article",
                    "dateAdded": future_date,
                },
            },
        ]

        children = [
            {
                "data": {
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "linkMode": "imported_file",
                },
            },
        ]

        # May be called multiple times during polling
        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=items,
        )

        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items/PDF123/children",
            json=children,
        )

        service = ZoteroVerificationService()
        result = service.verify_save(
            "https://example.com/article",
            timeout=2.0,
            poll_interval=0.1,
            check_attachment=True,
        )

        assert result.found is True
        assert result.has_attachment is True

    @responses.activate
    def test_verify_save_timeout(self):
        """verify_save returns not found on timeout."""
        # Return empty results
        responses.add(
            responses.GET,
            f"{ZOTERO_API_BASE}/items",
            json=[],
        )

        service = ZoteroVerificationService()
        result = service.verify_save(
            "https://example.com/nonexistent",
            timeout=0.5,
            poll_interval=0.1,
        )

        assert result.found is False
        assert "timeout" in result.error.lower()
