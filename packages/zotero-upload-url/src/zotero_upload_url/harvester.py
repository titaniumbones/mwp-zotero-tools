"""
Zotero Reference Harvester

Extract references (URLs, DOIs, arXiv IDs) from text and batch import to Zotero.

Usage:
    zotero-harvest --extract document.md           # Extract and show references
    cat output.txt | zotero-harvest --extract -    # Extract from stdin
    zotero-harvest --import document.md --collection KEY  # Import to collection
    zotero-harvest --import file.md --collection KEY --dry-run  # Preview only
"""

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, TextIO
from urllib.parse import urlparse

from .saver import (
    DEFAULT_ZOTERO_PORT,
    check_zotero_running,
    open_url_in_firefox,
    trigger_zotero_save,
)


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
    """Import references to Zotero in batch."""

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
      Import references to a specific Zotero collection

  %(prog)s --import file.md --collection KEY --dry-run
      Preview what would be imported without actually importing

  %(prog)s --import file.md --collection KEY --interactive
      Prompt before importing each reference

Reference types detected:
  - Plain URLs: https://example.com/article
  - Markdown links: [Title](https://example.com)
  - DOIs: doi:10.1038/nature12373 or https://doi.org/10.1038/nature12373
  - arXiv: arXiv:2301.00001 or https://arxiv.org/abs/2301.00001
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
        default=8.0,
        help="Seconds to wait between saves (default: 8)"
    )
    parser.add_argument(
        "--shortcut", "-s",
        default="option+cmd+s",
        help="Zotero Connector keyboard shortcut (default: option+cmd+s)"
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
