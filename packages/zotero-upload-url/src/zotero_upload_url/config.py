"""Configuration management for zotero-harvest.

Handles loading and saving configuration from ~/.zotero-harvest/config.toml
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

import tomli_w


CONFIG_DIR = Path.home() / ".zotero-harvest"
CONFIG_FILE = CONFIG_DIR / "config.toml"
PROFILES_DIR = CONFIG_DIR / "profiles"


@dataclass
class ProxyConfig:
    """University library proxy configuration."""

    login_url: str = ""
    url_pattern: str = ""
    enabled: bool = False

    def rewrite_url(self, url: str) -> str:
        """Rewrite a URL to go through the proxy.

        Pattern placeholders:
            %u - full original URL (URL-encoded)
            %h - original host
            %p - original path (including query string)
        """
        if not self.enabled or not self.url_pattern:
            return url

        from urllib.parse import urlparse, quote

        parsed = urlparse(url)
        host = parsed.netloc
        path = parsed.path
        if parsed.query:
            path = f"{path}?{parsed.query}"
        if parsed.fragment:
            path = f"{path}#{parsed.fragment}"

        # Remove leading slash from path for pattern substitution
        path_no_slash = path.lstrip("/")

        result = self.url_pattern
        result = result.replace("%u", quote(url, safe=""))
        result = result.replace("%h", host)
        result = result.replace("%p", path_no_slash)

        # Ensure we have a scheme
        if not result.startswith(("http://", "https://")):
            result = f"https://{result}"

        return result


@dataclass
class BrowserConfig:
    """Browser automation configuration."""

    browser_type: str = "chromium"
    headless: bool = False
    extension_path: str = ""
    default_profile: str = "default"
    page_load_timeout: int = 30000  # milliseconds
    save_timeout: int = 10000  # milliseconds
    keyboard_shortcut: str = "ctrl+shift+s"


@dataclass
class RetryConfig:
    """Retry behavior configuration."""

    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0


@dataclass
class HarvestConfig:
    """Complete harvest configuration."""

    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    verify_saves: bool = True
    delay_between_saves: float = 2.0  # seconds

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "HarvestConfig":
        """Load configuration from TOML file.

        Args:
            config_path: Path to config file. Defaults to ~/.zotero-harvest/config.toml

        Returns:
            HarvestConfig with values from file, or defaults if file doesn't exist
        """
        path = config_path or CONFIG_FILE
        if not path.exists():
            return cls()

        with open(path, "rb") as f:
            data = tomllib.load(f)

        config = cls()

        # Load proxy config
        if "proxy" in data:
            proxy_data = data["proxy"]
            config.proxy = ProxyConfig(
                login_url=proxy_data.get("login_url", ""),
                url_pattern=proxy_data.get("url_pattern", ""),
                enabled=proxy_data.get("enabled", False),
            )

        # Load browser config
        if "browser" in data:
            browser_data = data["browser"]
            config.browser = BrowserConfig(
                browser_type=browser_data.get("browser_type", "chromium"),
                headless=browser_data.get("headless", False),
                extension_path=browser_data.get("extension_path", ""),
                default_profile=browser_data.get("default_profile", "default"),
                page_load_timeout=browser_data.get("page_load_timeout", 30000),
                save_timeout=browser_data.get("save_timeout", 10000),
                keyboard_shortcut=browser_data.get("keyboard_shortcut", "ctrl+shift+s"),
            )

        # Load retry config
        if "retry" in data:
            retry_data = data["retry"]
            config.retry = RetryConfig(
                max_attempts=retry_data.get("max_attempts", 3),
                initial_delay=retry_data.get("initial_delay", 1.0),
                max_delay=retry_data.get("max_delay", 30.0),
                backoff_factor=retry_data.get("backoff_factor", 2.0),
            )

        # Load top-level settings
        config.verify_saves = data.get("verify_saves", True)
        config.delay_between_saves = data.get("delay_between_saves", 2.0)

        return config

    def save(self, config_path: Optional[Path] = None) -> None:
        """Save configuration to TOML file.

        Args:
            config_path: Path to config file. Defaults to ~/.zotero-harvest/config.toml
        """
        path = config_path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "verify_saves": self.verify_saves,
            "delay_between_saves": self.delay_between_saves,
            "proxy": {
                "login_url": self.proxy.login_url,
                "url_pattern": self.proxy.url_pattern,
                "enabled": self.proxy.enabled,
            },
            "browser": {
                "browser_type": self.browser.browser_type,
                "headless": self.browser.headless,
                "extension_path": self.browser.extension_path,
                "default_profile": self.browser.default_profile,
                "page_load_timeout": self.browser.page_load_timeout,
                "save_timeout": self.browser.save_timeout,
                "keyboard_shortcut": self.browser.keyboard_shortcut,
            },
            "retry": {
                "max_attempts": self.retry.max_attempts,
                "initial_delay": self.retry.initial_delay,
                "max_delay": self.retry.max_delay,
                "backoff_factor": self.retry.backoff_factor,
            },
        }

        with open(path, "wb") as f:
            tomli_w.dump(data, f)


def get_profile_path(profile_name: str = "default") -> Path:
    """Get the path to a browser profile directory.

    Args:
        profile_name: Name of the profile

    Returns:
        Path to the profile directory (creates if needed)
    """
    profile_path = PROFILES_DIR / profile_name
    profile_path.mkdir(parents=True, exist_ok=True)
    return profile_path


def ensure_config_dir() -> Path:
    """Ensure the config directory exists.

    Returns:
        Path to the config directory
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def create_default_config() -> HarvestConfig:
    """Create and save a default configuration file.

    Returns:
        The created HarvestConfig
    """
    config = HarvestConfig()
    # Set UofT proxy defaults as example
    config.proxy.login_url = "https://myaccess.library.utoronto.ca/login?qurl=%u"
    config.proxy.url_pattern = "https://%h.myaccess.library.utoronto.ca/%p"
    config.proxy.enabled = False  # Disabled by default
    config.save()
    return config
