# Zotero Tooling Comparison

This document compares three related repositories for Zotero automation and details how they can be consolidated.

## Repository Purposes

| Repository | Purpose | Communication Method |
|------------|---------|---------------------|
| **zotero-export-notes** | Zotero 7 plugin - exports annotations, manages collections via UI | Exposes HTTP API on `/export-org/*` |
| **zotero-cli** | CLI toolkit - retrieves annotations, processes org files | Uses Zotero's native API `/api/*` |
| **zotero-upload-url** | URL saver - saves URLs via Firefox/AppleScript | Uses export-org API + AppleScript |

## API Comparison

### Zotero Native API (used by zotero-cli)

Zotero exposes a local HTTP server with these endpoints:

```
GET  /api/users/0/items              # Personal library items
GET  /api/users/0/items/<key>        # Specific item
GET  /api/users/0/items/<key>/children  # Child items (attachments, notes)
GET  /api/users/0/collections        # Personal library collections
GET  /api/groups                     # List groups user belongs to
GET  /api/groups/<id>/items          # Group library items
GET  /api/groups/<id>/collections    # Group library collections
```

### Export-Org Plugin API (exposed by zotero-export-notes)

The plugin adds these custom endpoints:

```
POST /export-org/citekey             # Export by citation key
GET  /export-org/libraries           # List all libraries
GET  /export-org/picker              # Get current Zotero UI selection
GET  /export-org/collections         # List collections (flat)
GET  /export-org/collection          # Get items in collection
GET  /export-org/collection/current  # Get currently selected collection
POST /export-org/collection/select   # Select collection in Zotero UI
POST /export-org/collection/create   # Create new collection
GET  /export-org/collections/list    # List collections (hierarchical tree)
```

## Overlapping Functionality

### 1. Annotation Export (org-mode/markdown)

| Feature | zotero-cli | zotero-export-notes |
|---------|-----------|---------------------|
| **Single item export** | `get-annots.py ITEM_ID --org` | POST `/export-org/citekey` |
| **Collection export** | `get-collection-annots.py` | POST `/export-org/collection` |
| **Batch export** | Yes | Yes (via `keys` array) |
| **Markdown support** | `--markdown` flag | `format: "md"` |
| **EPUB support** | Yes (via get_file_attachments) | Yes |
| **API used** | Native Zotero `/api/*` | Custom plugin API |
| **Citekey lookup** | Via BibTeX file parsing | Via Better BibTeX JSON-RPC |

**Key Difference**: zotero-cli uses a locally exported BibTeX file to resolve citation keys, while zotero-export-notes queries Better BibTeX directly via JSON-RPC.

### 2. Library/Collection Listing

| Feature | zotero-cli | zotero-upload-url |
|---------|-----------|-------------------|
| **Script** | `list-libraries.py` | `zotero-collection --list` |
| **API** | Native `/api/users/0/groups`, `/api/users/0/collections` | Plugin `/export-org/collections/list` |
| **Output** | JSON to file | JSON or tree to stdout |
| **Hierarchical** | Flat list | Full tree with nesting |

**Recommendation**: Use native API for listing (more portable, doesn't require plugin).

### 3. Collection Management

| Feature | zotero-upload-url | zotero-export-notes API |
|---------|-------------------|-------------------------|
| **List** | `--list` | GET `/export-org/collections` |
| **Select** | `--select KEY` | POST `/export-org/collection/select` |
| **Create** | `--create NAME` | POST `/export-org/collection/create` |
| **Current** | `--current` | GET `/export-org/collection/current` |

**Note**: Collection selection and creation require UI manipulation, so these must use the plugin API. Only listing can use the native API.

## Unique Functionality (No Overlap)

### zotero-cli only

- **`org_zotero_client.py`** - Parse org files for citations, resolve BibTeX keys, batch insert
- **`export-attachments.py`** - Download PDFs/EPUBs, convert to markdown with `markitdown`
- **Emacs Lisp implementation** (`zotero-api.el`, `org-zotero-client.el`)
- **Debugging scripts** (`debug-api.py`, `debug-annotations.py`)
- **BibTeX key resolution** from exported .bib files

### zotero-upload-url only

- **`zotero-save`** - URL saving via Firefox/AppleScript automation
- **Fuzzy finder (fzf)** integration for collection selection

### zotero-export-notes only

- **Zotero UI integration** (context menus)
- **`/export-org/picker`** - Get current selection from Zotero UI
- **Better BibTeX integration** - Direct citekey lookup via JSON-RPC

## Implementation Details

### zotero-cli Python Classes

```python
class ZoteroLocalAPI:
    """Wrapper for Zotero's native HTTP API"""

    def get_items(library_id=None)
    def get_item(item_key, library_id=None)
    def get_item_children(item_key, library_id=None)
    def get_pdf_attachments(item_id, library_id=None)
    def get_file_attachments(item_id, library_id=None, file_types=['pdf', 'epub'])
    def get_attachment_annotations(attachment_id, library_id=None)
    def get_item_annotations(item_key, library_id=None)
    def get_collections(library_id=None)
    def get_collection_items(collection_key, library_id=None)
    def get_all_collection_annotations(collection_id, library_id=None)
    def format_annotations_as_org(...)
    def format_annotations_as_markdown(...)
```

### zotero-upload-url API Usage

The `collection.py` module makes direct requests to:
- Plugin API: `/export-org/collections/list`, `/export-org/collection/select`, `/export-org/collection/create`
- These could be refactored to use native API for listing while keeping plugin API for selection/creation

### Emacs Lisp Functions

```elisp
;; zotero-api.el
(defun zotero-api-get-items (&optional library-id))
(defun zotero-api-get-item (item-key &optional library-id))
(defun zotero-api-get-item-children (item-key &optional library-id))
(defun zotero-api-get-collections (&optional library-id))
(defun zotero-api-get-collection-items (collection-key &optional library-id))

;; org-zotero-client.el
(defun org-zotero-get-annotations-for-item (item-key))
(defun org-zotero-insert-annotations (item-key))
(defun org-zotero-resolve-citation (citation-key bibtex-file))
```

## Recommendations for Consolidation

### 1. Collection Listing
**Decision**: Use **native Zotero API** for listing libraries/collections.

**Rationale**:
- Zotero's `/api/users/0/collections` and `/api/groups/{id}/collections` are stable
- Plugin API adds unnecessary dependency for basic collection listing
- Native API doesn't require the plugin to be installed

**Action**: Update `zotero-upload-url/collection.py` to use native API for `--list`.

### 2. Annotation Export
**Decision**: Keep **both approaches** but document when to use which.

| Use Case | Recommended Approach |
|----------|---------------------|
| Have citation key, want org output | Plugin API (`/export-org/citekey`) |
| Have item ID, want org output | zotero-cli (`get-annots.py`) |
| Need to process BibTeX file | zotero-cli (has BibTeX parsing) |
| Working in Emacs | Emacs Lisp implementation |
| Don't have plugin installed | zotero-cli (native API only) |

### 3. Shared API Client
**Decision**: Create single `ZoteroLocalAPI` class used by all Python scripts.

**Current situation**:
- `zotero-cli/python/get-annots.py` has `ZoteroLocalAPI` class
- `zotero-upload-url/collection.py` makes direct requests

**Action**:
1. Extract `ZoteroLocalAPI` class to shared module
2. Add collection selection/creation methods (using plugin API)
3. Both packages import from shared module

## Data Flow Diagrams

### URL Saving Flow (zotero-upload-url)
```
User runs: zotero-save "https://example.com"
    │
    ├─► Opens URL in Firefox
    │
    ├─► User authenticates (if needed)
    │
    ├─► AppleScript sends Cmd+Shift+S to Firefox
    │
    └─► Zotero Connector saves item to selected collection
```

### Annotation Export Flow (zotero-cli)
```
User runs: get-annots.py ITEM_KEY --org
    │
    ├─► GET /api/users/0/items/ITEM_KEY/children
    │       │
    │       └─► Filter for PDF/EPUB attachments
    │
    ├─► For each attachment:
    │       GET /api/users/0/items/ATTACHMENT_KEY/children
    │       │
    │       └─► Filter for annotations
    │
    └─► Format annotations as org-mode and output
```

### Annotation Export Flow (zotero-export-notes plugin)
```
User calls: POST /export-org/citekey {"key": "smith2023"}
    │
    ├─► Query Better BibTeX JSON-RPC for item
    │
    ├─► Get PDF attachment and annotations from Zotero API
    │
    └─► Format as org-mode and return JSON response
```
