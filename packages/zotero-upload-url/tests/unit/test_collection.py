"""Tests for collection management functions."""

import pytest
import responses

from zotero_upload_url.collection import (
    _build_collection_tree,
    build_flat_list,
    create_collection,
    get_current_collection,
    get_native_url,
    get_plugin_url,
    list_collections_native,
    select_collection,
)


class TestUrlHelpers:
    """Tests for URL helper functions."""

    def test_get_plugin_url(self):
        """Test plugin URL construction."""
        url = get_plugin_url(23119, "/collection/current")
        assert url == "http://127.0.0.1:23119/export-org/collection/current"

    def test_get_plugin_url_custom_port(self):
        """Test plugin URL with custom port."""
        url = get_plugin_url(9999, "/collection/select")
        assert url == "http://127.0.0.1:9999/export-org/collection/select"

    def test_get_native_url(self):
        """Test native API URL construction."""
        url = get_native_url(23119, "/users/0/collections")
        assert url == "http://127.0.0.1:23119/api/users/0/collections"

    def test_get_native_url_custom_port(self):
        """Test native API URL with custom port."""
        url = get_native_url(8080, "/groups/12345/collections")
        assert url == "http://127.0.0.1:8080/api/groups/12345/collections"


class TestBuildCollectionTree:
    """Tests for the _build_collection_tree function."""

    def test_empty_list(self):
        """Test building tree from empty list."""
        result = _build_collection_tree([])
        assert result == []

    def test_flat_collections(self, flat_collections):
        """Test building tree from flat collections (no nesting)."""
        result = _build_collection_tree(flat_collections)

        assert len(result) == 3
        # All should be roots since no parent
        for node in result:
            assert node["children"] == []

    def test_nested_collections(self, nested_collections):
        """Test building tree from nested collections."""
        result = _build_collection_tree(nested_collections)

        # Should have 2 roots: Research and Teaching Materials
        assert len(result) == 2

        # Find Research collection (has children)
        research = next((c for c in result if c["name"] == "Research"), None)
        assert research is not None
        assert len(research["children"]) == 2  # ML and NLP

        # NLP should have Transformers as child
        nlp = next((c for c in research["children"] if c["name"] == "Natural Language Processing"), None)
        assert nlp is not None
        assert len(nlp["children"]) == 1
        assert nlp["children"][0]["name"] == "Transformers"

    def test_alphabetical_sorting(self):
        """Test that children are sorted alphabetically."""
        collections = [
            {"key": "C", "data": {"name": "Zebra", "parentCollection": False}},
            {"key": "A", "data": {"name": "Apple", "parentCollection": False}},
            {"key": "B", "data": {"name": "Banana", "parentCollection": False}},
        ]
        result = _build_collection_tree(collections)

        names = [c["name"] for c in result]
        assert names == ["Apple", "Banana", "Zebra"]

    def test_preserves_keys(self, nested_collections):
        """Test that keys are preserved in tree nodes."""
        result = _build_collection_tree(nested_collections)

        # Check that keys are present
        for node in result:
            assert "key" in node
            assert node["key"] is not None

    def test_parent_key_stored(self, nested_collections):
        """Test that parent keys are stored in tree nodes."""
        result = _build_collection_tree(nested_collections)

        # Root nodes should have None parentKey
        research = next((c for c in result if c["name"] == "Research"), None)
        assert research["parentKey"] is None

        # Child nodes should have parentKey
        ml = next((c for c in research["children"] if c["name"] == "Machine Learning"), None)
        assert ml["parentKey"] == research["key"]


class TestBuildFlatList:
    """Tests for the build_flat_list function."""

    def test_empty_libraries(self):
        """Test building flat list from empty library list."""
        result = build_flat_list([])
        assert result == []

    def test_library_root_included(self):
        """Test that library roots are included."""
        libraries = [
            {"id": 1, "name": "My Library", "type": "user", "collections": []}
        ]
        result = build_flat_list(libraries)

        assert len(result) == 1
        assert result[0]["type"] == "library"
        assert result[0]["name"] == "My Library"
        assert result[0]["key"] is None

    def test_collections_included(self):
        """Test that collections are included."""
        libraries = [
            {
                "id": 1,
                "name": "My Library",
                "type": "user",
                "collections": [
                    {"key": "COL1", "name": "Test Collection", "children": []}
                ]
            }
        ]
        result = build_flat_list(libraries)

        assert len(result) == 2  # Library root + 1 collection
        assert result[1]["type"] == "collection"
        assert result[1]["key"] == "COL1"

    def test_nested_collections_flattened(self):
        """Test that nested collections are flattened."""
        libraries = [
            {
                "id": 1,
                "name": "My Library",
                "type": "user",
                "collections": [
                    {
                        "key": "PARENT",
                        "name": "Parent",
                        "children": [
                            {"key": "CHILD", "name": "Child", "children": []}
                        ]
                    }
                ]
            }
        ]
        result = build_flat_list(libraries)

        assert len(result) == 3  # Library root + parent + child
        keys = [item.get("key") for item in result]
        assert None in keys  # Library root
        assert "PARENT" in keys
        assert "CHILD" in keys

    def test_display_format(self):
        """Test that display strings are formatted correctly."""
        libraries = [
            {
                "id": 1,
                "name": "My Library",
                "type": "user",
                "collections": [
                    {"key": "COL1", "name": "Test", "children": []}
                ]
            }
        ]
        result = build_flat_list(libraries)

        assert result[0]["display"] == "My Library (root)"
        assert "My Library > " in result[1]["display"]


class TestGetCurrentCollection:
    """Tests for the get_current_collection function."""

    @responses.activate
    def test_successful_request(self):
        """Test successful get current collection request."""
        responses.add(
            responses.GET,
            "http://127.0.0.1:23119/export-org/collection/current",
            json={
                "libraryID": 1,
                "libraryName": "My Library",
                "collection": {"key": "COL1", "name": "Test"}
            },
            status=200
        )

        result = get_current_collection(23119)

        assert result is not None
        assert result["libraryID"] == 1
        assert result["collection"]["key"] == "COL1"

    @responses.activate
    def test_connection_error(self, capsys):
        """Test handling of connection error."""
        responses.add(
            responses.GET,
            "http://127.0.0.1:23119/export-org/collection/current",
            body=responses.ConnectionError("Connection refused")
        )

        result = get_current_collection(23119)

        assert result is None
        captured = capsys.readouterr()
        assert "Cannot connect to Zotero" in captured.err

    @responses.activate
    def test_http_error(self, capsys):
        """Test handling of HTTP error."""
        responses.add(
            responses.GET,
            "http://127.0.0.1:23119/export-org/collection/current",
            status=500
        )

        result = get_current_collection(23119)

        assert result is None


class TestListCollectionsNative:
    """Tests for the list_collections_native function."""

    @responses.activate
    def test_successful_request(self, nested_collections, group_libraries):
        """Test successful list collections request."""
        # Mock personal library collections
        responses.add(
            responses.GET,
            "http://127.0.0.1:23119/api/users/0/collections",
            json=nested_collections,
            status=200
        )
        # Mock groups
        responses.add(
            responses.GET,
            "http://127.0.0.1:23119/api/users/0/groups",
            json=group_libraries["groups"],
            status=200
        )
        # Mock group collections
        for group in group_libraries["groups"]:
            group_id = group["id"]
            group_colls = group_libraries.get("group_collections", {}).get(str(group_id), [])
            responses.add(
                responses.GET,
                f"http://127.0.0.1:23119/api/groups/{group_id}/collections",
                json=group_colls,
                status=200
            )

        result = list_collections_native(23119)

        assert result is not None
        assert "libraries" in result
        # Personal library + 2 groups
        assert len(result["libraries"]) == 3

    @responses.activate
    def test_connection_error(self, capsys):
        """Test handling of connection error."""
        responses.add(
            responses.GET,
            "http://127.0.0.1:23119/api/users/0/collections",
            body=responses.ConnectionError("Connection refused")
        )

        result = list_collections_native(23119)

        assert result is None
        captured = capsys.readouterr()
        assert "Cannot connect to Zotero" in captured.err

    @responses.activate
    def test_personal_library_included(self, flat_collections):
        """Test that personal library is always included."""
        responses.add(
            responses.GET,
            "http://127.0.0.1:23119/api/users/0/collections",
            json=flat_collections,
            status=200
        )
        responses.add(
            responses.GET,
            "http://127.0.0.1:23119/api/users/0/groups",
            json=[],
            status=200
        )

        result = list_collections_native(23119)

        assert result is not None
        assert len(result["libraries"]) == 1
        assert result["libraries"][0]["name"] == "My Library"
        assert result["libraries"][0]["type"] == "user"


class TestSelectCollection:
    """Tests for the select_collection function."""

    @responses.activate
    def test_successful_selection(self):
        """Test successful collection selection."""
        responses.add(
            responses.POST,
            "http://127.0.0.1:23119/export-org/collection/select",
            json={"success": True, "selected": {"libraryID": 1, "collectionKey": "COL1"}},
            status=200
        )

        result = select_collection(23119, 1, "COL1")

        assert result is not None
        assert result["success"] is True

    @responses.activate
    def test_select_library_root(self):
        """Test selecting library root (no collection key)."""
        responses.add(
            responses.POST,
            "http://127.0.0.1:23119/export-org/collection/select",
            json={"success": True, "selected": {"libraryID": 1, "collectionKey": None}},
            status=200
        )

        result = select_collection(23119, 1, None)

        assert result is not None
        assert result["success"] is True

    @responses.activate
    def test_connection_error(self, capsys):
        """Test handling of connection error."""
        responses.add(
            responses.POST,
            "http://127.0.0.1:23119/export-org/collection/select",
            body=responses.ConnectionError("Connection refused")
        )

        result = select_collection(23119, 1, "COL1")

        assert result is None
        captured = capsys.readouterr()
        assert "Cannot connect to Zotero" in captured.err


class TestCreateCollection:
    """Tests for the create_collection function."""

    @responses.activate
    def test_successful_creation(self):
        """Test successful collection creation."""
        responses.add(
            responses.POST,
            "http://127.0.0.1:23119/export-org/collection/create",
            json={
                "success": True,
                "collection": {"key": "NEWCOL", "name": "New Collection"}
            },
            status=200
        )

        result = create_collection(23119, 1, "New Collection")

        assert result is not None
        assert result["success"] is True
        assert result["collection"]["name"] == "New Collection"

    @responses.activate
    def test_create_subcollection(self):
        """Test creating a subcollection with parent key."""
        responses.add(
            responses.POST,
            "http://127.0.0.1:23119/export-org/collection/create",
            json={
                "success": True,
                "collection": {"key": "SUBCOL", "name": "Subcollection"}
            },
            status=200
        )

        result = create_collection(23119, 1, "Subcollection", parent_key="PARENT")

        assert result is not None
        assert result["success"] is True

        # Verify request body included parent key
        request = responses.calls[0].request
        import json
        body = json.loads(request.body)
        assert body["parentKey"] == "PARENT"

    @responses.activate
    def test_connection_error(self, capsys):
        """Test handling of connection error."""
        responses.add(
            responses.POST,
            "http://127.0.0.1:23119/export-org/collection/create",
            body=responses.ConnectionError("Connection refused")
        )

        result = create_collection(23119, 1, "New Collection")

        assert result is None
        captured = capsys.readouterr()
        assert "Cannot connect to Zotero" in captured.err

    @responses.activate
    def test_http_error(self, capsys):
        """Test handling of HTTP error."""
        responses.add(
            responses.POST,
            "http://127.0.0.1:23119/export-org/collection/create",
            status=500
        )

        result = create_collection(23119, 1, "New Collection")

        assert result is None
