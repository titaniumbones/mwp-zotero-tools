/**
 * Formats Zotero annotations as org-mode blocks.
 *
 * Annotation type mapping:
 * - highlight, underline → #+begin_quote / #+end_quote
 * - note → #+begin_comment / #+end_comment
 * - image, ink → #+begin_example with placeholder
 *
 * Links use Zotero protocols:
 * - PDF: [[zotero://open-pdf/library/items/KEY?page=N&annotation=ANNOT_KEY][Page N]]:
 * - EPUB: [[zotero://open-epub/library/items/KEY?annotation=ANNOT_KEY][Location]]:
 */

export interface ZoteroAnnotation {
  annotationType: "highlight" | "underline" | "note" | "image" | "ink";
  annotationText?: string;
  annotationComment?: string;
  annotationPageLabel: string;
  annotationPosition: string;
  annotationColor?: string;
  annotationSortIndex?: string;
  key: string;
  getTags(): Array<{ tag: string }>;
}

/**
 * Generate Zotero link for an annotation in org-mode format.
 * Supports both PDF and EPUB attachments.
 */
function generateZoteroOrgLink(
  attachmentKey: string,
  libraryID: number,
  annotation: ZoteroAnnotation,
  contentType: string,
): string {
  const annotKey = annotation.key;
  const libraryPath = libraryID === 1 ? "library" : `groups/${libraryID}`;

  if (contentType === "application/epub+zip") {
    // EPUB: Use location label as-is (may be chapter or EPUBCFI)
    const location = annotation.annotationPageLabel || "Location";
    const url = `zotero://open-epub/${libraryPath}/items/${attachmentKey}?annotation=${annotKey}`;
    return `[[${url}][${location}]]:`;
  } else {
    // PDF: Use numeric page
    const page = parseInt(annotation.annotationPageLabel) || 1;
    const url = `zotero://open-pdf/${libraryPath}/items/${attachmentKey}?page=${page}&annotation=${annotKey}`;
    return `[[${url}][Page ${page}]]:`;
  }
}

export class AnnotationFormatter {
  /**
   * Format a single annotation as org-mode text.
   * Output order: link (with colon), block, optional comment, optional tags.
   */
  static format(
    annotation: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string = "application/pdf",
  ): string {
    const type = annotation.annotationType;

    switch (type) {
      case "highlight":
      case "underline":
        return this.formatHighlight(annotation, attachmentKey, libraryID, contentType);
      case "note":
        return this.formatNote(annotation, attachmentKey, libraryID, contentType);
      case "image":
        return this.formatImage(annotation, attachmentKey, libraryID, contentType);
      case "ink":
        return this.formatInk(annotation, attachmentKey, libraryID, contentType);
      default:
        return this.formatGeneric(annotation, attachmentKey, libraryID, contentType);
    }
  }

  private static formatHighlight(
    annot: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string,
  ): string {
    const link = generateZoteroOrgLink(attachmentKey, libraryID, annot, contentType);
    const text = annot.annotationText || "";
    const comment = annot.annotationComment;
    const tags = this.formatTags(annot);

    let output = "";

    // Link first (above the block)
    output += link + "\n";

    // Quote block for highlighted/underlined text
    output += "#+begin_quote\n";
    output += text.trim() + "\n";
    output += "#+end_quote\n";

    // Comment as separate paragraph (below block)
    if (comment && comment.trim()) {
      output += "\n" + comment.trim() + "\n";
    }

    // Tags on their own line
    if (tags) {
      output += tags + "\n";
    }

    return output;
  }

  private static formatNote(
    annot: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string,
  ): string {
    const link = generateZoteroOrgLink(attachmentKey, libraryID, annot, contentType);
    const comment = annot.annotationComment || "";
    const tags = this.formatTags(annot);

    let output = "";

    // Link first
    output += link + "\n";

    // Comment block for standalone notes
    output += "#+begin_comment\n";
    output += comment.trim() + "\n";
    output += "#+end_comment\n";

    if (tags) {
      output += tags + "\n";
    }

    return output;
  }

  private static formatImage(
    annot: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string,
  ): string {
    const link = generateZoteroOrgLink(attachmentKey, libraryID, annot, contentType);
    const comment = annot.annotationComment;
    const location = annot.annotationPageLabel;
    const tags = this.formatTags(annot);

    let output = "";

    output += link + "\n";
    output += "#+begin_example\n";
    output += `[Image annotation at ${location}]\n`;
    output += "#+end_example\n";

    if (comment && comment.trim()) {
      output += "\n" + comment.trim() + "\n";
    }

    if (tags) {
      output += tags + "\n";
    }

    return output;
  }

  private static formatInk(
    annot: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string,
  ): string {
    const link = generateZoteroOrgLink(attachmentKey, libraryID, annot, contentType);
    const comment = annot.annotationComment;
    const location = annot.annotationPageLabel;
    const tags = this.formatTags(annot);

    let output = "";

    output += link + "\n";
    output += "#+begin_example\n";
    output += `[Ink/drawing annotation at ${location}]\n`;
    output += "#+end_example\n";

    if (comment && comment.trim()) {
      output += "\n" + comment.trim() + "\n";
    }

    if (tags) {
      output += tags + "\n";
    }

    return output;
  }

  private static formatGeneric(
    annot: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string,
  ): string {
    const link = generateZoteroOrgLink(attachmentKey, libraryID, annot, contentType);
    const text = annot.annotationText || annot.annotationComment || "";

    return `${link}\n${text.trim()}\n`;
  }

  private static formatTags(annot: ZoteroAnnotation): string {
    const tags = annot.getTags();
    if (!tags || tags.length === 0) return "";

    // Org-mode tag format: :tag1:tag2:tag3:
    const tagStr = tags
      .map((t) => t.tag.replace(/\s+/g, "_").replace(/:/g, "-"))
      .join(":");
    return `:${tagStr}:`;
  }
}
