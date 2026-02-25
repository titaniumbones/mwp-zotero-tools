---
name: zotero-collector
description: >
  Save web resources and document references to Zotero collections.
  Use this skill when: (1) Performing web searches where results may be worth saving,
  (2) User asks to add references/URLs to Zotero, (3) Extracting references from
  PDFs or documents to save to Zotero, (4) Creating or organizing Zotero collections.
  When doing web searches, ask user before adding results to Zotero (unless explicitly instructed).
---

# Zotero Collector

Save URLs, DOIs, and references to Zotero via Firefox + Zotero Connector.

## When to Use This Skill

**Proactively offer** to save to Zotero when:
- You perform a web search that returns academic papers, articles, or valuable resources
- You help the user find documentation, tutorials, or reference materials
- You extract or discuss references from a document the user shares
- The user mentions building a reading list or collecting sources

**Use immediately** when the user:
- Asks to "save to Zotero", "add to Zotero", or "collect references"
- Provides URLs and mentions Zotero
- Asks to harvest/extract references from text or documents
- Wants to organize Zotero collections

## Prerequisites

Before running commands, verify:
```bash
# Check if Zotero is running
curl -s http://127.0.0.1:23119/connector/ping && echo "Zotero running" || echo "Zotero not running"
```

If Zotero isn't running, tell the user: "Please start Zotero desktop before saving references."

Requirements:
- Zotero desktop running (port 23119, or 23124 in dev mode)
- Firefox with Zotero Connector extension
- `zotero-upload-url` package installed

---

## Workflow 1: Harvest References from Text

Use when: User provides text containing references (LLM output, notes, markdown, etc.)

### Step 1: Extract References

Write the text to a temp file and extract:

```bash
# Write user's text to temp file
cat > /tmp/refs.md << 'EOF'
[paste user's text here]
EOF

# Extract references
zotero-harvest --extract /tmp/refs.md
```

Or pipe directly:
```bash
echo "user's text with [links](https://example.com) and doi:10.1000/xyz" | zotero-harvest --extract -
```

### Step 2: Present Results to User

Show the extracted references and ask:
- "I found N references. Which would you like to save to Zotero?"
- "Would you like to save all of these, or select specific ones?"

### Step 3: Select Target Collection

```bash
# List available collections
zotero-collection --list --tree

# Or show current selection
zotero-collection --current
```

Ask user which collection to use. Offer to create a new one if needed:
```bash
zotero-collection --library 1 --create "Collection Name"
```

### Step 4: Import References

```bash
# Dry run first to confirm
zotero-harvest --import /tmp/refs.md --collection COLLECTION_KEY --dry-run

# If user confirms, import
zotero-harvest --import /tmp/refs.md --collection COLLECTION_KEY
```

For selective import, use interactive mode:
```bash
zotero-harvest --import /tmp/refs.md --collection COLLECTION_KEY --interactive
```

---

## Workflow 2: Save Web Search Results

Use when: You perform a WebSearch and results may be worth saving.

### Step 1: Complete the Search

Perform the web search as requested. Present results to user.

### Step 2: Offer to Save (Don't Auto-Save)

After presenting results, ask:
> "Would you like to save any of these to your Zotero library?"

Only proceed if user confirms.

### Step 3: Collect URLs to Save

Extract URLs from the search results. Create a temp file:

```bash
cat > /tmp/search_refs.md << 'EOF'
- [Result Title 1](https://url1.com)
- [Result Title 2](https://url2.com)
- [Result Title 3](https://url3.com)
EOF
```

### Step 4: Follow Workflow 1 Steps 3-4

Select collection and import.

---

## Workflow 3: Save Direct URLs

Use when: User provides specific URLs to save.

### For Single URL:
```bash
# Check Zotero is running first
zotero-save --auto 8 "https://example.com/article"
```

### For Multiple URLs:

Create a file with the URLs:
```bash
cat > /tmp/urls.md << 'EOF'
https://url1.com
https://url2.com
[Title](https://url3.com)
EOF

zotero-harvest --import /tmp/urls.md --collection KEY
```

---

## Workflow 4: Extract from PDF/Document

Use when: User shares a document with a reference list.

### Step 1: Read the Document

Use Read tool to examine the document's references/bibliography section.

### Step 2: Extract Identifiable References

Look for:
- DOIs (e.g., `doi:10.1000/xyz` or `https://doi.org/10.1000/xyz`)
- arXiv IDs (e.g., `arXiv:2301.00001`)
- URLs to papers/articles
- Titles that can be searched

### Step 3: Create Reference List

For references with DOIs/URLs:
```bash
cat > /tmp/doc_refs.md << 'EOF'
doi:10.1038/nature12373
arXiv:2301.00001
https://example.com/paper
EOF

zotero-harvest --extract /tmp/doc_refs.md
```

### Step 4: Handle Ambiguous References

For references without DOIs/URLs (just author-year citations):
1. Tell the user which references couldn't be automatically resolved
2. Offer to search for them: "Would you like me to search for 'Smith et al. 2023' to find the DOI?"
3. If found, add to the import list

### Step 5: Import

Follow Workflow 1 Steps 3-4.

---

## Workflow 5: Collection Management

### List All Collections
```bash
zotero-collection --list --tree
```

### Create New Collection
```bash
# Top-level collection
zotero-collection --library 1 --create "New Collection"

# Subcollection (need parent key from --list)
zotero-collection --library 1 --create "Subcollection" --parent PARENT_KEY
```

### Select Collection (for subsequent saves)
```bash
zotero-collection --library 1 --select COLLECTION_KEY
```

### Get Current Selection
```bash
zotero-collection --current
```

---

## Command Reference

### zotero-harvest

```bash
# Extract mode - analyze text for references
zotero-harvest --extract FILE          # From file
zotero-harvest --extract -             # From stdin
zotero-harvest --extract FILE --json   # JSON output

# Import mode - save references to Zotero
zotero-harvest --import FILE --collection KEY
zotero-harvest --import FILE --collection KEY --dry-run      # Preview only
zotero-harvest --import FILE --collection KEY --interactive  # Confirm each

# Options
--port PORT      # Zotero port (default: 23119, dev mode: 23124)
--delay SECONDS  # Wait between saves (default: 8)
```

### zotero-save

```bash
zotero-save "URL"              # Interactive (waits for Enter)
zotero-save --auto 8 "URL"     # Auto-save after 8 seconds
zotero-save --no-open x        # Save current Firefox tab

# Options
--port PORT        # Zotero port
--shortcut KEY     # Connector shortcut (default: option+cmd+s)
```

### zotero-collection

```bash
zotero-collection --list              # List all (JSON)
zotero-collection --list --tree       # List as tree
zotero-collection --current           # Show current selection
zotero-collection --library ID --select KEY        # Select collection
zotero-collection --library ID --create "Name"     # Create collection
zotero-collection --library ID --create "Name" --parent KEY  # Subcollection
```

---

## Reference Patterns Detected

The harvester automatically detects:

| Pattern | Example | Resolved URL |
|---------|---------|--------------|
| Plain URL | `https://arxiv.org/abs/2301.00001` | As-is |
| Markdown link | `[Title](https://example.com)` | URL with title preserved |
| DOI prefix | `doi:10.1038/nature12373` | `https://doi.org/10.1038/nature12373` |
| DOI URL | `https://doi.org/10.1038/nature12373` | As-is |
| arXiv prefix | `arXiv:2301.00001` | `https://arxiv.org/abs/2301.00001` |
| arXiv URL | `https://arxiv.org/abs/2301.00001` | As-is |

Markdown links take precedence when deduplicating (they preserve titles).

---

## Error Handling

### "Zotero is not running"
Tell user: "Please start Zotero desktop and try again."

### "Cannot connect to Zotero on port X"
Try alternate port:
```bash
curl -s http://127.0.0.1:23124/connector/ping && echo "Try --port 23124"
```

### Save fails for specific URL
- Some sites block automated saves
- Tell user: "The save for [URL] may not have completed. You can manually save it in Firefox with Option+Cmd+S"
- Continue with remaining URLs

### Rate limiting / slow sites
Increase delay:
```bash
zotero-harvest --import file.md --collection KEY --delay 12
```

---

## Timing Guidelines

| Site Type | Recommended Delay |
|-----------|-------------------|
| arXiv, GitHub, Wikipedia | `--auto 5` or `--delay 5` |
| Most academic journals | `--auto 8` or `--delay 8` (default) |
| NYT, paywalled sites | `--auto 12` or `--delay 12` |
| Heavy/slow-loading pages | `--auto 15` or `--delay 15` |

---

## Example Conversations

### User: "Save these papers to Zotero"
1. Extract references from their message
2. Ask which collection
3. Import with dry-run first, then confirm

### User: "Search for papers on transformers and save the good ones"
1. Perform web search
2. Present results
3. Ask: "Which of these would you like to save?"
4. Create reference file from selections
5. Ask which collection (offer to create new)
6. Import

### User: "Extract the references from this PDF"
1. Read the PDF's bibliography
2. Identify DOIs, arXiv IDs, URLs
3. Report what was found vs. what needs manual lookup
4. Offer to search for unresolved references
5. Import resolved references

### User: "Create a collection for my thesis research"
1. `zotero-collection --library 1 --create "Thesis Research"`
2. Report the new collection key
3. Ask if they want subcollections (e.g., "Literature Review", "Methods")
