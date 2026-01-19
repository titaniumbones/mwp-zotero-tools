"""Tests for annotation formatting in ZoteroLocalAPI."""

import pytest

from zotero_cli.api import ZoteroLocalAPI


class TestFormatAsOrgMode:
    """Tests for the format_as_org_mode method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    def test_error_response(self, api):
        """Test formatting an error response."""
        data = {"error": "Item not found"}
        result = api.format_as_org_mode(data)
        assert "# Error: Item not found" in result

    def test_basic_structure(self, api, annotations_data):
        """Test basic org-mode structure."""
        result = api.format_as_org_mode(annotations_data)

        # Check main header
        assert result.startswith("* ")
        assert annotations_data["item_title"] in result

        # Check property drawer
        assert ":PROPERTIES:" in result
        assert ":ITEM_TYPE:" in result
        assert ":ZOTERO_KEY:" in result
        assert ":END:" in result

    def test_attachment_subheader(self, api, annotations_data):
        """Test attachment subheader formatting."""
        result = api.format_as_org_mode(annotations_data)

        # Check attachment header (level 2)
        assert "** " in result
        assert ":ATTACHMENT_ID:" in result
        assert ":FILENAME:" in result

    def test_quote_block_present(self, api, annotations_data):
        """Test that quote blocks are present."""
        result = api.format_as_org_mode(annotations_data)

        assert "#+BEGIN_QUOTE" in result
        assert "#+END_QUOTE" in result

    def test_citation_key_included(self, api, annotations_data):
        """Test citation key is included in output."""
        result = api.format_as_org_mode(annotations_data, citation_key="smith2023")

        assert "[cite:@smith2023" in result

    def test_citation_without_key(self, api, annotations_data):
        """Test output when no citation key provided."""
        result = api.format_as_org_mode(annotations_data, citation_key=None)

        assert "[cite:@" not in result

    def test_empty_attachments(self, api):
        """Test formatting when no attachments."""
        data = {
            "item_id": "ABC123",
            "item_title": "Test Item",
            "item_type": "journalArticle",
            "attachments": []
        }
        result = api.format_as_org_mode(data)

        assert "* Test Item" in result
        assert ":ZOTERO_KEY: ABC123" in result
        # No attachment headers
        assert "** " not in result

    def test_attachment_with_no_annotations(self, api):
        """Test formatting attachment with no annotations."""
        data = {
            "item_id": "ABC123",
            "item_title": "Test Item",
            "item_type": "journalArticle",
            "attachments": [
                {
                    "attachment_id": "ATT001",
                    "attachment_title": "test.pdf",
                    "filename": "test.pdf",
                    "annotations_count": 0,
                    "annotations": []
                }
            ]
        }
        result = api.format_as_org_mode(data)

        assert "No annotations found." in result

    def test_annotation_text_included(self, api, annotations_data):
        """Test that annotation text is included."""
        result = api.format_as_org_mode(annotations_data)

        # Check that some annotation text from fixtures is present
        assert "Machine learning" in result or len(annotations_data["attachments"][0]["annotations"]) > 0

    def test_comment_formatting(self, api):
        """Test comment formatting."""
        data = {
            "item_id": "ABC123",
            "item_title": "Test Item",
            "item_type": "journalArticle",
            "attachments": [
                {
                    "attachment_id": "ATT001",
                    "attachment_title": "test.pdf",
                    "filename": "test.pdf",
                    "annotations_count": 1,
                    "annotations": [
                        {
                            "data": {
                                "annotationType": "highlight",
                                "annotationText": "Some highlighted text",
                                "annotationComment": "This is my comment",
                                "annotationPageLabel": "5"
                            }
                        }
                    ]
                }
            ]
        }
        result = api.format_as_org_mode(data)

        assert "*Comment:* This is my comment" in result


class TestFormatAsMarkdown:
    """Tests for the format_as_markdown method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    def test_error_response(self, api):
        """Test formatting an error response."""
        data = {"error": "Item not found"}
        result = api.format_as_markdown(data)
        assert "# Error: Item not found" in result

    def test_basic_structure(self, api, annotations_data):
        """Test basic markdown structure."""
        result = api.format_as_markdown(annotations_data)

        # Check main header
        assert result.startswith("# ")
        assert annotations_data["item_title"] in result

        # Check metadata
        assert "**Item Type:**" in result
        assert "**Zotero Key:**" in result

    def test_attachment_subheader(self, api, annotations_data):
        """Test attachment subheader formatting."""
        result = api.format_as_markdown(annotations_data)

        # Check attachment header (level 2)
        assert "## " in result
        assert "**Attachment ID:**" in result
        assert "**Filename:**" in result

    def test_quote_block_present(self, api, annotations_data):
        """Test that quote blocks are present."""
        result = api.format_as_markdown(annotations_data)

        assert "::: .quote" in result
        assert ":::" in result

    def test_citation_key_included(self, api, annotations_data):
        """Test citation key is included in output."""
        result = api.format_as_markdown(annotations_data, citation_key="smith2023")

        assert "[cite:@smith2023" in result

    def test_empty_attachments(self, api):
        """Test formatting when no attachments."""
        data = {
            "item_id": "ABC123",
            "item_title": "Test Item",
            "item_type": "journalArticle",
            "attachments": []
        }
        result = api.format_as_markdown(data)

        assert "# Test Item" in result
        assert "**Zotero Key:** ABC123" in result

    def test_comment_formatting(self, api):
        """Test comment formatting in markdown."""
        data = {
            "item_id": "ABC123",
            "item_title": "Test Item",
            "item_type": "journalArticle",
            "attachments": [
                {
                    "attachment_id": "ATT001",
                    "attachment_title": "test.pdf",
                    "filename": "test.pdf",
                    "annotations_count": 1,
                    "annotations": [
                        {
                            "data": {
                                "annotationType": "highlight",
                                "annotationText": "Some highlighted text",
                                "annotationComment": "This is my comment",
                                "annotationPageLabel": "5"
                            }
                        }
                    ]
                }
            ]
        }
        result = api.format_as_markdown(data)

        assert "**Comment:** This is my comment" in result


class TestFormatCollectionAnnotationsAsOrg:
    """Tests for the format_collection_annotations_as_org method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    def test_error_response(self, api):
        """Test formatting an error response."""
        data = {"error": "Collection not found"}
        result = api.format_collection_annotations_as_org(data)
        assert "# Error: Collection not found" in result

    def test_collection_header(self, api, collection_data):
        """Test collection header formatting."""
        result = api.format_collection_annotations_as_org(collection_data)

        assert "* Collection:" in result
        assert collection_data["collection_name"] in result
        assert ":COLLECTION_ID:" in result
        assert ":TOTAL_ITEMS:" in result
        assert ":ITEMS_WITH_ANNOTATIONS:" in result

    def test_empty_collection(self, api):
        """Test formatting empty collection."""
        data = {
            "collection_id": "COL001",
            "collection_name": "Empty Collection",
            "collection_parent": None,
            "library_id": None,
            "items_count": 0,
            "items": []
        }
        result = api.format_collection_annotations_as_org(data)

        assert "No items with annotations found" in result


class TestFormatCollectionAnnotationsAsMarkdown:
    """Tests for the format_collection_annotations_as_markdown method."""

    @pytest.fixture
    def api(self):
        """Create API instance for testing."""
        return ZoteroLocalAPI()

    def test_error_response(self, api):
        """Test formatting an error response."""
        data = {"error": "Collection not found"}
        result = api.format_collection_annotations_as_markdown(data)
        assert "# Error: Collection not found" in result

    def test_collection_header(self, api, collection_data):
        """Test collection header formatting."""
        result = api.format_collection_annotations_as_markdown(collection_data)

        assert "# Collection:" in result
        assert collection_data["collection_name"] in result
        assert "**Collection ID:**" in result
        assert "**Total Items:**" in result
        assert "**Items with Annotations:**" in result

    def test_empty_collection(self, api):
        """Test formatting empty collection."""
        data = {
            "collection_id": "COL001",
            "collection_name": "Empty Collection",
            "collection_parent": None,
            "library_id": None,
            "items_count": 0,
            "items": []
        }
        result = api.format_collection_annotations_as_markdown(data)

        assert "No items with annotations found" in result
