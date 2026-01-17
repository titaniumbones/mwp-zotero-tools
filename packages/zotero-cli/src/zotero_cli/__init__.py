"""
Zotero CLI - Python toolkit for interacting with Zotero's local API.

Provides functionality for:
- Retrieving annotations from PDF/EPUB attachments
- Exporting annotations as org-mode or markdown
- Managing collections and libraries
- Batch export of attachments with markdown conversion
"""

from zotero_cli.api import ZoteroLocalAPI

__version__ = "0.1.0"
__all__ = ["ZoteroLocalAPI"]
