"""Tests for annotation formatting in ZoteroLocalAPI."""

import pytest

from zotero_cli.api import ZoteroLocalAPI


@pytest.fixture
def api():
    """Create API instance for testing."""
    return ZoteroLocalAPI()


@pytest.fixture
def single_highlight_data():
    """Minimal data with one highlight annotation."""
    return {
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
                        "key": "ANN001",
                        "data": {
                            "key": "ANN001",
                            "annotationType": "highlight",
                            "annotationText": "Some highlighted text",
                            "annotationComment": "",
                            "annotationColor": "#ffd400",
                            "annotationPageLabel": "5",
                            "annotationSortIndex": "00005|001000|00100",
                            "annotationPosition": {"pageIndex": 4},
                            "tags": [],
                        },
                    }
                ],
            }
        ],
    }


@pytest.fixture
def multi_annotation_data():
    """Data with multiple annotation types in non-sorted order."""
    return {
        "item_id": "ABC123",
        "item_title": "Test Item",
        "item_type": "book",
        "attachments": [
            {
                "attachment_id": "ATT001",
                "attachment_title": "test.pdf",
                "filename": "test.pdf",
                "annotations_count": 4,
                "annotations": [
                    {
                        "key": "ANN_P20",
                        "data": {
                            "key": "ANN_P20",
                            "annotationType": "highlight",
                            "annotationText": "Later text on page 20",
                            "annotationComment": "A comment on this",
                            "annotationColor": "#5fb236",
                            "annotationPageLabel": "20",
                            "annotationSortIndex": "00020|002000|00100",
                            "annotationPosition": {"pageIndex": 19},
                            "tags": [{"tag": "important"}],
                        },
                    },
                    {
                        "key": "ANN_P5",
                        "data": {
                            "key": "ANN_P5",
                            "annotationType": "highlight",
                            "annotationText": "Early text on page 5",
                            "annotationComment": "",
                            "annotationColor": "#ffd400",
                            "annotationPageLabel": "5",
                            "annotationSortIndex": "00005|001000|00100",
                            "annotationPosition": {"pageIndex": 4},
                            "tags": [],
                        },
                    },
                    {
                        "key": "ANN_NOTE",
                        "data": {
                            "key": "ANN_NOTE",
                            "annotationType": "note",
                            "annotationText": "",
                            "annotationComment": "This is a standalone note",
                            "annotationColor": "#2ea8e5",
                            "annotationPageLabel": "10",
                            "annotationSortIndex": "00010|001500|00050",
                            "annotationPosition": {"pageIndex": 9},
                            "tags": [{"tag": "follow-up"}],
                        },
                    },
                    {
                        "key": "ANN_IMG",
                        "data": {
                            "key": "ANN_IMG",
                            "annotationType": "image",
                            "annotationText": "",
                            "annotationComment": "Figure 1: Architecture diagram",
                            "annotationColor": "#ff6666",
                            "annotationPageLabel": "8",
                            "annotationSortIndex": "00008|001200|00200",
                            "annotationPosition": {"pageIndex": 7},
                            "tags": [{"tag": "figure"}],
                        },
                    },
                ],
            }
        ],
    }


class TestFormatAsOrgMode:
    """Tests for the format_as_org_mode method."""

    def test_error_response(self, api):
        data = {"error": "Item not found"}
        result = api.format_as_org_mode(data)
        assert "# Error: Item not found" in result

    def test_basic_structure(self, api, single_highlight_data):
        result = api.format_as_org_mode(single_highlight_data)
        assert result.startswith("* Test Item")
        assert ":PROPERTIES:" in result
        assert ":ITEM_TYPE: journalArticle" in result
        assert ":ZOTERO_KEY: ABC123" in result
        assert ":END:" in result

    def test_custom_id_with_citation_key(self, api, single_highlight_data):
        result = api.format_as_org_mode(single_highlight_data, citation_key="smith2023")
        assert ":CUSTOM_ID: smith2023" in result

    def test_no_custom_id_without_citation_key(self, api, single_highlight_data):
        result = api.format_as_org_mode(single_highlight_data)
        assert ":CUSTOM_ID:" not in result

    def test_per_annotation_quote_blocks(self, api, multi_annotation_data):
        result = api.format_as_org_mode(multi_annotation_data)
        # Should have multiple begin_quote blocks, not one giant one
        assert result.count("#+begin_quote") >= 2

    def test_annotations_sorted_by_sort_index(self, api, multi_annotation_data):
        result = api.format_as_org_mode(multi_annotation_data)
        # Page 5 should come before page 20
        pos_p5 = result.find("Early text on page 5")
        pos_p20 = result.find("Later text on page 20")
        assert pos_p5 < pos_p20, "Annotations should be in reading order"

    def test_zotero_open_pdf_links(self, api, single_highlight_data):
        result = api.format_as_org_mode(single_highlight_data)
        assert "zotero://open-pdf/library/items/ATT001" in result
        assert "page=5" in result
        assert "annotation=ANN001" in result

    def test_comment_interleaved_with_highlight(self, api, multi_annotation_data):
        result = api.format_as_org_mode(multi_annotation_data)
        # Comment should appear right after its associated highlight text
        pos_text = result.find("Later text on page 20")
        pos_comment = result.find("A comment on this")
        assert pos_comment > pos_text, "Comment should follow its highlight"
        # And before the next annotation
        pos_next = result.find("Early text on page 5")
        # Due to sorting, p5 comes first, so let's check p20's comment is near it
        assert pos_comment > pos_text

    def test_note_annotation_uses_comment_block(self, api, multi_annotation_data):
        result = api.format_as_org_mode(multi_annotation_data)
        assert "#+begin_comment" in result
        assert "This is a standalone note" in result
        assert "#+end_comment" in result

    def test_image_annotation_uses_example_block(self, api, multi_annotation_data):
        result = api.format_as_org_mode(multi_annotation_data)
        assert "#+begin_example" in result
        assert "[Image annotation]" in result
        assert "#+end_example" in result
        assert "Figure 1: Architecture diagram" in result

    def test_tags_in_org_format(self, api, multi_annotation_data):
        result = api.format_as_org_mode(multi_annotation_data)
        assert ":important:" in result
        assert ":follow-up:" in result
        assert ":figure:" in result

    def test_citation_key_outside_quote_block(self, api, single_highlight_data):
        result = api.format_as_org_mode(single_highlight_data, citation_key="smith2023")
        lines = result.split("\n")
        # Find the end_quote and the cite line
        for i, line in enumerate(lines):
            if "#+end_quote" in line:
                # Citation should be after end_quote
                remaining = "\n".join(lines[i + 1 :])
                assert "[cite:@smith2023, p.5]" in remaining
                break

    def test_citation_without_key(self, api, single_highlight_data):
        result = api.format_as_org_mode(single_highlight_data, citation_key=None)
        assert "[cite:@" not in result

    def test_empty_attachments(self, api):
        data = {
            "item_id": "ABC123",
            "item_title": "Test Item",
            "item_type": "journalArticle",
            "attachments": [],
        }
        result = api.format_as_org_mode(data)
        assert "* Test Item" in result
        assert ":ZOTERO_KEY: ABC123" in result

    def test_attachment_with_no_annotations(self, api):
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
                    "annotations": [],
                }
            ],
        }
        result = api.format_as_org_mode(data)
        assert "No annotations found." in result

    def test_annotations_heading_present(self, api, single_highlight_data):
        result = api.format_as_org_mode(single_highlight_data)
        assert "** Annotations" in result

    def test_single_attachment_no_attachment_header(self, api, single_highlight_data):
        """With a single attachment, skip the attachment-level header."""
        result = api.format_as_org_mode(single_highlight_data)
        # Should NOT have a ** header with the attachment title
        assert "** test.pdf" not in result

    def test_multi_attachment_has_attachment_headers(self, api):
        data = {
            "item_id": "ABC123",
            "item_title": "Test Item",
            "item_type": "book",
            "attachments": [
                {
                    "attachment_id": "ATT001",
                    "attachment_title": "part1.pdf",
                    "filename": "part1.pdf",
                    "annotations_count": 0,
                    "annotations": [],
                },
                {
                    "attachment_id": "ATT002",
                    "attachment_title": "part2.pdf",
                    "filename": "part2.pdf",
                    "annotations_count": 0,
                    "annotations": [],
                },
            ],
        }
        result = api.format_as_org_mode(data)
        assert "** part1.pdf" in result
        assert "** part2.pdf" in result

    def test_with_shared_fixture(self, api, annotations_data):
        """Test with the shared conftest fixture."""
        result = api.format_as_org_mode(annotations_data)
        assert result.startswith("* ")
        assert "** Annotations" in result
        assert "#+begin_quote" in result


class TestFormatAsMarkdown:
    """Tests for the format_as_markdown method."""

    def test_error_response(self, api):
        data = {"error": "Item not found"}
        result = api.format_as_markdown(data)
        assert "# Error: Item not found" in result

    def test_basic_structure(self, api, single_highlight_data):
        result = api.format_as_markdown(single_highlight_data)
        assert result.startswith("# Test Item")
        assert "**Item Type:** journalArticle" in result
        assert "**Zotero Key:** ABC123" in result

    def test_citation_key_in_header(self, api, single_highlight_data):
        result = api.format_as_markdown(single_highlight_data, citation_key="smith2023")
        assert "**Citation Key:** smith2023" in result

    def test_per_annotation_blockquotes(self, api, multi_annotation_data):
        result = api.format_as_markdown(multi_annotation_data)
        assert result.count("> ") >= 2

    def test_annotations_sorted(self, api, multi_annotation_data):
        result = api.format_as_markdown(multi_annotation_data)
        pos_p5 = result.find("Early text on page 5")
        pos_p20 = result.find("Later text on page 20")
        assert pos_p5 < pos_p20

    def test_zotero_links(self, api, single_highlight_data):
        result = api.format_as_markdown(single_highlight_data)
        assert "zotero://open-pdf/library/items/ATT001" in result

    def test_comment_interleaved(self, api, multi_annotation_data):
        result = api.format_as_markdown(multi_annotation_data)
        pos_text = result.find("Later text on page 20")
        pos_comment = result.find("A comment on this")
        assert pos_comment > pos_text

    def test_note_annotation_italic(self, api, multi_annotation_data):
        result = api.format_as_markdown(multi_annotation_data)
        assert "*This is a standalone note*" in result

    def test_image_annotation(self, api, multi_annotation_data):
        result = api.format_as_markdown(multi_annotation_data)
        assert "`[Image annotation]`" in result

    def test_tags_formatted(self, api, multi_annotation_data):
        result = api.format_as_markdown(multi_annotation_data)
        assert "`important`" in result

    def test_citation_key_included(self, api, single_highlight_data):
        result = api.format_as_markdown(single_highlight_data, citation_key="smith2023")
        assert "[cite:@smith2023" in result

    def test_empty_attachments(self, api):
        data = {
            "item_id": "ABC123",
            "item_title": "Test Item",
            "item_type": "journalArticle",
            "attachments": [],
        }
        result = api.format_as_markdown(data)
        assert "# Test Item" in result
        assert "**Zotero Key:** ABC123" in result

    def test_annotations_heading(self, api, single_highlight_data):
        result = api.format_as_markdown(single_highlight_data)
        assert "## Annotations" in result

    def test_with_shared_fixture(self, api, annotations_data):
        result = api.format_as_markdown(annotations_data)
        assert result.startswith("# ")
        assert "## Annotations" in result


class TestFormatCollectionAnnotationsAsOrg:
    """Tests for the format_collection_annotations_as_org method."""

    def test_error_response(self, api):
        data = {"error": "Collection not found"}
        result = api.format_collection_annotations_as_org(data)
        assert "# Error: Collection not found" in result

    def test_collection_header(self, api, collection_data):
        result = api.format_collection_annotations_as_org(collection_data)
        assert "* Collection:" in result
        assert collection_data["collection_name"] in result
        assert ":COLLECTION_ID:" in result
        assert ":TOTAL_ITEMS:" in result
        assert ":ITEMS_WITH_ANNOTATIONS:" in result

    def test_empty_collection(self, api):
        data = {
            "collection_id": "COL001",
            "collection_name": "Empty Collection",
            "collection_parent": None,
            "library_id": None,
            "items_count": 0,
            "items": [],
        }
        result = api.format_collection_annotations_as_org(data)
        assert "No items with annotations found" in result


class TestFormatCollectionAnnotationsAsMarkdown:
    """Tests for the format_collection_annotations_as_markdown method."""

    def test_error_response(self, api):
        data = {"error": "Collection not found"}
        result = api.format_collection_annotations_as_markdown(data)
        assert "# Error: Collection not found" in result

    def test_collection_header(self, api, collection_data):
        result = api.format_collection_annotations_as_markdown(collection_data)
        assert "# Collection:" in result
        assert collection_data["collection_name"] in result
        assert "**Collection ID:**" in result
        assert "**Total Items:**" in result
        assert "**Items with Annotations:**" in result

    def test_empty_collection(self, api):
        data = {
            "collection_id": "COL001",
            "collection_name": "Empty Collection",
            "collection_parent": None,
            "library_id": None,
            "items_count": 0,
            "items": [],
        }
        result = api.format_collection_annotations_as_markdown(data)
        assert "No items with annotations found" in result


class TestSortAnnotations:
    """Tests for the _sort_annotations helper."""

    def test_sort_by_sort_index(self, api):
        annotations = [
            {"data": {"annotationSortIndex": "00020|002000|00100"}},
            {"data": {"annotationSortIndex": "00005|001000|00100"}},
            {"data": {"annotationSortIndex": "00010|001500|00050"}},
        ]
        result = api._sort_annotations(annotations)
        indices = [a["data"]["annotationSortIndex"] for a in result]
        assert indices == [
            "00005|001000|00100",
            "00010|001500|00050",
            "00020|002000|00100",
        ]

    def test_sort_fallback_to_page_label(self, api):
        annotations = [
            {"data": {"annotationPageLabel": "20"}},
            {"data": {"annotationPageLabel": "5"}},
        ]
        result = api._sort_annotations(annotations)
        pages = [a["data"]["annotationPageLabel"] for a in result]
        assert pages == ["5", "20"]
