"""
Zotero Reference Harvester

Extract references (URLs, DOIs, arXiv IDs) from text and batch import to Zotero.

Usage:
    zotero-harvest --extract document.md           # Extract and show references
    cat output.txt | zotero-harvest --extract -    # Extract from stdin
    zotero-harvest --import document.md --collection KEY  # Import to collection
    zotero-harvest --import file.md --collection KEY --dry-run  # Preview only

Playwright-based harvesting (recommended):
    zotero-harvest --import doc.md --collection KEY --preflight-proxy
    zotero-harvest --import doc.md --collection KEY --proxy-urls --verify
"""

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, TextIO
from urllib.parse import urlparse

from .config import HarvestConfig, ensure_config_dir
from .saver import (
    DEFAULT_ZOTERO_PORT,
    check_zotero_running,
    open_url_in_firefox,
    trigger_zotero_save,
)
from .verification import ZoteroVerificationService


@dataclass
class ExtractedReference:
    """A reference extracted from text."""

    original_text: str
    ref_type: str  # 'url', 'doi', 'arxiv', 'markdown_link'
    url: str | None = None
    title: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None

    def get_save_url(self) -> str | None:
        """Get the URL to use for saving to Zotero."""
        if self.url:
            return self.url
        if self.doi:
            return f"https://doi.org/{self.doi}"
        if self.arxiv_id:
            return f"https://arxiv.org/abs/{self.arxiv_id}"
        return None

    def display_str(self) -> str:
        """Human-readable display string."""
        if self.title:
            return f"[{self.ref_type}] {self.title} ({self.get_save_url()})"
        return f"[{self.ref_type}] {self.get_save_url()}"


@dataclass
class BatchImportResult:
    """Result of a batch import operation."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[tuple[ExtractedReference, str]] = field(default_factory=list)


class ReferenceExtractor:
    """Extract references from text content."""

    # Regex patterns for reference extraction
    # URL pattern - matches http/https URLs
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"\')\]]+',
        re.IGNORECASE
    )

    # Markdown link pattern - [title](url)
    MARKDOWN_LINK_PATTERN = re.compile(
        r'\[([^\]]+)\]\((https?://[^)]+)\)',
        re.IGNORECASE
    )

    # DOI patterns
    # doi:10.xxx/yyy or https://doi.org/10.xxx/yyy
    DOI_PATTERN = re.compile(
        r'(?:doi[:\s]*|https?://(?:dx\.)?doi\.org/)(10\.\d{4,}/[^\s<>"\')\]]+)',
        re.IGNORECASE
    )

    # arXiv pattern - arXiv:YYMM.NNNNN or arxiv.org/abs/YYMM.NNNNN
    ARXIV_PATTERN = re.compile(
        r'(?:arXiv[:\s]*|https?://arxiv\.org/abs/)(\d{4}\.\d{4,5}(?:v\d+)?)',
        re.IGNORECASE
    )

    def extract_all(self, text: str) -> list[ExtractedReference]:
        """Extract all references from text, deduplicating by URL.

        Returns references in order of first appearance, with markdown links
        taking precedence (they include titles).
        """
        refs: dict[str, ExtractedReference] = {}

        # Extract markdown links first (they have titles)
        for ref in self.extract_markdown_links(text):
            url = ref.get_save_url()
            if url and url not in refs:
                refs[url] = ref

        # Extract DOIs
        for ref in self.extract_dois(text):
            url = ref.get_save_url()
            if url and url not in refs:
                refs[url] = ref

        # Extract arXiv IDs
        for ref in self.extract_arxiv(text):
            url = ref.get_save_url()
            if url and url not in refs:
                refs[url] = ref

        # Extract plain URLs last (markdown links already captured)
        for ref in self.extract_urls(text):
            url = ref.get_save_url()
            if url and url not in refs:
                refs[url] = ref

        return list(refs.values())

    def extract_urls(self, text: str) -> list[ExtractedReference]:
        """Extract plain URLs from text."""
        refs = []
        for match in self.URL_PATTERN.finditer(text):
            url = match.group(0)
            # Clean trailing punctuation that might have been captured
            url = url.rstrip('.,;:')
            refs.append(ExtractedReference(
                original_text=match.group(0),
                ref_type='url',
                url=url
            ))
        return refs

    def extract_markdown_links(self, text: str) -> list[ExtractedReference]:
        """Extract markdown links [title](url) from text."""
        refs = []
        for match in self.MARKDOWN_LINK_PATTERN.finditer(text):
            title = match.group(1)
            url = match.group(2)
            refs.append(ExtractedReference(
                original_text=match.group(0),
                ref_type='markdown_link',
                url=url,
                title=title
            ))
        return refs

    def extract_dois(self, text: str) -> list[ExtractedReference]:
        """Extract DOI references from text."""
        refs = []
        for match in self.DOI_PATTERN.finditer(text):
            doi = match.group(1)
            # Clean trailing punctuation
            doi = doi.rstrip('.,;:')
            refs.append(ExtractedReference(
                original_text=match.group(0),
                ref_type='doi',
                doi=doi,
                url=f"https://doi.org/{doi}"
            ))
        return refs

    def extract_arxiv(self, text: str) -> list[ExtractedReference]:
        """Extract arXiv references from text."""
        refs = []
        for match in self.ARXIV_PATTERN.finditer(text):
            arxiv_id = match.group(1)
            refs.append(ExtractedReference(
                original_text=match.group(0),
                ref_type='arxiv',
                arxiv_id=arxiv_id,
                url=f"https://arxiv.org/abs/{arxiv_id}"
            ))
        return refs


class BatchImporter:
    """Import references to Zotero in batch (legacy AppleScript method)."""

    def __init__(
        self,
        port: int = DEFAULT_ZOTERO_PORT,
        delay: float = 8.0,
        shortcut: str = "option+cmd+s"
    ):
        """Initialize the batch importer.

        Args:
            port: Zotero connector port
            delay: Seconds to wait between saves for Connector to process
            shortcut: Keyboard shortcut for Zotero Connector save
        """
        self.port = port
        self.delay = delay
        self.shortcut = shortcut

    def import_references(
        self,
        refs: list[ExtractedReference],
        dry_run: bool = False,
        interactive: bool = False,
        progress_callback: Callable[[int, int, ExtractedReference], None] | None = None
    ) -> BatchImportResult:
        """Import a list of references to Zotero.

        Args:
            refs: List of references to import
            dry_run: If True, only show what would be imported
            interactive: If True, prompt before each import
            progress_callback: Optional callback(current, total, ref) for progress

        Returns:
            BatchImportResult with success/failure counts
        """
        result = BatchImportResult(total=len(refs))

        if dry_run:
            print("Dry run - would import:")
            for i, ref in enumerate(refs, 1):
                print(f"  {i}. {ref.display_str()}")
            result.skipped = len(refs)
            return result

        for i, ref in enumerate(refs):
            url = ref.get_save_url()
            if not url:
                result.failed += 1
                result.errors.append((ref, "No URL available"))
                continue

            if progress_callback:
                progress_callback(i + 1, len(refs), ref)

            if interactive:
                response = input(f"Import {ref.display_str()}? [Y/n/q] ").strip().lower()
                if response == 'q':
                    result.skipped += len(refs) - i
                    break
                if response == 'n':
                    result.skipped += 1
                    continue

            try:
                self._save_url(url)
                result.succeeded += 1
            except Exception as e:
                result.failed += 1
                result.errors.append((ref, str(e)))

            # Wait between saves to let Zotero Connector process
            if i < len(refs) - 1:
                time.sleep(self.delay)

        return result

    def _save_url(self, url: str) -> None:
        """Save a single URL to Zotero.

        Uses the existing saver functions.
        """
        # Open URL in Firefox
        open_url_in_firefox(url)

        # Wait for page to load
        time.sleep(3)

        # Trigger Zotero save
        trigger_zotero_save(self.shortcut)


class PlaywrightBatchImporter:
    """Import references to Zotero using Playwright browser automation."""

    def __init__(
        self,
        config: Optional[HarvestConfig] = None,
        profile: str = "default",
        preflight_proxy: bool = False,
        verify: bool = True,
    ):
        """Initialize the Playwright batch importer.

        Args:
            config: Harvest configuration
            profile: Browser profile name
            preflight_proxy: Whether to authenticate to proxy first
            verify: Whether to verify saves via Zotero API
        """
        self.config = config or HarvestConfig.load()
        self.profile = profile
        self.preflight_proxy = preflight_proxy
        self.verify = verify
        self._harvester = None

    def import_references(
        self,
        refs: list[ExtractedReference],
        collection_key: Optional[str] = None,
        dry_run: bool = False,
        interactive: bool = False,
        progress_callback: Callable[[int, int, ExtractedReference], None] | None = None
    ) -> BatchImportResult:
        """Import a list of references to Zotero using Playwright.

        Args:
            refs: List of references to import
            collection_key: Target collection key
            dry_run: If True, only show what would be imported
            interactive: If True, prompt before each import
            progress_callback: Optional callback(current, total, ref) for progress

        Returns:
            BatchImportResult with success/failure counts
        """
        from .playwright_harvester import PlaywrightHarvester, check_playwright_available

        if not check_playwright_available():
            raise ImportError(
                "Playwright is not available. Install with: "
                "uv add playwright && playwright install chromium"
            )

        result = BatchImportResult(total=len(refs))

        if dry_run:
            print("Dry run - would import:")
            for i, ref in enumerate(refs, 1):
                proxy_note = ""
                if self.config.proxy.enabled:
                    url = ref.get_save_url()
                    if url:
                        proxied = self.config.proxy.rewrite_url(url)
                        if proxied != url:
                            proxy_note = f" (via proxy)"
                print(f"  {i}. {ref.display_str()}{proxy_note}")
            result.skipped = len(refs)
            return result

        # Filter references interactively if needed
        refs_to_import = []
        if interactive:
            for ref in refs:
                response = input(f"Import {ref.display_str()}? [Y/n/q] ").strip().lower()
                if response == 'q':
                    result.skipped += len(refs) - len(refs_to_import)
                    break
                if response == 'n':
                    result.skipped += 1
                    continue
                refs_to_import.append(ref)
        else:
            refs_to_import = refs

        if not refs_to_import:
            return result

        # Start harvester
        harvester = PlaywrightHarvester(
            config=self.config,
            verification_service=ZoteroVerificationService(),
        )

        try:
            print("Starting browser...")
            harvester.start(profile_name=self.profile)

            # Handle proxy authentication if requested
            if self.preflight_proxy and self.config.proxy.login_url:
                print(f"Navigating to proxy login...")
                success = harvester.preflight_proxy_auth(
                    progress_callback=lambda msg: print(f"  {msg}")
                )
                if not success:
                    print("Warning: Proxy authentication may have failed. Continuing...")

            # Build URL list
            urls = []
            url_to_ref = {}
            for ref in refs_to_import:
                url = ref.get_save_url()
                if url:
                    urls.append(url)
                    url_to_ref[url] = ref

            # Progress adapter
            def batch_progress(current: int, total: int, url: str, harvest_result) -> None:
                ref = url_to_ref.get(url)
                if ref and progress_callback:
                    progress_callback(current, total, ref)

                if harvest_result:
                    if harvest_result.success:
                        status = "saved"
                        if harvest_result.has_attachment:
                            status += " (with PDF)"
                    else:
                        status = f"FAILED: {harvest_result.error.message if harvest_result.error else 'unknown'}"
                    print(f"  -> {status}")

            # Harvest all URLs
            batch_result = harvester.harvest_batch(
                urls,
                collection_key=collection_key,
                verify=self.verify,
                progress_callback=batch_progress,
            )

            # Map results back to references
            for harvest_result in batch_result.results:
                ref = url_to_ref.get(harvest_result.url)
                if harvest_result.success:
                    result.succeeded += 1
                else:
                    result.failed += 1
                    if ref and harvest_result.error:
                        result.errors.append((ref, harvest_result.error.message))

        finally:
            print("Closing browser...")
            harvester.stop()

        return result


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    parsed = urlparse(url)
    # Remove trailing slashes, lowercase host
    normalized = f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized


def read_input(source: str | TextIO) -> str:
    """Read input from file path or stdin."""
    if source == '-' or (hasattr(source, 'read') and source == sys.stdin):
        return sys.stdin.read()
    if hasattr(source, 'read'):
        return source.read()
    with open(source) as f:
        return f.read()


def main():
    parser = argparse.ArgumentParser(
        description="Extract and import references to Zotero",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --extract document.md
      Extract and display references from a markdown file

  cat llm_output.txt | %(prog)s --extract -
      Extract references from stdin (piped content)

  %(prog)s --import document.md --collection KEY
      Import references to a specific Zotero collection (uses Playwright)

  %(prog)s --import file.md --collection KEY --dry-run
      Preview what would be imported without actually importing

  %(prog)s --import file.md --collection KEY --interactive
      Prompt before importing each reference

  %(prog)s --import file.md --collection KEY --preflight-proxy
      Authenticate to university proxy before batch import

  %(prog)s --import file.md --collection KEY --proxy-urls
      Rewrite URLs through university proxy

  %(prog)s --import file.md --collection KEY --legacy
      Use legacy AppleScript method (macOS only)

Reference types detected:
  - Plain URLs: https://example.com/article
  - Markdown links: [Title](https://example.com)
  - DOIs: doi:10.1038/nature12373 or https://doi.org/10.1038/nature12373
  - arXiv: arXiv:2301.00001 or https://arxiv.org/abs/2301.00001

Configuration:
  Config file: ~/.zotero-harvest/config.toml
  Browser profiles: ~/.zotero-harvest/profiles/
        """
    )

    # Mode arguments (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--extract", "-e",
        metavar="FILE",
        help="Extract references from file (use '-' for stdin)"
    )
    mode_group.add_argument(
        "--import", "-i",
        dest="import_file",
        metavar="FILE",
        help="Import references from file to Zotero"
    )
    mode_group.add_argument(
        "--init-config",
        action="store_true",
        help="Create default config file at ~/.zotero-harvest/config.toml"
    )

    # Import options
    parser.add_argument(
        "--collection", "-c",
        metavar="KEY",
        help="Collection key to import into (required for --import)"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be imported without actually importing"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt before importing each reference"
    )

    # Playwright options
    parser.add_argument(
        "--profile",
        default="default",
        help="Browser profile name (default: 'default')"
    )
    parser.add_argument(
        "--preflight-proxy",
        action="store_true",
        help="Navigate to proxy login before batch import"
    )
    parser.add_argument(
        "--proxy-urls",
        action="store_true",
        help="Rewrite URLs through university proxy"
    )
    parser.add_argument(
        "--no-proxy-urls",
        dest="proxy_urls",
        action="store_false",
        help="Don't rewrite URLs through proxy"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify saves via Zotero API (default: enabled)"
    )
    parser.add_argument(
        "--no-verify",
        dest="verify",
        action="store_false",
        help="Skip save verification"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum retry attempts for failed saves (default: 2)"
    )
    parser.add_argument(
        "--extension-path",
        metavar="PATH",
        help="Path to unpacked Zotero Connector extension"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run browser with visible window (default)"
    )

    # Legacy options
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy AppleScript method (macOS only)"
    )

    # Common options
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_ZOTERO_PORT,
        help=f"Zotero connector port (default: {DEFAULT_ZOTERO_PORT})"
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=2.0,
        help="Seconds to wait between saves (default: 2)"
    )
    parser.add_argument(
        "--shortcut", "-s",
        default="ctrl+shift+s",
        help="Zotero Connector keyboard shortcut (default: ctrl+shift+s)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format (for --extract)"
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip checking if Zotero is running"
    )

    args = parser.parse_args()

    # Handle --init-config
    if args.init_config:
        from .config import create_default_config, CONFIG_FILE
        if CONFIG_FILE.exists():
            print(f"Config file already exists: {CONFIG_FILE}")
            response = input("Overwrite? [y/N] ").strip().lower()
            if response != 'y':
                print("Aborted.")
                return 0
        config = create_default_config()
        print(f"Created config file: {CONFIG_FILE}")
        print("\nDefault proxy settings (UofT Library):")
        print(f"  login_url: {config.proxy.login_url}")
        print(f"  url_pattern: {config.proxy.url_pattern}")
        print(f"  enabled: {config.proxy.enabled}")
        print("\nEdit the config file to customize settings.")
        return 0

    # Extract mode
    if args.extract:
        try:
            text = read_input(args.extract)
        except FileNotFoundError:
            print(f"Error: File not found: {args.extract}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error reading input: {e}", file=sys.stderr)
            return 1

        extractor = ReferenceExtractor()
        refs = extractor.extract_all(text)

        if args.json:
            import json
            output = [
                {
                    "type": ref.ref_type,
                    "url": ref.get_save_url(),
                    "title": ref.title,
                    "doi": ref.doi,
                    "arxiv_id": ref.arxiv_id,
                    "original_text": ref.original_text
                }
                for ref in refs
            ]
            print(json.dumps(output, indent=2))
        else:
            if not refs:
                print("No references found.")
            else:
                print(f"Found {len(refs)} reference(s):\n")
                for i, ref in enumerate(refs, 1):
                    print(f"  {i}. {ref.display_str()}")

        return 0

    # Import mode
    if args.import_file:
        # Validate requirements
        if not args.collection and not args.dry_run:
            print("Error: --collection is required for import (or use --dry-run)", file=sys.stderr)
            return 1

        # Check Zotero is running (unless dry-run)
        if not args.dry_run and not args.skip_check:
            if not check_zotero_running(args.port):
                print(f"Error: Zotero is not running on port {args.port}.", file=sys.stderr)
                print("Start Zotero or use --skip-check to bypass.", file=sys.stderr)
                return 1

        try:
            text = read_input(args.import_file)
        except FileNotFoundError:
            print(f"Error: File not found: {args.import_file}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error reading input: {e}", file=sys.stderr)
            return 1

        extractor = ReferenceExtractor()
        refs = extractor.extract_all(text)

        if not refs:
            print("No references found to import.")
            return 0

        print(f"Found {len(refs)} reference(s) to import.")
        if args.collection:
            print(f"Target collection: {args.collection}")
        print()

        def progress_callback(current: int, total: int, ref: ExtractedReference):
            print(f"[{current}/{total}] Importing: {ref.display_str()}")

        # Choose importer based on --legacy flag
        if args.legacy:
            # Legacy AppleScript method (macOS only)
            print("Using legacy AppleScript method...")
            importer = BatchImporter(
                port=args.port,
                delay=args.delay,
                shortcut=args.shortcut
            )

            result = importer.import_references(
                refs,
                dry_run=args.dry_run,
                interactive=args.interactive,
                progress_callback=None if args.dry_run else progress_callback
            )
        else:
            # Playwright method (cross-platform, recommended)
            try:
                from .playwright_harvester import check_playwright_available
                if not check_playwright_available():
                    raise ImportError("Playwright not available")
            except ImportError:
                print("Error: Playwright is not available.", file=sys.stderr)
                print("Install with: uv add playwright && playwright install chromium", file=sys.stderr)
                print("Or use --legacy for AppleScript method (macOS only).", file=sys.stderr)
                return 1

            # Load config and apply CLI overrides
            config = HarvestConfig.load()

            # Apply CLI arguments to config
            if args.proxy_urls:
                config.proxy.enabled = True
            if args.extension_path:
                config.browser.extension_path = args.extension_path
            if args.headless:
                config.browser.headless = True
            if args.shortcut:
                config.browser.keyboard_shortcut = args.shortcut
            if args.delay:
                config.delay_between_saves = args.delay
            if args.max_retries:
                config.retry.max_attempts = args.max_retries + 1  # +1 because first attempt isn't a retry

            print("Using Playwright browser automation...")
            importer = PlaywrightBatchImporter(
                config=config,
                profile=args.profile,
                preflight_proxy=args.preflight_proxy,
                verify=args.verify,
            )

            result = importer.import_references(
                refs,
                collection_key=args.collection,
                dry_run=args.dry_run,
                interactive=args.interactive,
                progress_callback=None if args.dry_run else progress_callback
            )

        # Print summary
        print()
        if args.dry_run:
            print(f"Dry run complete. {result.total} reference(s) would be imported.")
        else:
            print(f"Import complete:")
            print(f"  Succeeded: {result.succeeded}")
            if result.failed:
                print(f"  Failed: {result.failed}")
            if result.skipped:
                print(f"  Skipped: {result.skipped}")

            if result.errors:
                print("\nErrors:")
                for ref, error in result.errors:
                    print(f"  - {ref.display_str()}: {error}")

        return 0 if result.failed == 0 else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
