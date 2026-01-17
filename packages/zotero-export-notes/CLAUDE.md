# Zotero Export Notes - Project Documentation

## Project Overview

A Zotero 7 plugin that exports PDF annotations from the current PDF (or current item's PDF attachment) as an `.org` file. Each annotation is formatted as a quote block with org-pdftools style links to the specific page in the local PDF file.

## Target Output Format

The plugin generates org-mode files with:
- Title as level 1 heading with property drawer below (org-mode requires property drawers under headings, not at file level)
- Annotations section as level 2 heading
- Each annotation: link with colon postfix ABOVE the block

```org
* Deep Learning for NLP
:PROPERTIES:
:AUTHOR: Smith, John
:DATE: 2023
:DOI: 10.1234/example
:ZOTERO_KEY: ABC123XY
:END:

** Annotations

[[pdf:/path/to/file.pdf::5++32.50;;annot-5-XYZ789][Page 5]]:
#+begin_quote
Highlighted text from the PDF annotation
#+end_quote

My comment on this highlight.

[[pdf:/path/to/file.pdf::7++15.20;;annot-7-DEF456][Page 7]]:
#+begin_comment
This is a standalone note annotation
#+end_comment
```

The org-pdftools link format is:
- Basic: `[[pdf:~/file.pdf::3][Page 3]]:`
- With annotation: `[[pdf:~/file.pdf::5++0.00;;annot-5-0][Page 5]]:`

## Technology Stack

- **Zotero 7**: Target platform (uses bootstrapped plugin architecture, not overlays)
- **TypeScript**: Primary development language
- **zotero-plugin-template**: Bootstrap from https://github.com/windingwind/zotero-plugin-template
- **zotero-plugin-toolkit**: Utility library for common plugin operations
- **ESBuild**: Build/transpilation tool

## Zotero 7 Plugin Architecture

### Key Files
- `manifest.json` - WebExtension-style plugin manifest
- `bootstrap.js` - Lifecycle hooks (startup, shutdown, install, uninstall)
- `src/hooks.ts` - Window lifecycle hooks (onMainWindowLoad, onMainWindowUnload)
- `src/index.ts` - Main entry point

### Lifecycle Hooks
```javascript
startup({ id, version, rootURI }, reason)  // Initialize plugin
shutdown({ id, version, rootURI }, reason) // Clean up
onMainWindowLoad({ id, version, rootURI }, window)   // Modify UI
onMainWindowUnload({ id, version, rootURI }, window) // Remove UI elements
```

### Zotero JavaScript API for Annotations

```javascript
// Get selected items
var item = ZoteroPane.getSelectedItems()[0];

// Get annotations from a PDF attachment
var annotations = item.getAnnotations();

// Filter by type (highlight, note, image, underline, ink)
var highlights = annotations.filter(x => x.annotationType == 'highlight');

// Get attachment file path
let path = attachment.getFilePath();

// File I/O
await Zotero.File.putContentsAsync(path, data);
```

Annotations are child items of PDF attachments with `itemType: annotation`.

## Development Commands

```bash
npm install          # Install dependencies
npm start            # Start dev server with hot reload
npm run build        # Production build
npm run release      # Version bump and release
```

## Plugin Features

### Context Menu
Right-click on items with PDF attachments to access:
- **Save to File...** - Export annotations to an .org file
- **Copy to Clipboard** - Copy org-formatted annotations

### HTTP API Endpoint

The plugin exposes an HTTP API endpoint on Zotero's built-in server (default port 23119, check Zotero preferences).

**Endpoint:**
```
POST http://localhost:<port>/export-org/citekey
Content-Type: application/json
{"key": "<citekey>"}
```

**Example:**
```bash
curl -X POST "http://localhost:23119/export-org/citekey" \
  -H "Content-Type: application/json" \
  -d '{"key":"smith2023deep"}'
```

**Response (JSON):**
```json
{
  "success": true,
  "citekey": "smith2023deep",
  "title": "Deep Learning for NLP",
  "annotationCount": 5,
  "org": "* Deep Learning for NLP\n:PROPERTIES:\n..."
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Item not found for citekey: smith2023deep"
}
```

**Notes:**
- Uses Better BibTeX JSON-RPC API for citekey lookup (recommended)
- Falls back to searching Extra field for "Citation Key: xxx"
- Only accessible from localhost (127.0.0.1)
- Check Zotero > Preferences > Advanced > Config Editor for `extensions.zotero.httpServer.port`

## Testing Strategy

- Unit tests for org-mode formatting functions
- Integration tests using Zotero's test framework
- Manual testing with sample PDFs containing various annotation types

## Key Resources

- [Zotero Plugin Template](https://github.com/windingwind/zotero-plugin-template)
- [Zotero 7 for Developers](https://www.zotero.org/support/dev/zotero_7_for_developers)
- [Zotero JavaScript API](https://www.zotero.org/support/dev/client_coding/javascript_api)
- [org-pdftools](https://github.com/fuxialexander/org-pdftools)
