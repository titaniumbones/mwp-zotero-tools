"""Shared pytest fixtures for zotero-cli tests."""

import json
from pathlib import Path
from typing import Any

import pytest
import responses

# Path to shared fixtures
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "shared" / "fixtures"


def load_fixture(path: str) -> Any:
    """Load a JSON fixture file.

    Args:
        path: Relative path within shared/fixtures directory

    Returns:
        Parsed JSON content
    """
    with open(FIXTURES_DIR / path) as f:
        return json.load(f)


@pytest.fixture
def journal_article():
    """Load journal article fixture."""
    return load_fixture("items/journal-article.json")


@pytest.fixture
def book_item():
    """Load book item fixture."""
    return load_fixture("items/book.json")


@pytest.fixture
def item_with_children():
    """Load item with children fixture."""
    return load_fixture("items/item-with-children.json")


@pytest.fixture
def nested_collections():
    """Load nested collections fixture."""
    return load_fixture("collections/nested-collections.json")


@pytest.fixture
def flat_collections():
    """Load flat collections fixture."""
    return load_fixture("collections/flat-collections.json")


@pytest.fixture
def pdf_annotations():
    """Load PDF annotations fixture."""
    return load_fixture("annotations/pdf-highlights.json")


@pytest.fixture
def group_libraries():
    """Load group libraries fixture."""
    return load_fixture("libraries/group-libraries.json")


@pytest.fixture
def mock_responses():
    """Context manager for mocking HTTP responses.

    Usage:
        def test_something(mock_responses):
            with mock_responses:
                responses.add(responses.GET, url, json=data)
                # ... test code
    """
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def zotero_api():
    """Create a ZoteroLocalAPI instance for testing."""
    from zotero_cli.api import ZoteroLocalAPI
    return ZoteroLocalAPI()


@pytest.fixture
def annotations_data(journal_article, pdf_annotations):
    """Create a realistic annotations_data structure for formatting tests."""
    return {
        "item_id": journal_article["key"],
        "item_title": journal_article["data"]["title"],
        "item_type": journal_article["data"]["itemType"],
        "attachments": [
            {
                "attachment_id": "ATTACH01",
                "attachment_title": "Garcia - 2024 - Advances in Natural Language Processing.pdf",
                "filename": "Garcia - 2024 - Advances in Natural Language Processing.pdf",
                "annotations_count": len(pdf_annotations),
                "annotations": pdf_annotations
            }
        ]
    }


@pytest.fixture
def collection_data(nested_collections, annotations_data):
    """Create a realistic collection_data structure for collection formatting tests."""
    return {
        "collection_id": nested_collections[0]["key"],
        "collection_name": nested_collections[0]["data"]["name"],
        "collection_parent": nested_collections[0]["data"]["parentCollection"],
        "library_id": None,
        "items_count": 15,
        "items": [annotations_data]
    }
