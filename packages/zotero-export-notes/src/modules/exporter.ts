/**
 * Main export orchestration for PDF and EPUB annotations.
 * Supports multiple output formats: org-mode and markdown.
 */

// Supported attachment content types
const SUPPORTED_CONTENT_TYPES = [
  "application/pdf",
  "application/epub+zip",
];

import {
  AnnotationFormatter,
  ZoteroAnnotation,
} from "./annotationFormatter";
import { MetadataFormatter } from "./metadataFormatter";
import { MarkdownFormatter } from "./markdownFormatter";
import { MarkdownMetadataFormatter } from "./markdownMetadataFormatter";

export type ExportFormat = "org" | "md";

interface GenerateResult {
  content: string;
  annotationCount: number;
}

interface BatchGenerateResult {
  content: string;
  totalAnnotations: number;
  itemCount: number;
  items: Array<{
    title: string;
    citekey?: string;
    annotationCount: number;
  }>;
}

export class Exporter {
  /**
   * Export annotations from multiple items to files.
   */
  static async exportItems(
    items: Zotero.Item[],
    format: ExportFormat = "md",
  ): Promise<void> {
    for (const item of items) {
      await this.exportItem(item, format);
    }
  }

  /**
   * Copy annotations from multiple items to clipboard.
   */
  static async copyItems(
    items: Zotero.Item[],
    format: ExportFormat = "md",
  ): Promise<void> {
    let allContent = "";
    let totalAnnotations = 0;

    for (const item of items) {
      const result = await this.generateContent(item, format);
      if (result) {
        allContent += result.content;
        totalAnnotations += result.annotationCount;
        // Add separator between items if multiple
        if (items.length > 1) {
          allContent += "\n";
        }
      }
    }

    if (totalAnnotations === 0) {
      new ztoolkit.ProgressWindow(addon.data.config.addonName)
        .createLine({
          text: "No annotations found",
          type: "fail",
        })
        .show();
      return;
    }

    // Copy to clipboard
    new ztoolkit.Clipboard()
      .addText(allContent, "text/plain")
      .copy();

    const formatLabel = format === "org" ? "org-mode" : "Markdown";
    new ztoolkit.ProgressWindow(addon.data.config.addonName)
      .createLine({
        text: `Copied ${totalAnnotations} annotations as ${formatLabel}`,
        type: "success",
      })
      .show();
  }

  /**
   * Export annotations from a single item to a file.
   */
  static async exportItem(
    item: Zotero.Item,
    format: ExportFormat = "md",
  ): Promise<void> {
    const result = await this.generateContent(item, format);

    if (!result || result.annotationCount === 0) {
      return; // Error already shown by generateContent
    }

    // Get parent item for filename
    const parentItem = item.isRegularItem()
      ? item
      : item.parentItemID
        ? await Zotero.Items.getAsync(item.parentItemID)
        : null;

    // Prompt for save location
    const defaultFilename = this.generateFilename(parentItem || item, format);
    const savePath = await this.promptSaveLocation(defaultFilename, format);

    if (savePath) {
      await Zotero.File.putContentsAsync(savePath, result.content);
      new ztoolkit.ProgressWindow(addon.data.config.addonName)
        .createLine({
          text: `Exported ${result.annotationCount} annotations to ${savePath}`,
          type: "success",
        })
        .show();
    }
  }

  /**
   * Generate content for an item's annotations.
   * Returns null if no supported attachments (PDF/EPUB) found.
   */
  static async generateContent(
    item: Zotero.Item,
    format: ExportFormat = "md",
  ): Promise<GenerateResult | null> {
    // Get PDF and EPUB attachment(s)
    const attachments: Zotero.Item[] = [];

    if (item.isPDFAttachment?.() || item.isEPUBAttachment?.()) {
      attachments.push(item);
    } else if (item.isRegularItem()) {
      const attachmentIDs = item.getAttachments();
      for (const id of attachmentIDs) {
        const att = await Zotero.Items.getAsync(id);
        if (att && SUPPORTED_CONTENT_TYPES.includes(att.attachmentContentType)) {
          attachments.push(att);
        }
      }
    }

    if (attachments.length === 0) {
      new ztoolkit.ProgressWindow(addon.data.config.addonName)
        .createLine({
          text: "No PDF or EPUB attachments found",
          type: "fail",
        })
        .show();
      return null;
    }

    // Generate content
    let content = "";

    // Get parent item for metadata
    const parentItem = item.isRegularItem()
      ? item
      : item.parentItemID
        ? await Zotero.Items.getAsync(item.parentItemID)
        : null;

    if (parentItem) {
      content +=
        format === "org"
          ? MetadataFormatter.format(parentItem)
          : MarkdownMetadataFormatter.format(parentItem);
    }

    let totalAnnotations = 0;

    // Process each attachment
    for (const attachment of attachments) {
      const annotations =
        attachment.getAnnotations() as unknown as ZoteroAnnotation[];
      if (!annotations || annotations.length === 0) continue;

      totalAnnotations += annotations.length;

      // Sort by page and position
      annotations.sort((a, b) => {
        const pageA = parseInt(a.annotationPageLabel) || 0;
        const pageB = parseInt(b.annotationPageLabel) || 0;
        if (pageA !== pageB) return pageA - pageB;
        return (a.annotationSortIndex || "").localeCompare(
          b.annotationSortIndex || "",
        );
      });

      // Get data needed for formatting
      const attachmentKey = attachment.key;
      const libraryID = attachment.libraryID;
      const contentType = attachment.attachmentContentType;

      for (const annot of annotations) {
        if (format === "org") {
          content += AnnotationFormatter.format(annot, attachmentKey, libraryID, contentType);
        } else {
          content += MarkdownFormatter.format(annot, attachmentKey, libraryID, contentType);
        }
        content += "\n";
      }
    }

    if (totalAnnotations === 0) {
      new ztoolkit.ProgressWindow(addon.data.config.addonName)
        .createLine({
          text: "No annotations found",
          type: "fail",
        })
        .show();
      return null;
    }

    return {
      content,
      annotationCount: totalAnnotations,
    };
  }

  /**
   * Generate org-mode content (backwards compatibility wrapper).
   */
  static async generateOrgContent(
    item: Zotero.Item,
  ): Promise<GenerateResult | null> {
    return this.generateContent(item, "org");
  }

  /**
   * Generate content for multiple items (batch export).
   * Returns combined content with stats for each item.
   */
  static async generateBatchContent(
    items: Zotero.Item[],
    format: ExportFormat = "md",
    citekeys?: string[],
  ): Promise<BatchGenerateResult | null> {
    const itemResults: BatchGenerateResult["items"] = [];
    let allContent = "";
    let totalAnnotations = 0;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const result = await this.generateContent(item, format);

      if (result && result.annotationCount > 0) {
        // Get title
        let title = "";
        try {
          const parentItem = item.isRegularItem()
            ? item
            : item.parentItemID
              ? await Zotero.Items.getAsync(item.parentItemID)
              : null;
          title = parentItem ? (parentItem.getField("title") as string) : "";
        } catch {
          // Title not available
        }

        itemResults.push({
          title,
          citekey: citekeys?.[i],
          annotationCount: result.annotationCount,
        });

        allContent += result.content;
        totalAnnotations += result.annotationCount;

        // Add separator between items
        if (i < items.length - 1) {
          allContent += "\n";
        }
      }
    }

    if (itemResults.length === 0) {
      return null;
    }

    return {
      content: allContent,
      totalAnnotations,
      itemCount: itemResults.length,
      items: itemResults,
    };
  }

  private static generateFilename(
    item: Zotero.Item,
    format: ExportFormat = "md",
  ): string {
    let title = "annotations";
    try {
      title = (item.getField("title") as string) || "annotations";
    } catch {
      // Use default
    }
    // Sanitize filename: remove special chars, limit length
    const safeTitle = title
      .replace(/[^a-zA-Z0-9\-_\s]/g, "")
      .replace(/\s+/g, "_")
      .substring(0, 50);
    const extension = format === "org" ? ".org" : ".md";
    return `${safeTitle}${extension}`;
  }

  private static async promptSaveLocation(
    defaultFilename: string,
    format: ExportFormat = "md",
  ): Promise<string | null> {
    const extension = format === "org" ? ".org" : ".md";
    const filterLabel =
      format === "org" ? "Org Files (*.org)" : "Markdown Files (*.md)";
    const filterPattern = format === "org" ? "*.org" : "*.md";
    const dialogTitle = format === "org" ? "Save Org File" : "Save Markdown File";

    const path = await new ztoolkit.FilePicker(
      dialogTitle,
      "save",
      [[filterLabel, filterPattern]],
      defaultFilename,
    ).open();

    if (path) {
      // Ensure correct extension
      return path.endsWith(extension) ? path : path + extension;
    }
    return null;
  }
}
