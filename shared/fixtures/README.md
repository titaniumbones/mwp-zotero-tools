# Shared Test Fixtures

This directory contains JSON fixtures representing realistic Zotero API responses for use in tests across all packages.

## Directory Structure

```
fixtures/
├── items/
│   ├── journal-article.json    # Standard journal article with full metadata
│   ├── book.json               # Book item with publisher info
│   └── item-with-children.json # Parent item with PDF attachment and note
├── collections/
│   ├── flat-collections.json   # Simple top-level collections
│   └── nested-collections.json # Hierarchical collection structure
├── annotations/
│   └── pdf-highlights.json     # Various annotation types (highlight, note, underline, image)
└── libraries/
    └── group-libraries.json    # User library + group libraries with collections
```

## Fixture Details

### Items

- **journal-article.json**: A journal article by "Smith et al." with DOI, multiple authors, tags, and full metadata.
- **book.json**: A book by "Thompson" with ISBN, publisher, edition info.
- **item-with-children.json**: An item with a PDF attachment (`ATTACH01`), a standalone note (`NOTE0001`), and a linked URL attachment.

### Collections

- **flat-collections.json**: Three top-level collections without nesting.
- **nested-collections.json**: Hierarchical structure:
  - Research (root)
    - Machine Learning
    - Natural Language Processing
      - Transformers
  - Teaching Materials (root)

### Annotations

- **pdf-highlights.json**: Five annotations on `ATTACH01`:
  - Yellow highlight with comment (key insight)
  - Green highlight (transformer architecture)
  - Blue note (follow-up needed)
  - Purple underline (transfer learning)
  - Red image annotation (figure)

### Libraries

- **group-libraries.json**: Contains:
  - User library (id: 12345)
  - Two groups: "AI Research Lab" (98765) and "Book Club" (87654)
  - Sample group collections

## Usage

### Python (pytest)

```python
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "shared" / "fixtures"

def load_fixture(path: str) -> dict | list:
    with open(FIXTURES_DIR / path) as f:
        return json.load(f)

# Example
article = load_fixture("items/journal-article.json")
```

### TypeScript

```typescript
import * as path from 'path';
import * as fs from 'fs';

const FIXTURES_DIR = path.join(__dirname, '..', '..', '..', 'shared', 'fixtures');

export function loadFixture<T>(relativePath: string): T {
  const fullPath = path.join(FIXTURES_DIR, relativePath);
  return JSON.parse(fs.readFileSync(fullPath, 'utf-8'));
}
```

### Emacs Lisp

```elisp
(defun zotero-test-load-fixture (path)
  "Load JSON fixture from PATH relative to shared/fixtures."
  (let ((full-path (expand-file-name
                    path
                    (expand-file-name "../../shared/fixtures"
                                      (file-name-directory load-file-name)))))
    (json-read-file full-path)))
```
