# MWP Zotero Tools - Development Guide

## Project Structure

```
mwp-zotero-tools/
├── packages/
│   ├── zotero-export-notes/    # Zotero 7 plugin (TypeScript)
│   ├── zotero-cli/             # Python CLI tools
│   ├── zotero-upload-url/      # URL saving tool (Python)
│   └── zotero-elisp/           # Emacs Lisp integration
└── docs/
```

## Package-Specific Development

### zotero-export-notes (Zotero 7 Plugin)

See [packages/zotero-export-notes/CLAUDE.md](./packages/zotero-export-notes/CLAUDE.md) for:
- Zotero 7 plugin architecture
- HTTP API endpoints
- Build and test commands

```bash
cd packages/zotero-export-notes
npm install
npm start           # Development with hot reload
npm run build       # Production build
```

### zotero-cli (Python)

See [packages/zotero-cli/CLAUDE.md](./packages/zotero-cli/CLAUDE.md) for:
- ZoteroLocalAPI class reference
- Annotation export examples
- Collection management

```bash
cd packages/zotero-cli
uv sync
uv run zotero-get-annots ITEM_KEY --org
```

### zotero-upload-url (Python)

```bash
cd packages/zotero-upload-url
uv sync
uv run zotero-save "https://example.com"
uv run zotero-collection --list
```

### zotero-elisp (Emacs Lisp)

Load in Emacs:
```elisp
(add-to-list 'load-path "/path/to/packages/zotero-elisp")
(require 'zotero-api)
(require 'org-zotero-client)
```

## API Architecture

### Native Zotero API (No plugin required)

All packages can use Zotero's built-in HTTP server (default port 23119):

```
GET  /api/users/0/items                    # Items
GET  /api/users/0/items/{key}/children     # Children (attachments, notes)
GET  /api/users/0/collections              # Collections
GET  /api/groups                           # Groups
GET  /api/groups/{id}/collections          # Group collections
```

### Plugin API (Requires zotero-export-notes)

Additional endpoints for UI integration and citekey lookup:

```
POST /export-org/citekey                   # Export by Better BibTeX key
GET  /export-org/picker                    # Current UI selection
POST /export-org/collection/select         # Select collection in UI
POST /export-org/collection/create         # Create collection
```

## Shared Code

The `ZoteroLocalAPI` class in `zotero-cli` is the reference implementation for:
- Making requests to Zotero's local API
- Parsing item and annotation data
- Formatting as org-mode or markdown

Consider extracting to a shared package if zotero-upload-url needs these capabilities.

## Testing

### Zotero Plugin
```bash
cd packages/zotero-export-notes
npm test
```

### Python
```bash
cd packages/zotero-cli
uv run pytest  # If tests are added
```

### Emacs Lisp
```bash
cd packages/zotero-elisp/test
emacs --batch -l run-tests.el
```

## Common Tasks

### Export annotations for an item
```bash
# Python
uv run zotero-get-annots ITEM_KEY --org > notes.org

# API
curl -X POST http://localhost:23119/export-org/citekey \
  -H "Content-Type: application/json" \
  -d '{"key": "smith2023"}'
```

### List collections
```bash
# Uses native API (no plugin needed)
uv run zotero-collection --list

# Or via API
curl http://localhost:23119/api/users/0/collections
```

### Save URL to Zotero
```bash
# Select collection first
uv run zotero-collection

# Then save URL
uv run zotero-save "https://example.com/article"
```
