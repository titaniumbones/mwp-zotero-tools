/**
 * Unit tests for AnnotationFormatter.
 */

import { assert } from "chai";
import { AnnotationFormatter } from "../../src/modules/annotationFormatter.js";
import { createMockAnnotation, loadPdfAnnotations } from "../fixtures/index.js";

describe("AnnotationFormatter", function () {
  const attachmentKey = "ATTACH01";
  const libraryID = 1;

  describe("format highlight", function () {
    it("should format highlight with quote block", function () {
      const annotation = createMockAnnotation({
        annotationType: "highlight",
        annotationText: "This is highlighted text",
        annotationPageLabel: "5",
        key: "ANNOT001",
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        libraryID,
      );

      assert.include(result, "#+begin_quote");
      assert.include(result, "This is highlighted text");
      assert.include(result, "#+end_quote");
    });

    it("should include Zotero link with page number", function () {
      const annotation = createMockAnnotation({
        annotationType: "highlight",
        annotationPageLabel: "10",
        key: "ANNOT002",
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        libraryID,
      );

      assert.include(result, "zotero://open-pdf/library/items/ATTACH01");
      assert.include(result, "page=10");
      assert.include(result, "annotation=ANNOT002");
      assert.include(result, "[Page 10]");
    });

    it("should include comment if present", function () {
      const annotation = createMockAnnotation({
        annotationType: "highlight",
        annotationText: "Highlighted text",
        annotationComment: "This is my comment",
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        libraryID,
      );

      assert.include(result, "This is my comment");
    });

    it("should format tags in org-mode style", function () {
      const annotation = createMockAnnotation({
        annotationType: "highlight",
        tags: [{ tag: "important" }, { tag: "review later" }],
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        libraryID,
      );

      assert.include(result, ":important:");
      assert.include(result, "review_later");
    });
  });

  describe("format underline", function () {
    it("should format underline same as highlight", function () {
      const annotation = createMockAnnotation({
        annotationType: "underline",
        annotationText: "Underlined text",
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        libraryID,
      );

      assert.include(result, "#+begin_quote");
      assert.include(result, "Underlined text");
      assert.include(result, "#+end_quote");
    });
  });

  describe("format note", function () {
    it("should format note with comment block", function () {
      const annotation = createMockAnnotation({
        annotationType: "note",
        annotationComment: "This is a standalone note",
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        libraryID,
      );

      assert.include(result, "#+begin_comment");
      assert.include(result, "This is a standalone note");
      assert.include(result, "#+end_comment");
    });
  });

  describe("format image", function () {
    it("should format image with example block and placeholder", function () {
      const annotation = createMockAnnotation({
        annotationType: "image",
        annotationPageLabel: "8",
        annotationComment: "Figure caption",
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        libraryID,
      );

      assert.include(result, "#+begin_example");
      assert.include(result, "[Image annotation at 8]");
      assert.include(result, "#+end_example");
      assert.include(result, "Figure caption");
    });
  });

  describe("format ink", function () {
    it("should format ink with example block and placeholder", function () {
      const annotation = createMockAnnotation({
        annotationType: "ink",
        annotationPageLabel: "12",
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        libraryID,
      );

      assert.include(result, "#+begin_example");
      assert.include(result, "[Ink/drawing annotation at 12]");
      assert.include(result, "#+end_example");
    });
  });

  describe("EPUB support", function () {
    it("should generate epub link for epub attachments", function () {
      const annotation = createMockAnnotation({
        annotationType: "highlight",
        annotationPageLabel: "Chapter 3",
        key: "EPUBANOT",
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        libraryID,
        "application/epub+zip",
      );

      assert.include(result, "zotero://open-epub/library/items/ATTACH01");
      assert.include(result, "annotation=EPUBANOT");
      assert.include(result, "[Chapter 3]");
      assert.notInclude(result, "page=");
    });
  });

  describe("group library support", function () {
    it("should use groups path for non-personal library", function () {
      const annotation = createMockAnnotation({
        annotationType: "highlight",
      });

      const result = AnnotationFormatter.format(
        annotation,
        attachmentKey,
        12345, // Group library ID
      );

      assert.include(result, "zotero://open-pdf/groups/12345/items/");
    });
  });

  describe("with fixture data", function () {
    it("should format annotations from fixture", function () {
      const annotations = loadPdfAnnotations();
      assert.isAbove(annotations.length, 0);

      for (const annotation of annotations) {
        const result = AnnotationFormatter.format(
          annotation,
          attachmentKey,
          libraryID,
        );

        // Should produce valid output
        assert.isString(result);
        assert.isAbove(result.length, 0);
        // Should contain a Zotero link
        assert.include(result, "zotero://");
      }
    });
  });
});
