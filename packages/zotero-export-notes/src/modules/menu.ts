/**
 * Context menu registration for "Export Annotations".
 * Supports multiple export formats: Markdown and Org-mode.
 */

import { config } from "../../package.json";
import { Exporter } from "./exporter";

/**
 * Get the active ZoteroPane.
 */
function getZoteroPane(): _ZoteroTypes.ZoteroPane | null {
  return Zotero.getActiveZoteroPane() || null;
}

export class MenuFactory {
  /**
   * Register the right-click context menu items for library items.
   */
  static registerItemContextMenu(): void {
    const menuIcon = `chrome://${config.addonRef}/content/icons/favicon@0.5x.png`;

    // Main menu with format submenus
    ztoolkit.Menu.register("item", {
      tag: "menu",
      id: "zotero-export-notes-menu",
      label: "Export Annotations",
      icon: menuIcon,
      children: [
        // Markdown submenu
        {
          tag: "menu",
          id: "zotero-export-notes-markdown-menu",
          label: "Markdown",
          children: [
            {
              tag: "menuitem",
              id: "zotero-export-notes-md-file",
              label: "Save to File...",
              commandListener: async () => {
                const zp = getZoteroPane();
                const items = zp?.getSelectedItems();
                if (items && items.length > 0) {
                  await Exporter.exportItems(items, "md");
                }
              },
            },
            {
              tag: "menuitem",
              id: "zotero-export-notes-md-clipboard",
              label: "Copy to Clipboard",
              commandListener: async () => {
                const zp = getZoteroPane();
                const items = zp?.getSelectedItems();
                if (items && items.length > 0) {
                  await Exporter.copyItems(items, "md");
                }
              },
            },
          ],
        },
        // Org-mode submenu
        {
          tag: "menu",
          id: "zotero-export-notes-org-menu",
          label: "Org-mode",
          children: [
            {
              tag: "menuitem",
              id: "zotero-export-notes-org-file",
              label: "Save to File...",
              commandListener: async () => {
                const zp = getZoteroPane();
                const items = zp?.getSelectedItems();
                if (items && items.length > 0) {
                  await Exporter.exportItems(items, "org");
                }
              },
            },
            {
              tag: "menuitem",
              id: "zotero-export-notes-org-clipboard",
              label: "Copy to Clipboard",
              commandListener: async () => {
                const zp = getZoteroPane();
                const items = zp?.getSelectedItems();
                if (items && items.length > 0) {
                  await Exporter.copyItems(items, "org");
                }
              },
            },
          ],
        },
      ],
      getVisibility: () => {
        // Show only when items with potential PDF attachments are selected
        const zp = getZoteroPane();
        const items = zp?.getSelectedItems();
        if (!items || items.length === 0) return false;

        return items.some((item: Zotero.Item) => {
          // Show for PDF attachments
          if (item.isPDFAttachment?.()) return true;
          // Show for regular items (which may have PDF attachments)
          if (item.isRegularItem()) return true;
          return false;
        });
      },
    });
  }
}
