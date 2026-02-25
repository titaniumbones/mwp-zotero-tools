"""Tests for the configuration module."""

import pytest
import tempfile
from pathlib import Path

from zotero_upload_url.config import (
    BrowserConfig,
    HarvestConfig,
    ProxyConfig,
    RetryConfig,
    get_profile_path,
    ensure_config_dir,
)


class TestProxyConfig:
    """Tests for ProxyConfig."""

    def test_default_proxy_disabled(self):
        """Default proxy is disabled."""
        proxy = ProxyConfig()
        assert proxy.enabled is False
        assert proxy.login_url == ""
        assert proxy.url_pattern == ""

    def test_rewrite_url_disabled(self):
        """Disabled proxy returns original URL."""
        proxy = ProxyConfig(
            url_pattern="https://%h.proxy.edu/%p",
            enabled=False,
        )

        url = "https://example.com/article"
        assert proxy.rewrite_url(url) == url

    def test_rewrite_url_basic(self):
        """Basic URL rewriting works."""
        proxy = ProxyConfig(
            url_pattern="https://%h.proxy.edu/%p",
            enabled=True,
        )

        result = proxy.rewrite_url("https://arxiv.org/abs/2301.00001")
        assert result == "https://arxiv.org.proxy.edu/abs/2301.00001"

    def test_rewrite_url_with_query(self):
        """URL rewriting preserves query string."""
        proxy = ProxyConfig(
            url_pattern="https://%h.proxy.edu/%p",
            enabled=True,
        )

        result = proxy.rewrite_url("https://example.com/search?q=test&page=1")
        assert result == "https://example.com.proxy.edu/search?q=test&page=1"

    def test_rewrite_url_with_fragment(self):
        """URL rewriting preserves fragment."""
        proxy = ProxyConfig(
            url_pattern="https://%h.proxy.edu/%p",
            enabled=True,
        )

        result = proxy.rewrite_url("https://example.com/article#section1")
        assert result == "https://example.com.proxy.edu/article#section1"

    def test_rewrite_url_full_url_pattern(self):
        """URL rewriting with %u placeholder."""
        proxy = ProxyConfig(
            url_pattern="https://proxy.edu/login?url=%u",
            enabled=True,
        )

        result = proxy.rewrite_url("https://example.com/article")
        assert "https%3A%2F%2Fexample.com%2Farticle" in result


class TestBrowserConfig:
    """Tests for BrowserConfig."""

    def test_default_browser_config(self):
        """Default browser config has sensible values."""
        config = BrowserConfig()

        assert config.browser_type == "chromium"
        assert config.headless is False
        assert config.extension_path == ""
        assert config.default_profile == "default"
        assert config.page_load_timeout == 30000
        assert config.save_timeout == 10000
        assert config.keyboard_shortcut == "ctrl+shift+s"

    def test_custom_browser_config(self):
        """Custom browser config values."""
        config = BrowserConfig(
            browser_type="firefox",
            headless=True,
            keyboard_shortcut="cmd+shift+z",
        )

        assert config.browser_type == "firefox"
        assert config.headless is True
        assert config.keyboard_shortcut == "cmd+shift+z"


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_retry_config(self):
        """Default retry config has sensible values."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 30.0
        assert config.backoff_factor == 2.0

    def test_custom_retry_config(self):
        """Custom retry config values."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=60.0,
            backoff_factor=3.0,
        )

        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 60.0
        assert config.backoff_factor == 3.0


class TestHarvestConfig:
    """Tests for HarvestConfig."""

    def test_default_harvest_config(self):
        """Default harvest config has sensible values."""
        config = HarvestConfig()

        assert config.verify_saves is True
        assert config.delay_between_saves == 2.0
        assert isinstance(config.proxy, ProxyConfig)
        assert isinstance(config.browser, BrowserConfig)
        assert isinstance(config.retry, RetryConfig)

    def test_load_nonexistent_file(self):
        """Loading nonexistent config returns defaults."""
        config = HarvestConfig.load(Path("/nonexistent/config.toml"))

        assert config.verify_saves is True
        assert config.proxy.enabled is False

    def test_save_and_load_config(self):
        """Config can be saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            # Create custom config
            config = HarvestConfig()
            config.verify_saves = False
            config.delay_between_saves = 5.0
            config.proxy.login_url = "https://proxy.edu/login"
            config.proxy.enabled = True
            config.browser.headless = True
            config.retry.max_attempts = 5

            # Save it
            config.save(config_path)

            # Load it back
            loaded = HarvestConfig.load(config_path)

            assert loaded.verify_saves is False
            assert loaded.delay_between_saves == 5.0
            assert loaded.proxy.login_url == "https://proxy.edu/login"
            assert loaded.proxy.enabled is True
            assert loaded.browser.headless is True
            assert loaded.retry.max_attempts == 5


class TestProfilePaths:
    """Tests for profile path helpers."""

    def test_get_profile_path_creates_dir(self):
        """get_profile_path creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Monkeypatch PROFILES_DIR
            import zotero_upload_url.config as config_module
            original_dir = config_module.PROFILES_DIR
            config_module.PROFILES_DIR = Path(tmpdir) / "profiles"

            try:
                profile_path = get_profile_path("test-profile")
                assert profile_path.exists()
                assert profile_path.is_dir()
                assert profile_path.name == "test-profile"
            finally:
                config_module.PROFILES_DIR = original_dir

    def test_ensure_config_dir_creates(self):
        """ensure_config_dir creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import zotero_upload_url.config as config_module
            original_dir = config_module.CONFIG_DIR
            config_module.CONFIG_DIR = Path(tmpdir) / "zotero-harvest"

            try:
                result = ensure_config_dir()
                assert result.exists()
                assert result.is_dir()
            finally:
                config_module.CONFIG_DIR = original_dir
