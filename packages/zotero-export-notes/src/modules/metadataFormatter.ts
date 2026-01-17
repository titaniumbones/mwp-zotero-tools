/**
 * Formats Zotero item bibliographic metadata as org-mode header.
 *
 * Output format:
 * * <title>
 * :PROPERTIES:
 * :AUTHOR: <authors>
 * :DATE: <date>
 * ...
 * :END:
 *
 * ** Annotations
 */

export class MetadataFormatter {
  /**
   * Format item metadata as org file header.
   * Title becomes level 1 heading with property drawer below.
   */
  static format(item: Zotero.Item): string {
    const fields = this.extractFields(item);

    // Title as level 1 heading
    let output = "* " + (fields.title || "Untitled") + "\n";

    // Property drawer (must be immediately after heading)
    output += ":PROPERTIES:\n";

    if (fields.authors) output += `:AUTHOR: ${fields.authors}\n`;
    if (fields.date) output += `:DATE: ${fields.date}\n`;
    if (fields.publication) output += `:PUBLICATION: ${fields.publication}\n`;
    if (fields.doi) output += `:DOI: ${fields.doi}\n`;
    if (fields.url) output += `:URL: ${fields.url}\n`;
    if (fields.zoteroKey) output += `:ZOTERO_KEY: ${fields.zoteroKey}\n`;
    if (fields.citekey) output += `:CUSTOM_ID: ${fields.citekey}\n`;

    output += ":END:\n\n";

    // Abstract as separate section if available
    if (fields.abstract) {
      output += "** Abstract\n";
      output += fields.abstract + "\n\n";
    }

    // Annotations section header (level 2)
    output += "** Annotations\n\n";

    return output;
  }

  private static extractFields(
    item: Zotero.Item,
  ): Record<string, string | undefined> {
    const fields: Record<string, string | undefined> = {};

    try {
      fields.title = item.getField("title") as string;
      fields.date = item.getField("date") as string;
      fields.doi = item.getField("DOI") as string;
      fields.url = item.getField("url") as string;
      fields.abstract = item.getField("abstractNote") as string;
      fields.publication = item.getField("publicationTitle") as string;
      fields.zoteroKey = item.key;

      // Get authors
      const creators = item.getCreators() as unknown as Array<{
        creatorType?: string;
        lastName?: string;
        firstName?: string;
        name?: string;
      }>;
      if (creators && creators.length > 0) {
        fields.authors = creators
          .filter((c) => c.creatorType === "author")
          .map((c) =>
            c.lastName
              ? `${c.lastName}, ${c.firstName || ""}`
              : c.name || "",
          )
          .filter((name) => name)
          .join("; ");
      }

      // Try to get Better BibTeX citekey from extra field
      const extra = item.getField("extra") as string;
      if (extra) {
        const citekeyMatch = extra.match(/Citation Key:\s*(.+)/i);
        if (citekeyMatch) {
          fields.citekey = citekeyMatch[1].trim();
        }
      }
    } catch (e) {
      // Silently handle errors accessing fields
      ztoolkit.log("Error extracting metadata fields:", e);
    }

    return fields;
  }
}
