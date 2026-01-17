/**
 * Formats Zotero item bibliographic metadata as markdown with YAML frontmatter.
 *
 * Output format:
 * ---
 * title: "Title"
 * author: "Author"
 * date: "2024"
 * ...
 * ---
 *
 * ## Abstract
 * <abstract text>
 *
 * ## Annotations
 */

export class MarkdownMetadataFormatter {
  /**
   * Format item metadata as markdown file header with YAML frontmatter.
   */
  static format(item: Zotero.Item): string {
    const fields = this.extractFields(item);

    // YAML frontmatter
    let output = "---\n";

    if (fields.title) output += `title: "${this.escapeYaml(fields.title)}"\n`;
    if (fields.authors) output += `author: "${this.escapeYaml(fields.authors)}"\n`;
    if (fields.date) output += `date: "${this.escapeYaml(fields.date)}"\n`;
    if (fields.publication) output += `publication: "${this.escapeYaml(fields.publication)}"\n`;
    if (fields.doi) output += `doi: "${this.escapeYaml(fields.doi)}"\n`;
    if (fields.url) output += `url: "${this.escapeYaml(fields.url)}"\n`;
    if (fields.zoteroKey) output += `zotero_key: "${fields.zoteroKey}"\n`;
    if (fields.citekey) output += `citekey: "${fields.citekey}"\n`;

    output += "---\n\n";

    // Title as H1 heading
    output += "# " + (fields.title || "Untitled") + "\n\n";

    // Abstract as separate section if available
    if (fields.abstract) {
      output += "## Abstract\n\n";
      output += fields.abstract + "\n\n";
    }

    // Annotations section header
    output += "## Annotations\n\n";

    return output;
  }

  /**
   * Escape special characters for YAML strings.
   */
  private static escapeYaml(str: string): string {
    // Escape quotes and backslashes
    return str.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
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
