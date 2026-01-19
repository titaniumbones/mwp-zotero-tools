"""Shared pytest fixtures for zotero-upload-url tests."""

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
def nested_collections():
    """Load nested collections fixture."""
    return load_fixture("collections/nested-collections.json")


@pytest.fixture
def flat_collections():
    """Load flat collections fixture."""
    return load_fixture("collections/flat-collections.json")


@pytest.fixture
def group_libraries():
    """Load group libraries fixture."""
    return load_fixture("libraries/group-libraries.json")


@pytest.fixture
def mock_responses():
    """Context manager for mocking HTTP responses."""
    with responses.RequestsMock() as rsps:
        yield rsps
