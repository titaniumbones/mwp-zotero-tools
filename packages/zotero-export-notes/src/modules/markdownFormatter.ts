/**
 * Formats Zotero annotations as markdown blocks.
 *
 * Annotation type mapping:
 * - highlight, underline -> blockquote (> text)
 * - note -> paragraph
 * - image, ink -> placeholder text
 *
 * Links use Zotero protocols:
 * - PDF: zotero://open-pdf/library/items/KEY?page=N&annotation=ANNOT_KEY
 * - EPUB: zotero://open-epub/library/items/KEY?annotation=ANNOT_KEY
 */

import { ZoteroAnnotation } from "./annotationFormatter";

/**
 * Generate Zotero link for an annotation in markdown format.
 * Supports both PDF and EPUB attachments.
 */
function generateZoteroLink(
  attachmentKey: string,
  libraryID: number,
  annotation: ZoteroAnnotation,
  contentType: string,
): string {
  const annotKey = annotation.key;
  const libraryPath = libraryID === 1 ? "library" : `groups/${libraryID}`;

  if (contentType === "application/epub+zip") {
    // EPUB: Use location label as-is
    const location = annotation.annotationPageLabel || "Location";
    const url = `zotero://open-epub/${libraryPath}/items/${attachmentKey}?annotation=${annotKey}`;
    return `[${location}](${url})`;
  } else {
    // PDF: Use numeric page
    const page = parseInt(annotation.annotationPageLabel) || 1;
    const url = `zotero://open-pdf/${libraryPath}/items/${attachmentKey}?page=${page}&annotation=${annotKey}`;
    return `[Page ${page}](${url})`;
  }
}

export class MarkdownFormatter {
  /**
   * Format a single annotation as markdown text.
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
    const link = generateZoteroLink(attachmentKey, libraryID, annot, contentType);
    const text = annot.annotationText || "";
    const comment = annot.annotationComment;
    const tags = this.formatTags(annot);

    let output = "";

    // Link first
    output += link + "\n\n";

    // Blockquote for highlighted/underlined text
    const quotedLines = text
      .trim()
      .split("\n")
      .map((line) => "> " + line)
      .join("\n");
    output += quotedLines + "\n";

    // Comment as separate paragraph
    if (comment && comment.trim()) {
      output += "\n" + comment.trim() + "\n";
    }

    // Tags as hashtags
    if (tags) {
      output += "\n" + tags + "\n";
    }

    return output;
  }

  private static formatNote(
    annot: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string,
  ): string {
    const link = generateZoteroLink(attachmentKey, libraryID, annot, contentType);
    const comment = annot.annotationComment || "";
    const tags = this.formatTags(annot);

    let output = "";

    // Link first
    output += link + "\n\n";

    // Note content as paragraph
    output += comment.trim() + "\n";

    if (tags) {
      output += "\n" + tags + "\n";
    }

    return output;
  }

  private static formatImage(
    annot: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string,
  ): string {
    const link = generateZoteroLink(attachmentKey, libraryID, annot, contentType);
    const comment = annot.annotationComment;
    const location = annot.annotationPageLabel;
    const tags = this.formatTags(annot);

    let output = "";

    output += link + "\n\n";
    output += `*[Image annotation at ${location}]*\n`;

    if (comment && comment.trim()) {
      output += "\n" + comment.trim() + "\n";
    }

    if (tags) {
      output += "\n" + tags + "\n";
    }

    return output;
  }

  private static formatInk(
    annot: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string,
  ): string {
    const link = generateZoteroLink(attachmentKey, libraryID, annot, contentType);
    const comment = annot.annotationComment;
    const location = annot.annotationPageLabel;
    const tags = this.formatTags(annot);

    let output = "";

    output += link + "\n\n";
    output += `*[Ink/drawing annotation at ${location}]*\n`;

    if (comment && comment.trim()) {
      output += "\n" + comment.trim() + "\n";
    }

    if (tags) {
      output += "\n" + tags + "\n";
    }

    return output;
  }

  private static formatGeneric(
    annot: ZoteroAnnotation,
    attachmentKey: string,
    libraryID: number,
    contentType: string,
  ): string {
    const link = generateZoteroLink(attachmentKey, libraryID, annot, contentType);
    const text = annot.annotationText || annot.annotationComment || "";

    return `${link}\n\n${text.trim()}\n`;
  }

  private static formatTags(annot: ZoteroAnnotation): string {
    const tags = annot.getTags();
    if (!tags || tags.length === 0) return "";

    // Markdown tag format: #tag1 #tag2 #tag3
    return tags
      .map((t) => "#" + t.tag.replace(/\s+/g, "_").replace(/#/g, ""))
      .join(" ");
  }
}
