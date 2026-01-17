# MWP Zotero Tools

A collection of tools for working with Zotero, including a Zotero 7 plugin, Python CLI tools, and Emacs Lisp integration.

## Packages

### [zotero-export-notes](./packages/zotero-export-notes/)

A Zotero 7 plugin that exports PDF annotations as org-mode files with org-pdftools style links.

**Features:**
- Export annotations from context menu
- HTTP API for external tool integration
- Collection management endpoints
- Better BibTeX integration for citekey lookup

### [zotero-cli](./packages/zotero-cli/)

Python CLI toolkit for interacting with Zotero's local API.

**Features:**
- Retrieve annotations from PDFs/EPUBs
- Export as org-mode or markdown
- Batch export attachments with markdown conversion
- Collection and library management

**Installation:**
```bash
uv tool install ./packages/zotero-cli
# Or with conversion support:
uv tool install ./packages/zotero-cli[convert]
```

### [zotero-upload-url](./packages/zotero-upload-url/)

macOS tool for saving URLs to Zotero via Firefox and the Zotero Connector.

**Features:**
- Save URLs with full metadata capture
- Interactive collection selection (with fzf support)
- Collection creation and management

**Installation:**
```bash
uv tool install ./packages/zotero-upload-url
```

### [zotero-elisp](./packages/zotero-elisp/)

Emacs Lisp integration for Zotero's local API.

**Features:**
- Retrieve and insert annotations in org-mode buffers
- Citation key resolution
- API parity with Python implementation

## API Overview

### Zotero Native API (port 23119)

Used by zotero-cli and zotero-upload-url for portable operations:

```
GET  /api/users/0/items              # Personal library items
GET  /api/users/0/collections        # Personal library collections
GET  /api/groups                     # List groups
GET  /api/groups/{id}/collections    # Group collections
```

### Export-Org Plugin API

Additional endpoints provided by zotero-export-notes:

```
POST /export-org/citekey             # Export by citation key
GET  /export-org/picker              # Get current Zotero selection
POST /export-org/collection/select   # Select collection in UI
POST /export-org/collection/create   # Create new collection
```

## Development

Each package can be developed independently:

```bash
# Zotero plugin
cd packages/zotero-export-notes
npm install
npm start

# Python packages
cd packages/zotero-cli
uv sync
uv run zotero-get-annots --help
```

## Documentation

- [API Comparison](./packages/zotero-export-notes/docs/comparison.md) - Detailed comparison of APIs and functionality

## License

MIT
