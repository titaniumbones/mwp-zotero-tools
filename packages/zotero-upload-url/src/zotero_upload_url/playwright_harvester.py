"""Playwright-based browser automation for harvesting URLs to Zotero.

Replaces the macOS-only AppleScript approach with cross-platform
Playwright automation using Chromium with persistent browser context.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from .config import (
    BrowserConfig,
    HarvestConfig,
    ProxyConfig,
    RetryConfig,
    get_profile_path,
)
from .verification import VerificationResult, ZoteroVerificationService

try:
    from playwright.sync_api import (
        Browser,
        BrowserContext,
        Page,
        Playwright,
        sync_playwright,
    )

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class HarvestErrorType(Enum):
    """Types of harvest errors."""

    NETWORK = "network"
    TIMEOUT = "timeout"
    AUTH_REQUIRED = "auth_required"
    ZOTERO_NOT_RUNNING = "zotero_not_running"
    EXTENSION_NOT_LOADED = "extension_not_loaded"
    VERIFICATION_FAILED = "verification_failed"
    UNKNOWN = "unknown"


@dataclass
class HarvestError:
    """Details about a harvest error."""

    error_type: HarvestErrorType
    message: str
    recoverable: bool = True
    url: Optional[str] = None


@dataclass
class HarvestResult:
    """Result of a single URL harvest attempt."""

    url: str
    success: bool
    item_key: Optional[str] = None
    title: Optional[str] = None
    has_attachment: bool = False
    error: Optional[HarvestError] = None
    attempts: int = 1
    elapsed_time: float = 0.0


@dataclass
class BatchHarvestResult:
    """Result of a batch harvest operation."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[HarvestResult] = field(default_factory=list)
    errors: list[HarvestError] = field(default_factory=list)
    elapsed_time: float = 0.0


# Domain-specific content markers for page load detection
PAGE_READY_MARKERS = {
    "arxiv.org": ["abs-content", "download-pdf"],
    "doi.org": ["doi-info", "redirected"],
    "jstor.org": ["stable-pdf", "item-header"],
    "springer.com": ["c-article-title", "pdf-download"],
    "sciencedirect.com": ["article-content", "pdf-download"],
    "wiley.com": ["article__content", "pdf-link"],
    "nature.com": ["c-article-title", "pdf-download"],
    "pnas.org": ["article-content", "core-wave"],
    "pubmed.ncbi.nlm.nih.gov": ["abstract-content", "full-text-links"],
    "nih.gov": ["content-container", "document-title"],
    "acm.org": ["article-content", "pdf-download"],
    "ieee.org": ["document-title", "pdf-download"],
}


class PageLoadStrategy:
    """Strategy for detecting when a page is ready for saving."""

    def __init__(self, page: "Page", timeout: int = 30000):
        """Initialize the page load strategy.

        Args:
            page: Playwright page object
            timeout: Maximum wait time in milliseconds
        """
        self.page = page
        self.timeout = timeout

    def wait_for_ready(self, url: str) -> bool:
        """Wait for page to be ready for saving.

        Uses multiple strategies:
        1. Wait for network idle
        2. Check domain-specific content markers
        3. Detect authentication dialogs

        Args:
            url: The URL being loaded

        Returns:
            True if page is ready, False if auth required
        """
        try:
            # First, wait for network to settle
            self.page.wait_for_load_state("networkidle", timeout=self.timeout)

            # Check for domain-specific markers
            domain = self._extract_domain(url)
            if domain in PAGE_READY_MARKERS:
                for marker in PAGE_READY_MARKERS[domain]:
                    try:
                        # Wait briefly for marker to appear
                        self.page.wait_for_selector(
                            f".{marker}, #{marker}, [class*='{marker}']",
                            timeout=5000,
                        )
                        break
                    except Exception:
                        continue

            # Check for common authentication dialogs
            if self._detect_auth_dialog():
                return False

            return True

        except Exception:
            # Timeout or other error - page may still be usable
            return True

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for marker lookup."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Strip www. prefix
        if domain.startswith("www."):
            domain = domain[4:]

        # Match partial domains (e.g., 'arxiv.org' matches 'export.arxiv.org')
        for known_domain in PAGE_READY_MARKERS:
            if known_domain in domain:
                return known_domain

        return domain

    def _detect_auth_dialog(self) -> bool:
        """Detect if an authentication dialog is present."""
        auth_indicators = [
            'input[type="password"]',
            'form[action*="login"]',
            'form[action*="auth"]',
            ".login-form",
            "#login-form",
            "[class*='login']",
            "[class*='auth']",
        ]

        for selector in auth_indicators:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    return True
            except Exception:
                continue

        return False


class RetryHandler:
    """Handles retry logic with exponential backoff."""

    def __init__(self, config: RetryConfig):
        """Initialize retry handler.

        Args:
            config: Retry configuration
        """
        self.config = config

    def should_retry(self, error: HarvestError, attempt: int) -> bool:
        """Determine if operation should be retried.

        Args:
            error: The error that occurred
            attempt: Current attempt number (1-based)

        Returns:
            True if should retry
        """
        if attempt >= self.config.max_attempts:
            return False

        return error.recoverable

    def get_delay(self, attempt: int) -> float:
        """Calculate delay before next retry.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        delay = self.config.initial_delay * (self.config.backoff_factor ** (attempt - 1))
        return min(delay, self.config.max_delay)


class PlaywrightHarvester:
    """Playwright-based browser automation for Zotero URL harvesting."""

    def __init__(
        self,
        config: Optional[HarvestConfig] = None,
        verification_service: Optional[ZoteroVerificationService] = None,
    ):
        """Initialize the harvester.

        Args:
            config: Harvest configuration
            verification_service: Service for verifying saves
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Install with: uv add playwright && playwright install chromium"
            )

        self.config = config or HarvestConfig()
        self.verifier = verification_service or ZoteroVerificationService()
        self.retry_handler = RetryHandler(self.config.retry)

        self._playwright: Optional["Playwright"] = None
        self._browser: Optional["Browser"] = None
        self._context: Optional["BrowserContext"] = None
        self._page: Optional["Page"] = None

    def start(self, profile_name: Optional[str] = None) -> None:
        """Start the browser with persistent context.

        Args:
            profile_name: Browser profile to use (default from config)
        """
        profile = profile_name or self.config.browser.default_profile
        profile_path = get_profile_path(profile)

        self._playwright = sync_playwright().start()

        # Build browser launch arguments
        args = [
            "--disable-blink-features=AutomationControlled",
        ]

        # Add extension if configured
        extension_path = self.config.browser.extension_path
        if extension_path and Path(extension_path).exists():
            args.extend([
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
            ])

        # Launch with persistent context
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            headless=self.config.browser.headless,
            args=args,
            viewport={"width": 1280, "height": 900},
        )

        # Use the first page or create one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()

    def stop(self) -> None:
        """Stop the browser and cleanup resources."""
        if self._context:
            self._context.close()
            self._context = None

        if self._playwright:
            self._playwright.stop()
            self._playwright = None

        self._page = None

    def preflight_proxy_auth(
        self,
        proxy_url: Optional[str] = None,
        timeout: int = 120000,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Navigate to proxy login and wait for authentication.

        Args:
            proxy_url: Proxy login URL (default from config)
            timeout: Maximum time to wait for auth
            progress_callback: Optional callback for progress updates

        Returns:
            True if authenticated successfully
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        url = proxy_url or self.config.proxy.login_url
        if not url:
            return True  # No proxy configured

        if progress_callback:
            progress_callback(f"Navigating to proxy login: {url}")

        # Navigate to proxy login
        self._page.goto(url, wait_until="networkidle")

        if progress_callback:
            progress_callback(
                "Waiting for authentication. Please log in to the proxy service..."
            )

        # Wait for user to authenticate
        # We detect successful auth by watching for redirect away from login page
        start_time = time.time()
        initial_url = self._page.url

        while time.time() - start_time < timeout / 1000:
            current_url = self._page.url

            # Check if we've navigated away from login page
            if "login" not in current_url.lower() and current_url != initial_url:
                if progress_callback:
                    progress_callback("Proxy authentication successful!")
                return True

            # Also check for success indicators on the page
            try:
                success_indicators = [
                    "text=logged in",
                    "text=welcome",
                    "text=authenticated",
                    ".logout",
                    "[href*='logout']",
                ]
                for indicator in success_indicators:
                    if self._page.query_selector(indicator):
                        if progress_callback:
                            progress_callback("Proxy authentication successful!")
                        return True
            except Exception:
                pass

            time.sleep(1)

        return False

    def harvest_url(
        self,
        url: str,
        collection_key: Optional[str] = None,
        verify: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> HarvestResult:
        """Harvest a single URL to Zotero.

        Args:
            url: URL to save
            collection_key: Target collection key
            verify: Whether to verify the save
            progress_callback: Optional callback for progress updates

        Returns:
            HarvestResult with success/failure details
        """
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        start_time = time.time()
        attempt = 0
        last_error: Optional[HarvestError] = None

        # Optionally rewrite URL through proxy
        save_url = url
        if self.config.proxy.enabled:
            save_url = self.config.proxy.rewrite_url(url)

        while attempt < self.config.retry.max_attempts:
            attempt += 1

            if progress_callback:
                if attempt > 1:
                    progress_callback(f"Attempt {attempt}/{self.config.retry.max_attempts}: {url}")
                else:
                    progress_callback(f"Loading: {url}")

            try:
                result = self._do_harvest(
                    save_url,
                    original_url=url,
                    collection_key=collection_key,
                    verify=verify,
                    progress_callback=progress_callback,
                )

                if result.success:
                    result.attempts = attempt
                    result.elapsed_time = time.time() - start_time
                    return result

                # If we have an error, check if we should retry
                if result.error:
                    last_error = result.error
                    if self.retry_handler.should_retry(result.error, attempt):
                        delay = self.retry_handler.get_delay(attempt)
                        if progress_callback:
                            progress_callback(f"Retrying in {delay:.1f}s...")
                        time.sleep(delay)
                        continue

                # Non-recoverable error or max retries reached
                result.attempts = attempt
                result.elapsed_time = time.time() - start_time
                return result

            except Exception as e:
                last_error = HarvestError(
                    error_type=HarvestErrorType.UNKNOWN,
                    message=str(e),
                    recoverable=False,
                    url=url,
                )

        # All retries exhausted
        return HarvestResult(
            url=url,
            success=False,
            error=last_error,
            attempts=attempt,
            elapsed_time=time.time() - start_time,
        )

    def _do_harvest(
        self,
        url: str,
        original_url: str,
        collection_key: Optional[str],
        verify: bool,
        progress_callback: Optional[Callable[[str], None]],
    ) -> HarvestResult:
        """Internal method to perform a single harvest attempt."""
        assert self._page is not None

        try:
            # Navigate to URL
            response = self._page.goto(url, wait_until="domcontentloaded")

            if response and response.status >= 400:
                return HarvestResult(
                    url=original_url,
                    success=False,
                    error=HarvestError(
                        error_type=HarvestErrorType.NETWORK,
                        message=f"HTTP {response.status}",
                        recoverable=response.status >= 500,
                        url=original_url,
                    ),
                )

            # Wait for page to be ready
            strategy = PageLoadStrategy(self._page, self.config.browser.page_load_timeout)
            ready = strategy.wait_for_ready(url)

            if not ready:
                # Auth required - this is a special case
                if progress_callback:
                    progress_callback("Authentication required. Please log in...")

                # Wait for user to authenticate (up to 2 minutes)
                time.sleep(5)  # Give user time to notice
                strategy.wait_for_ready(url)  # Try again

            # Trigger Zotero save via keyboard shortcut
            if progress_callback:
                progress_callback("Triggering Zotero save...")

            self._trigger_save()

            # Verify the save if requested
            if verify:
                verification = self.verifier.verify_save(
                    original_url,
                    timeout=self.config.browser.save_timeout / 1000,
                    collection_key=collection_key,
                    progress_callback=progress_callback,
                )

                if verification.found:
                    return HarvestResult(
                        url=original_url,
                        success=True,
                        item_key=verification.item_key,
                        title=verification.title,
                        has_attachment=verification.has_attachment,
                    )
                else:
                    return HarvestResult(
                        url=original_url,
                        success=False,
                        error=HarvestError(
                            error_type=HarvestErrorType.VERIFICATION_FAILED,
                            message=verification.error or "Item not found",
                            recoverable=True,
                            url=original_url,
                        ),
                    )
            else:
                # No verification - assume success
                return HarvestResult(
                    url=original_url,
                    success=True,
                )

        except Exception as e:
            error_type = HarvestErrorType.UNKNOWN
            recoverable = True

            error_str = str(e).lower()
            if "timeout" in error_str:
                error_type = HarvestErrorType.TIMEOUT
            elif "net::" in error_str or "network" in error_str:
                error_type = HarvestErrorType.NETWORK

            return HarvestResult(
                url=original_url,
                success=False,
                error=HarvestError(
                    error_type=error_type,
                    message=str(e),
                    recoverable=recoverable,
                    url=original_url,
                ),
            )

    def _trigger_save(self) -> None:
        """Trigger Zotero save via keyboard shortcut."""
        assert self._page is not None

        shortcut = self.config.browser.keyboard_shortcut.lower()
        modifiers = []

        # Parse the shortcut string (e.g., "ctrl+shift+s")
        parts = shortcut.split("+")
        key = parts[-1]

        for part in parts[:-1]:
            if part in ("ctrl", "control"):
                modifiers.append("Control")
            elif part in ("shift",):
                modifiers.append("Shift")
            elif part in ("alt", "option"):
                modifiers.append("Alt")
            elif part in ("cmd", "meta", "command"):
                modifiers.append("Meta")

        # Press modifier keys
        for mod in modifiers:
            self._page.keyboard.down(mod)

        # Press the main key
        self._page.keyboard.press(key)

        # Release modifier keys
        for mod in reversed(modifiers):
            self._page.keyboard.up(mod)

        # Brief pause to let extension process
        time.sleep(0.5)

    def harvest_batch(
        self,
        urls: list[str],
        collection_key: Optional[str] = None,
        verify: bool = True,
        progress_callback: Optional[Callable[[int, int, str, Optional[HarvestResult]], None]] = None,
    ) -> BatchHarvestResult:
        """Harvest a batch of URLs to Zotero.

        Args:
            urls: List of URLs to save
            collection_key: Target collection key
            verify: Whether to verify each save
            progress_callback: Callback(current, total, url, result) for progress

        Returns:
            BatchHarvestResult with overall statistics
        """
        start_time = time.time()
        batch_result = BatchHarvestResult(total=len(urls))

        def url_progress(message: str) -> None:
            """Adapter for single-URL progress callback."""
            if progress_callback:
                progress_callback(
                    batch_result.succeeded + batch_result.failed + 1,
                    batch_result.total,
                    message,
                    None,
                )

        for i, url in enumerate(urls):
            result = self.harvest_url(
                url,
                collection_key=collection_key,
                verify=verify,
                progress_callback=url_progress,
            )

            batch_result.results.append(result)

            if result.success:
                batch_result.succeeded += 1
            else:
                batch_result.failed += 1
                if result.error:
                    batch_result.errors.append(result.error)

            # Notify progress
            if progress_callback:
                progress_callback(i + 1, len(urls), url, result)

            # Delay between saves (except for last one)
            if i < len(urls) - 1:
                time.sleep(self.config.delay_between_saves)

        batch_result.elapsed_time = time.time() - start_time
        return batch_result

    def __enter__(self) -> "PlaywrightHarvester":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop()


def check_playwright_available() -> bool:
    """Check if Playwright is available and configured.

    Returns:
        True if Playwright can be used
    """
    return PLAYWRIGHT_AVAILABLE
