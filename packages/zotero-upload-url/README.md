# Zotero URL Saver

A simple macOS tool to save URLs to Zotero using your existing Firefox browser with the Zotero Connector extension.

## How It Works

1. Opens the URL in your existing Firefox (new tab)
2. Waits for you to complete any authentication (Duo push, login, etc.)
3. You press Enter when ready
4. Sends `Cmd+Shift+S` to trigger Zotero Connector
5. Zotero saves the item with full metadata and snapshot

## Prerequisites

- **macOS** (uses AppleScript)
- **Firefox** with [Zotero Connector](https://www.zotero.org/download/connectors) extension installed
- **Zotero** desktop app running

## Installation

Install globally with `uv`:

```bash
uv tool install git+https://github.com/titaniumbones/zotero-upload-url
```

Or from a local checkout:

```bash
uv tool install .
```

This installs two commands: `zotero-save` and `zotero-collection`.

## Usage

### Interactive Mode (recommended for sites requiring login)

```bash
zotero-save "https://example-library.edu/article"
```

The script will:
1. Open the URL in Firefox
2. Wait for you to press Enter (giving you time to authenticate)
3. Trigger Zotero save

### Auto Mode (for public sites)

```bash
zotero-save --auto 10 "https://arxiv.org/abs/2301.07041"
```

Waits 10 seconds for the page to load, then saves automatically.

### Save Current Tab

```bash
zotero-save --no-open placeholder
```

Just triggers the Zotero save on whatever tab is currently open in Firefox.

### Collection Selector

Select which Zotero collection to save items to:

```bash
zotero-collection              # Interactive selection (uses fzf if available)
zotero-collection --current    # Show current selection
zotero-collection --list       # List all collections (JSON)
```

### Create Collection

Create new collections in Zotero:

```bash
# Create a top-level collection in library 1
zotero-collection --library 1 --create "New Collection"

# Create a subcollection under an existing collection
zotero-collection --library 1 --create "Subcollection" --parent ABCD1234
```

## Options

### zotero-save

```
positional arguments:
  url                   URL to save (or placeholder if using --no-open)

options:
  -h, --help            show this help message and exit
  --auto SECONDS, -a SECONDS
                        Auto-save after N seconds instead of waiting for Enter
  --no-open, -n         Don't open URL (assume it's already open in Firefox)
  --skip-check          Skip checking if Zotero is running
```

### zotero-collection

```
options:
  -h, --help            show this help message and exit
  --port PORT, -p PORT  Zotero port (default: 23119)
  --current, -c         Show currently selected collection
  --list, -l            List all libraries and collections
  --tree, -t            Display list as tree (with --list)
  --library ID          Library ID for selection or creation
  --select KEY, -s KEY  Collection key to select (use with --library)
  --create NAME         Create a new collection (use with --library)
  --parent KEY          Parent collection for subcollection (use with --create)
  --json                Output in JSON format
  --no-fzf              Use numbered list instead of fuzzy finder
```

## Troubleshooting

### "Zotero is not running"

Start the Zotero desktop app before running this script.

### AppleScript permissions

On first run, macOS may ask for permissions to control Firefox and System Events. Grant these permissions in System Preferences > Security & Privacy > Privacy > Accessibility.

### Nothing happens when saving

Make sure the Zotero Connector extension is installed in Firefox and that Firefox is the frontmost window when the save is triggered.
