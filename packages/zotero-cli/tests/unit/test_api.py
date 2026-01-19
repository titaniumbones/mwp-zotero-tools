"""Tests for ZoteroLocalAPI HTTP methods."""

import pytest
import responses

from zotero_cli.api import ZoteroLocalAPI


class TestMakeRequest:
    """Tests for the _make_request method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_successful_request(self, api):
        """Test successful API request."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ABC123",
            json={"key": "ABC123", "data": {"title": "Test"}},
            status=200
        )

        result = api._make_request("/api/users/0/items/ABC123")

        assert result is not None
        assert result["key"] == "ABC123"

    @responses.activate
    def test_request_with_leading_slash(self, api):
        """Test request with leading slash in endpoint."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items",
            json=[{"key": "ABC123"}],
            status=200
        )

        result = api._make_request("/api/users/0/items")

        assert result is not None
        assert len(result) == 1

    @responses.activate
    def test_request_without_leading_slash(self, api):
        """Test request without leading slash in endpoint."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items",
            json=[{"key": "ABC123"}],
            status=200
        )

        result = api._make_request("api/users/0/items")

        assert result is not None

    @responses.activate
    def test_request_failure_returns_none(self, api, capsys):
        """Test that failed request returns None."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/NOTFOUND",
            status=404
        )

        result = api._make_request("/api/users/0/items/NOTFOUND")

        assert result is None

    @responses.activate
    def test_json_parse_error_returns_none(self, api, capsys):
        """Test that JSON parse error returns None."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items",
            body="not valid json",
            status=200
        )

        result = api._make_request("/api/users/0/items")

        assert result is None


class TestGetItem:
    """Tests for the get_item method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_get_item_personal_library(self, api, journal_article):
        """Test getting item from personal library."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ABC12345",
            json=journal_article,
            status=200
        )

        result = api.get_item("ABC12345")

        assert result is not None
        assert result["key"] == "ABC12345"

    @responses.activate
    def test_get_item_group_library(self, api, journal_article):
        """Test getting item from group library."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/groups/12345/items/ABC12345",
            json=journal_article,
            status=200
        )

        result = api.get_item("ABC12345", library_id="12345")

        assert result is not None

    @responses.activate
    def test_get_item_not_found(self, api):
        """Test getting non-existent item."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/NOTFOUND",
            status=404
        )

        result = api.get_item("NOTFOUND")

        assert result is None


class TestGetItemChildren:
    """Tests for the get_item_children method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_get_children_returns_list(self, api, item_with_children):
        """Test getting children returns a list."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/PARENT01/children",
            json=item_with_children["children"],
            status=200
        )

        result = api.get_item_children("PARENT01")

        assert isinstance(result, list)
        assert len(result) == 3

    @responses.activate
    def test_get_children_empty(self, api):
        """Test getting children when none exist."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ABC123/children",
            json=[],
            status=200
        )

        result = api.get_item_children("ABC123")

        assert result == []

    @responses.activate
    def test_get_children_group_library(self, api, item_with_children):
        """Test getting children from group library."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/groups/99999/items/PARENT01/children",
            json=item_with_children["children"],
            status=200
        )

        result = api.get_item_children("PARENT01", library_id="99999")

        assert len(result) == 3


class TestGetPdfAttachments:
    """Tests for the get_pdf_attachments method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_filters_pdf_attachments(self, api, item_with_children):
        """Test that only PDF attachments are returned."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/PARENT01/children",
            json=item_with_children["children"],
            status=200
        )

        result = api.get_pdf_attachments("PARENT01")

        # Should only include the PDF attachment, not the note or URL
        assert len(result) == 1
        assert result[0]["data"]["contentType"] == "application/pdf"


class TestGetFileAttachments:
    """Tests for the get_file_attachments method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_filters_multiple_types(self, api):
        """Test filtering multiple file types."""
        children = [
            {"data": {"itemType": "attachment", "contentType": "application/pdf"}},
            {"data": {"itemType": "attachment", "contentType": "application/epub+zip"}},
            {"data": {"itemType": "attachment", "contentType": "text/html"}},
            {"data": {"itemType": "note"}},
        ]
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ABC123/children",
            json=children,
            status=200
        )

        result = api.get_file_attachments("ABC123", file_types=["pdf", "epub"])

        assert len(result) == 2

    @responses.activate
    def test_filters_pdf_only(self, api):
        """Test filtering PDF only."""
        children = [
            {"data": {"itemType": "attachment", "contentType": "application/pdf"}},
            {"data": {"itemType": "attachment", "contentType": "application/epub+zip"}},
        ]
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ABC123/children",
            json=children,
            status=200
        )

        result = api.get_file_attachments("ABC123", file_types=["pdf"])

        assert len(result) == 1
        assert result[0]["data"]["contentType"] == "application/pdf"


class TestGetCollections:
    """Tests for the get_collections method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_get_collections_personal_library(self, api, nested_collections):
        """Test getting collections from personal library."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/collections",
            json=nested_collections,
            status=200
        )

        result = api.get_collections()

        assert len(result) == 5

    @responses.activate
    def test_get_collections_group_library(self, api, nested_collections):
        """Test getting collections from group library."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/groups/12345/collections",
            json=nested_collections,
            status=200
        )

        result = api.get_collections(library_id="12345")

        assert len(result) == 5

    @responses.activate
    def test_get_collections_empty(self, api):
        """Test getting collections when none exist."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/collections",
            json=[],
            status=200
        )

        result = api.get_collections()

        assert result == []


class TestGetLibraries:
    """Tests for the get_libraries method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_get_libraries(self, api, group_libraries):
        """Test getting group libraries."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/groups",
            json=group_libraries["groups"],
            status=200
        )

        result = api.get_libraries()

        assert len(result) == 2

    @responses.activate
    def test_get_libraries_empty(self, api):
        """Test getting libraries when none exist."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/groups",
            json=[],
            status=200
        )

        result = api.get_libraries()

        assert result == []


class TestGetItems:
    """Tests for the get_items method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_get_items_with_limit(self, api, journal_article, book_item):
        """Test getting items with limit."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items?limit=10",
            json=[journal_article, book_item],
            status=200
        )

        result = api.get_items(limit=10)

        assert len(result) == 2

    @responses.activate
    def test_get_items_with_type_filter(self, api, journal_article):
        """Test getting items with type filter."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items?limit=25&itemType=journalArticle",
            json=[journal_article],
            status=200
        )

        result = api.get_items(item_type="journalArticle")

        assert len(result) == 1

    @responses.activate
    def test_get_items_group_library(self, api, journal_article):
        """Test getting items from group library."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/groups/12345/items?limit=25",
            json=[journal_article],
            status=200
        )

        result = api.get_items(library_id="12345")

        assert len(result) == 1


class TestGetAttachmentAnnotations:
    """Tests for the get_attachment_annotations method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_get_annotations_as_children(self, api, pdf_annotations):
        """Test getting annotations as children of attachment."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ATTACH01/children",
            json=pdf_annotations,
            status=200
        )

        result = api.get_attachment_annotations("ATTACH01")

        assert len(result) == len(pdf_annotations)

    @responses.activate
    def test_get_annotations_empty(self, api):
        """Test getting annotations when none exist."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ATTACH01/children",
            json=[],
            status=200
        )
        # Also mock the fallback query
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items?limit=1000&itemType=annotation",
            json=[],
            status=200
        )

        result = api.get_attachment_annotations("ATTACH01")

        assert result == []


class TestGetAllAnnotationsForItem:
    """Tests for the get_all_annotations_for_item method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_item_not_found(self, api):
        """Test when item is not found."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/NOTFOUND",
            status=404
        )

        result = api.get_all_annotations_for_item("NOTFOUND")

        assert "error" in result

    @responses.activate
    def test_returns_structured_data(self, api, journal_article, item_with_children, pdf_annotations):
        """Test that structured annotation data is returned."""
        # Mock item request
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ABC12345",
            json=journal_article,
            status=200
        )
        # Mock children request (for PDF attachments)
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ABC12345/children",
            json=[item_with_children["children"][0]],  # Just the PDF attachment
            status=200
        )
        # Mock annotations request
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ATTACH01/children",
            json=pdf_annotations,
            status=200
        )

        result = api.get_all_annotations_for_item("ABC12345")

        assert "item_id" in result
        assert "item_title" in result
        assert "item_type" in result
        assert "attachments" in result


class TestGetCollectionItems:
    """Tests for the get_collection_items method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_get_collection_items(self, api, journal_article, book_item):
        """Test getting items from a collection."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/collections/COL001/items?limit=100",
            json=[journal_article, book_item],
            status=200
        )

        result = api.get_collection_items("COL001")

        assert len(result) == 2

    @responses.activate
    def test_get_collection_items_group_library(self, api, journal_article):
        """Test getting collection items from group library."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/groups/12345/collections/COL001/items?limit=100",
            json=[journal_article],
            status=200
        )

        result = api.get_collection_items("COL001", library_id="12345")

        assert len(result) == 1


class TestGetCollectionInfo:
    """Tests for the get_collection_info method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_get_collection_info(self, api, nested_collections):
        """Test getting collection info."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/collections/COL00001",
            json=nested_collections[0],
            status=200
        )

        result = api.get_collection_info("COL00001")

        assert result is not None
        assert result["key"] == "COL00001"

    @responses.activate
    def test_get_collection_info_not_found(self, api):
        """Test getting non-existent collection."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/collections/NOTFOUND",
            status=404
        )

        result = api.get_collection_info("NOTFOUND")

        assert result is None


class TestExportItemBibtex:
    """Tests for the export_item_bibtex method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_export_bibtex(self, api):
        """Test exporting item as BibTeX."""
        bibtex = "@article{smith2023,\n  title={Test Article},\n  author={Smith, John}\n}"
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ABC123?format=bibtex",
            body=bibtex,
            status=200
        )

        result = api.export_item_bibtex("ABC123")

        assert result is not None
        assert "@article{smith2023" in result

    @responses.activate
    def test_export_bibtex_failure(self, api):
        """Test BibTeX export failure."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/NOTFOUND?format=bibtex",
            status=404
        )

        result = api.export_item_bibtex("NOTFOUND")

        assert result is None


class TestGetCitationKeyForItem:
    """Tests for the get_citation_key_for_item method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    @responses.activate
    def test_get_citation_key(self, api):
        """Test extracting citation key from BibTeX."""
        bibtex = "@article{smith2023,\n  title={Test Article},\n  author={Smith, John}\n}"
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/ABC123?format=bibtex",
            body=bibtex,
            status=200
        )

        result = api.get_citation_key_for_item("ABC123")

        assert result == "smith2023"

    @responses.activate
    def test_get_citation_key_not_found(self, api):
        """Test citation key when BibTeX export fails."""
        responses.add(
            responses.GET,
            "http://localhost:23119/api/users/0/items/NOTFOUND?format=bibtex",
            status=404
        )

        result = api.get_citation_key_for_item("NOTFOUND")

        assert result is None
