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

---

## Project History & Design Decisions

### Consolidation (January 2026)

This monorepo was created by consolidating three separate repositories:

1. **titaniumbones/zotero-export-notes** (archived)
   - Zotero 7 plugin with HTTP API
   - Now at `packages/zotero-export-notes/`

2. **titaniumbones/zotero-cli** (archived)
   - Python scripts + Emacs Lisp
   - Python now at `packages/zotero-cli/`
   - Elisp now at `packages/zotero-elisp/`

3. **titaniumbones/zotero-upload-url** (archived)
   - URL saving tool
   - Now at `packages/zotero-upload-url/`

### Key Design Decisions

**API Strategy: Prefer Native Zotero API**
- Collection listing (`zotero-collection --list`) uses native `/api/users/0/collections`
- This works without the plugin installed
- Plugin API only used for operations requiring UI manipulation:
  - `collection/select` (changes Zotero's UI selection)
  - `collection/create` (creates via Zotero's transaction system)
  - `collection/current` (reads UI state)
  - `picker` (gets current UI selection)

**Citekey Resolution**
- Plugin uses Better BibTeX JSON-RPC for real-time citekey lookup
- Python CLI uses exported BibTeX file parsing (offline/batch scenarios)
- Both approaches have valid use cases

**Emacs Lisp as First-Class**
- Elisp implementation maintains API parity with Python where possible
- Separate package (`zotero-elisp`) for clean Emacs integration
- Tests in `packages/zotero-elisp/test/`

### Future Considerations

1. **Shared Python API module**: The `ZoteroLocalAPI` class in `zotero-cli` could be extracted to a shared package that `zotero-upload-url` imports, avoiding code duplication.

2. **Package dependencies**: Currently independent packages. Could add:
   ```toml
   # packages/zotero-upload-url/pyproject.toml
   dependencies = ["zotero-cli"]  # For shared ZoteroLocalAPI
   ```

3. **Workspace configuration**: Could add root `pyproject.toml` with uv workspace config if packages need to share code.

### Detailed Comparison

See [packages/zotero-export-notes/docs/comparison.md](./packages/zotero-export-notes/docs/comparison.md) for:
- Complete API endpoint comparison
- Overlapping vs unique functionality matrix
- Data flow diagrams
- When to use which tool
