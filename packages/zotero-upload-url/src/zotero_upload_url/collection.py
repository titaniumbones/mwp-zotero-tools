"""
Zotero Collection Selector

List, select, and create Zotero collections.
- Listing uses Zotero's native API (no plugin required)
- Selection and creation use the export-org plugin API (requires plugin)

Use this to set the target collection before running zotero-save.

Usage:
    zotero-collection                        # Interactive selection
    zotero-collection --current              # Show current selection
    zotero-collection --list                 # List all collections
    zotero-collection --select KEY           # Select collection by key
    zotero-collection --create NAME          # Create new collection
    zotero-collection --create NAME --parent KEY  # Create subcollection
"""

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any

import requests

DEFAULT_ZOTERO_PORT = 23119

# Plugin API base path (for selection/creation)
PLUGIN_BASE_PATH = "/export-org"

# Native API base path (for listing)
NATIVE_BASE_PATH = "/api"


def get_plugin_url(port: int, endpoint: str) -> str:
    """Get URL for plugin API endpoints (selection, creation)."""
    return f"http://127.0.0.1:{port}{PLUGIN_BASE_PATH}{endpoint}"


def get_native_url(port: int, endpoint: str) -> str:
    """Get URL for native Zotero API endpoints (listing)."""
    return f"http://127.0.0.1:{port}{NATIVE_BASE_PATH}{endpoint}"


def get_current_collection(port: int) -> dict | None:
    """Get the currently selected library/collection.

    Uses plugin API (requires zotero-export-notes plugin).
    """
    try:
        r = requests.get(get_plugin_url(port, "/collection/current"), timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Zotero on port {port}", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def _build_collection_tree(collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build hierarchical tree from flat collection list.

    Takes flat list from native API and builds nested tree structure.
    """
    # Create lookup by key
    by_key: dict[str, dict[str, Any]] = {}
    for c in collections:
        data = c.get("data", {})
        key = c.get("key", "")
        by_key[key] = {
            "key": key,
            "name": data.get("name", "Unknown"),
            "parentKey": data.get("parentCollection") or None,
            "children": []
        }

    # Build tree
    roots: list[dict[str, Any]] = []
    for key, node in by_key.items():
        parent_key = node["parentKey"]
        if parent_key and parent_key in by_key:
            by_key[parent_key]["children"].append(node)
        else:
            roots.append(node)

    # Sort children alphabetically
    def sort_children(nodes: list[dict[str, Any]]) -> None:
        nodes.sort(key=lambda x: x["name"].lower())
        for node in nodes:
            if node["children"]:
                sort_children(node["children"])

    sort_children(roots)
    return roots


def list_collections_native(port: int) -> dict | None:
    """Get hierarchical list of all libraries and collections using native API.

    Uses Zotero's native API (no plugin required).
    """
    try:
        libraries: list[dict[str, Any]] = []

        # Get personal library collections
        personal_collections_resp = requests.get(
            get_native_url(port, "/users/0/collections"),
            timeout=10
        )
        personal_collections_resp.raise_for_status()
        personal_collections = personal_collections_resp.json()

        libraries.append({
            "id": 1,  # Personal library is always ID 1
            "name": "My Library",
            "type": "user",
            "collections": _build_collection_tree(personal_collections)
        })

        # Get group libraries
        groups_resp = requests.get(
            get_native_url(port, "/users/0/groups"),
            timeout=10
        )
        groups_resp.raise_for_status()
        groups = groups_resp.json()

        # Get collections for each group
        for group in groups:
            group_id = group.get("id")
            group_name = group.get("data", {}).get("name") or group.get("name", f"Group {group_id}")

            try:
                group_collections_resp = requests.get(
                    get_native_url(port, f"/groups/{group_id}/collections"),
                    timeout=10
                )
                group_collections_resp.raise_for_status()
                group_collections = group_collections_resp.json()
            except requests.exceptions.RequestException:
                group_collections = []

            libraries.append({
                "id": group_id,
                "name": group_name,
                "type": "group",
                "collections": _build_collection_tree(group_collections)
            })

        return {"libraries": libraries}

    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Zotero on port {port}", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def list_collections(port: int) -> dict | None:
    """Get hierarchical list of all libraries and collections.

    Uses native Zotero API (no plugin required).
    """
    return list_collections_native(port)


def select_collection(port: int, library_id: int, collection_key: str | None) -> dict | None:
    """Select a library or collection in Zotero's UI.

    Uses plugin API (requires zotero-export-notes plugin).
    """
    try:
        r = requests.post(
            get_plugin_url(port, "/collection/select"),
            json={"libraryID": library_id, "collectionKey": collection_key},
            timeout=5
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Zotero on port {port}", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def create_collection(port: int, library_id: int, name: str, parent_key: str | None = None) -> dict | None:
    """Create a new collection in Zotero.

    Uses plugin API (requires zotero-export-notes plugin).

    Args:
        port: Zotero connector port
        library_id: Library ID to create collection in
        name: Name of the new collection
        parent_key: Optional parent collection key for creating subcollections
    """
    try:
        payload = {"libraryID": library_id, "name": name}
        if parent_key:
            payload["parentKey"] = parent_key
        r = requests.post(
            get_plugin_url(port, "/collection/create"),
            json=payload,
            timeout=5
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Zotero on port {port}", file=sys.stderr)
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def print_tree(collections: list, prefix: str = "", start_idx: int = 1) -> tuple[list, int]:
    """Print collection tree and return flat list for selection.

    Returns (items, next_idx) where items is flat list and next_idx is the next available index.
    """
    items = []
    idx = start_idx

    for i, c in enumerate(collections):
        is_last = i == len(collections) - 1
        branch = "└── " if is_last else "├── "
        child_prefix = "    " if is_last else "│   "

        items.append(c)
        print(f"{prefix}{branch}[{idx}] {c['name']}")
        idx += 1

        if c.get("children"):
            child_items, idx = print_tree(c["children"], prefix + child_prefix, idx)
            items.extend(child_items)

    return items, idx


def build_flat_list(libraries: list) -> list:
    """Build flat list of all selectable items from library data."""
    all_items = []

    def add_collections(collections: list, lib_id: int, lib_name: str, depth: int = 0):
        for c in collections:
            indent = "  " * depth
            all_items.append({
                "type": "collection",
                "id": lib_id,
                "name": c["name"],
                "key": c["key"],
                "display": f"{lib_name} > {indent}{c['name']}"
            })
            if c.get("children"):
                add_collections(c["children"], lib_id, lib_name, depth + 1)

    for lib in libraries:
        # Add library root
        all_items.append({
            "type": "library",
            "id": lib["id"],
            "name": lib["name"],
            "key": None,
            "display": f"{lib['name']} (root)"
        })
        # Add collections
        if lib.get("collections"):
            add_collections(lib["collections"], lib["id"], lib["name"])

    return all_items


def fuzzy_select(items: list) -> dict | None:
    """Use fzf for fuzzy selection if available."""
    fzf_path = shutil.which("fzf")
    if not fzf_path:
        return None

    # Build input for fzf: "index:display_name"
    fzf_input = "\n".join(f"{i}:{item['display']}" for i, item in enumerate(items))

    try:
        result = subprocess.run(
            [fzf_path, "--height=40%", "--reverse", "--prompt=Collection> ",
             "--with-nth=2..", "--delimiter=:"],
            input=fzf_input,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            idx = int(result.stdout.strip().split(":")[0])
            return items[idx]
    except Exception:
        pass

    return None


def numbered_select(items: list, libraries: list) -> dict | None:
    """Fallback numbered selection when fzf is not available."""
    next_idx = 1

    for lib in libraries:
        print(f"[{next_idx}] {lib['name']} (Library root)")
        next_idx += 1

        if lib.get("collections"):
            _, next_idx = print_tree(lib["collections"], prefix="    ", start_idx=next_idx)

        print()

    try:
        choice = input("Select number (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            return None

        idx = int(choice) - 1
        if idx < 0 or idx >= len(items):
            print("Invalid selection.")
            return None

        return items[idx]

    except (ValueError, EOFError):
        return None


def interactive_select(port: int, use_fzf: bool = True) -> bool:
    """Interactive collection selection."""
    data = list_collections(port)
    if not data:
        return False

    libraries = data.get("libraries", [])
    if not libraries:
        print("No libraries found.")
        return False

    # Build flat list of all selectable items
    all_items = build_flat_list(libraries)

    # Try fzf first, fall back to numbered list
    selected = None
    if use_fzf:
        selected = fuzzy_select(all_items)

    if selected is None and not use_fzf:
        selected = numbered_select(all_items, libraries)
    elif selected is None:
        # fzf not available or cancelled, try numbered
        print("(fzf not found or cancelled, using numbered list)\n")
        selected = numbered_select(all_items, libraries)

    if selected is None:
        return False

    result = select_collection(port, selected["id"], selected["key"])

    if result and result.get("success"):
        if selected["key"]:
            print(f"Selected: {selected['name']} in library {selected['id']}")
        else:
            print(f"Selected: {selected['name']} (library root)")
        return True
    else:
        print(f"Failed to select: {result.get('error', 'Unknown error')}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="List and select Zotero collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Interactive selection
  %(prog)s --current                # Show current selection
  %(prog)s --list                   # List all collections (JSON)
  %(prog)s --list --tree            # List as tree
  %(prog)s --library 1 --select KEY # Select specific collection
  %(prog)s --library 1              # Select library root
  %(prog)s --library 1 --create "New Collection"  # Create collection
  %(prog)s --library 1 --create "Sub" --parent KEY  # Create subcollection
        """
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_ZOTERO_PORT,
        help=f"Zotero port (default: {DEFAULT_ZOTERO_PORT})"
    )
    parser.add_argument(
        "--current", "-c",
        action="store_true",
        help="Show currently selected collection"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all libraries and collections"
    )
    parser.add_argument(
        "--tree", "-t",
        action="store_true",
        help="Display list as tree (with --list)"
    )
    parser.add_argument(
        "--library",
        type=int,
        metavar="ID",
        help="Library ID for selection"
    )
    parser.add_argument(
        "--select", "-s",
        metavar="KEY",
        help="Collection key to select (use with --library)"
    )
    parser.add_argument(
        "--create",
        metavar="NAME",
        help="Create a new collection with this name (use with --library)"
    )
    parser.add_argument(
        "--parent",
        metavar="KEY",
        help="Parent collection key for creating subcollections (use with --create)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--no-fzf",
        action="store_true",
        help="Use numbered list instead of fuzzy finder"
    )

    args = parser.parse_args()

    # Show current selection
    if args.current:
        data = get_current_collection(args.port)
        if data:
            if args.json:
                print(json.dumps(data, indent=2))
            else:
                lib_name = data.get("libraryName", "Unknown")
                coll = data.get("collection")
                if coll:
                    print(f"Library: {lib_name} (ID: {data.get('libraryID')})")
                    print(f"Collection: {coll['name']} (Key: {coll['key']})")
                else:
                    print(f"Library: {lib_name} (ID: {data.get('libraryID')})")
                    print("Collection: (library root)")
        return 0 if data else 1

    # List all collections
    if args.list:
        data = list_collections(args.port)
        if data:
            if args.json or not args.tree:
                print(json.dumps(data, indent=2))
            else:
                for lib in data.get("libraries", []):
                    print(f"{lib['name']} (Library ID: {lib['id']})")
                    if lib.get("collections"):
                        print_tree(lib["collections"], prefix="  ")  # ignore return
                    print()
        return 0 if data else 1

    # Create collection
    if args.create:
        if args.library is None:
            print("Error: --library is required when using --create", file=sys.stderr)
            return 1
        result = create_collection(args.port, args.library, args.create, args.parent)
        if result:
            if args.json:
                print(json.dumps(result, indent=2))
            elif result.get("success"):
                coll = result.get("collection", {})
                print(f"Created: {coll.get('name')} (Key: {coll.get('key')})")
                if args.parent:
                    print(f"Parent: {args.parent}")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
                return 1
        return 0 if result and result.get("success") else 1

    # Programmatic selection
    if args.library is not None:
        result = select_collection(args.port, args.library, args.select)
        if result:
            if args.json:
                print(json.dumps(result, indent=2))
            elif result.get("success"):
                sel = result.get("selected", {})
                if sel.get("collectionKey"):
                    print(f"Selected: {sel.get('collectionName')} (Key: {sel.get('collectionKey')})")
                else:
                    print(f"Selected: Library {sel.get('libraryID')} (root)")
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
                return 1
        return 0 if result and result.get("success") else 1

    # Interactive selection (default)
    success = interactive_select(args.port, use_fzf=not args.no_fzf)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
