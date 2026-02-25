"""Tests for the Playwright-based harvester."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from zotero_upload_url.config import (
    BrowserConfig,
    HarvestConfig,
    ProxyConfig,
    RetryConfig,
)
from zotero_upload_url.playwright_harvester import (
    HarvestError,
    HarvestErrorType,
    HarvestResult,
    BatchHarvestResult,
    PageLoadStrategy,
    RetryHandler,
    check_playwright_available,
    PAGE_READY_MARKERS,
)


class TestHarvestConfig:
    """Tests for harvest configuration."""

    def test_default_config(self):
        """Default config has sensible values."""
        config = HarvestConfig()
        assert config.browser.browser_type == "chromium"
        assert config.browser.headless is False
        assert config.retry.max_attempts == 3
        assert config.verify_saves is True

    def test_proxy_config_rewrite_url(self):
        """Proxy URL rewriting works correctly."""
        proxy = ProxyConfig(
            url_pattern="https://%h.proxy.example.com/%p",
            enabled=True,
        )

        # Basic URL rewrite
        result = proxy.rewrite_url("https://arxiv.org/abs/2301.00001")
        assert result == "https://arxiv.org.proxy.example.com/abs/2301.00001"

        # URL with query string
        result = proxy.rewrite_url("https://example.com/search?q=test")
        assert result == "https://example.com.proxy.example.com/search?q=test"

    def test_proxy_disabled_no_rewrite(self):
        """Disabled proxy doesn't rewrite URLs."""
        proxy = ProxyConfig(
            url_pattern="https://%h.proxy.example.com/%p",
            enabled=False,
        )

        result = proxy.rewrite_url("https://arxiv.org/abs/2301.00001")
        assert result == "https://arxiv.org/abs/2301.00001"


class TestRetryHandler:
    """Tests for retry logic."""

    def test_should_retry_recoverable_error(self):
        """Recoverable errors should be retried."""
        handler = RetryHandler(RetryConfig(max_attempts=3))
        error = HarvestError(
            error_type=HarvestErrorType.NETWORK,
            message="Connection timeout",
            recoverable=True,
        )

        assert handler.should_retry(error, attempt=1) is True
        assert handler.should_retry(error, attempt=2) is True
        assert handler.should_retry(error, attempt=3) is False  # Max reached

    def test_should_not_retry_fatal_error(self):
        """Non-recoverable errors should not be retried."""
        handler = RetryHandler(RetryConfig(max_attempts=3))
        error = HarvestError(
            error_type=HarvestErrorType.ZOTERO_NOT_RUNNING,
            message="Zotero not available",
            recoverable=False,
        )

        assert handler.should_retry(error, attempt=1) is False

    def test_exponential_backoff(self):
        """Retry delays use exponential backoff."""
        handler = RetryHandler(RetryConfig(
            initial_delay=1.0,
            backoff_factor=2.0,
            max_delay=30.0,
        ))

        assert handler.get_delay(1) == 1.0
        assert handler.get_delay(2) == 2.0
        assert handler.get_delay(3) == 4.0
        assert handler.get_delay(4) == 8.0

    def test_max_delay_capped(self):
        """Retry delay doesn't exceed max."""
        handler = RetryHandler(RetryConfig(
            initial_delay=1.0,
            backoff_factor=10.0,
            max_delay=30.0,
        ))

        assert handler.get_delay(5) == 30.0  # Capped at max


class TestHarvestResult:
    """Tests for harvest result data classes."""

    def test_harvest_result_success(self):
        """Successful harvest result."""
        result = HarvestResult(
            url="https://example.com",
            success=True,
            item_key="ABC123",
            title="Test Article",
            has_attachment=True,
        )

        assert result.success is True
        assert result.item_key == "ABC123"
        assert result.error is None

    def test_harvest_result_failure(self):
        """Failed harvest result."""
        result = HarvestResult(
            url="https://example.com",
            success=False,
            error=HarvestError(
                error_type=HarvestErrorType.TIMEOUT,
                message="Page load timeout",
            ),
        )

        assert result.success is False
        assert result.error.error_type == HarvestErrorType.TIMEOUT

    def test_batch_harvest_result_stats(self):
        """Batch result tracks statistics correctly."""
        batch = BatchHarvestResult(total=5)
        batch.succeeded = 3
        batch.failed = 2

        batch.results = [
            HarvestResult(url="http://a.com", success=True),
            HarvestResult(url="http://b.com", success=True),
            HarvestResult(url="http://c.com", success=True),
            HarvestResult(url="http://d.com", success=False),
            HarvestResult(url="http://e.com", success=False),
        ]

        assert batch.total == 5
        assert batch.succeeded == 3
        assert batch.failed == 2


class TestPageReadyMarkers:
    """Tests for page-specific content markers."""

    def test_arxiv_markers_defined(self):
        """arXiv has defined markers."""
        assert "arxiv.org" in PAGE_READY_MARKERS
        assert len(PAGE_READY_MARKERS["arxiv.org"]) > 0

    def test_doi_markers_defined(self):
        """DOI has defined markers."""
        assert "doi.org" in PAGE_READY_MARKERS

    def test_jstor_markers_defined(self):
        """JSTOR has defined markers."""
        assert "jstor.org" in PAGE_READY_MARKERS


class TestPageLoadStrategy:
    """Tests for page load detection strategy."""

    def test_extract_domain_simple(self):
        """Simple domain extraction."""
        # Create mock page
        mock_page = MagicMock()
        strategy = PageLoadStrategy(mock_page, timeout=5000)

        domain = strategy._extract_domain("https://arxiv.org/abs/2301.00001")
        assert domain == "arxiv.org"

    def test_extract_domain_with_www(self):
        """Domain extraction strips www prefix."""
        mock_page = MagicMock()
        strategy = PageLoadStrategy(mock_page, timeout=5000)

        domain = strategy._extract_domain("https://www.nature.com/articles/123")
        assert domain == "nature.com"

    def test_extract_domain_subdomain(self):
        """Subdomain matches parent domain markers."""
        mock_page = MagicMock()
        strategy = PageLoadStrategy(mock_page, timeout=5000)

        # export.arxiv.org should match arxiv.org
        domain = strategy._extract_domain("https://export.arxiv.org/abs/2301.00001")
        assert domain == "arxiv.org"


class TestHarvestErrorTypes:
    """Tests for error type classification."""

    def test_network_error_recoverable(self):
        """Network errors are typically recoverable."""
        error = HarvestError(
            error_type=HarvestErrorType.NETWORK,
            message="Connection refused",
            recoverable=True,
        )
        assert error.recoverable is True

    def test_timeout_error_recoverable(self):
        """Timeout errors are typically recoverable."""
        error = HarvestError(
            error_type=HarvestErrorType.TIMEOUT,
            message="Page load timeout",
            recoverable=True,
        )
        assert error.recoverable is True

    def test_extension_error_not_recoverable(self):
        """Extension not loaded is not recoverable."""
        error = HarvestError(
            error_type=HarvestErrorType.EXTENSION_NOT_LOADED,
            message="Zotero Connector not found",
            recoverable=False,
        )
        assert error.recoverable is False


class TestPlaywrightAvailability:
    """Tests for Playwright availability checking."""

    def test_check_playwright_available(self):
        """check_playwright_available returns boolean."""
        # This will return True if playwright is installed, False otherwise
        result = check_playwright_available()
        assert isinstance(result, bool)


class TestKeyboardShortcutParsing:
    """Tests for keyboard shortcut parsing (indirectly via config)."""

    def test_default_shortcut(self):
        """Default shortcut is ctrl+shift+s."""
        config = BrowserConfig()
        assert config.keyboard_shortcut == "ctrl+shift+s"

    def test_shortcut_string_format(self):
        """Shortcut string has expected format."""
        config = BrowserConfig(keyboard_shortcut="cmd+shift+z")
        parts = config.keyboard_shortcut.split("+")
        assert len(parts) == 3
        assert parts[-1] == "z"  # Key is last


class TestBatchHarvestResult:
    """Tests for batch harvest result aggregation."""

    def test_empty_batch(self):
        """Empty batch has zero counts."""
        batch = BatchHarvestResult()
        assert batch.total == 0
        assert batch.succeeded == 0
        assert batch.failed == 0
        assert batch.skipped == 0
        assert batch.results == []
        assert batch.errors == []

    def test_batch_with_mixed_results(self):
        """Batch correctly aggregates mixed results."""
        batch = BatchHarvestResult(total=3)

        success_result = HarvestResult(url="http://a.com", success=True)
        fail_result = HarvestResult(
            url="http://b.com",
            success=False,
            error=HarvestError(
                error_type=HarvestErrorType.TIMEOUT,
                message="timeout",
            ),
        )

        batch.results.append(success_result)
        batch.results.append(fail_result)
        batch.succeeded = 1
        batch.failed = 1
        batch.skipped = 1

        assert len(batch.results) == 2
        assert batch.succeeded + batch.failed + batch.skipped == batch.total

    def test_batch_elapsed_time(self):
        """Batch tracks elapsed time."""
        batch = BatchHarvestResult()
        batch.elapsed_time = 45.5
        assert batch.elapsed_time == 45.5
