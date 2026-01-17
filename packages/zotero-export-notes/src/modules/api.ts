/**
 * Zotero Export Org Notes - HTTP API Reference
 * ============================================
 *
 * This plugin exposes HTTP endpoints for programmatic access to Zotero annotations.
 * Base URL: http://localhost:<port> (default port: 23119, dev: 23124)
 *
 * ## Available Endpoints
 *
 * ### 1. POST /export-org/citekey - Export annotations by citation key
 * Retrieves annotations for items by Better BibTeX citation key.
 *
 * Request (single item):
 *   {"key": "smith2020", "libraryID": 1, "format": "md"}
 *
 * Request (batch):
 *   {"keys": ["smith2020", "jones2021"], "libraryID": 1, "format": "org"}
 *
 * Parameters:
 *   - key (string): Single citation key
 *   - keys (string[]): Array of citation keys for batch export
 *   - libraryID (number, optional): Library ID (default: user library)
 *   - format ("org"|"md", optional): Output format (default: "md")
 *
 * Response:
 *   {
 *     "success": true,
 *     "citekey": "smith2020",
 *     "title": "Paper Title",
 *     "annotationCount": 15,
 *     "format": "md",
 *     "content": "...formatted annotations..."
 *   }
 *
 * ### 2. GET/POST /export-org/libraries - List available libraries
 * Returns all Zotero libraries (user and group).
 *
 * Response:
 *   {
 *     "success": true,
 *     "libraries": [
 *       {"id": 1, "name": "My Library", "type": "user"},
 *       {"id": 2, "name": "Lab Group", "type": "group"}
 *     ]
 *   }
 *
 * ### 3. GET/POST /export-org/picker - Get selected item's citekey
 * Returns the citation key of the currently selected item in Zotero UI.
 * Focuses Zotero window. Requires Better BibTeX.
 *
 * Response:
 *   {"success": true, "citekey": "smith2020", "itemKey": "ABC12345"}
 *
 * ### 4. GET/POST /export-org/collections - List collections (flat)
 * Returns all collections in a library as a flat list.
 *
 * Request (optional):
 *   {"libraryID": 1}
 *
 * Response:
 *   {
 *     "success": true,
 *     "libraryID": 1,
 *     "collections": [
 *       {"key": "ABC123", "name": "Papers", "parentKey": null},
 *       {"key": "DEF456", "name": "AI", "parentKey": "ABC123"}
 *     ]
 *   }
 *
 * ### 5. POST /export-org/collection - Export annotations from collection
 * Exports all annotations from items in a collection.
 *
 * Request:
 *   {
 *     "collectionKey": "ABC123",
 *     "libraryID": 1,
 *     "recursive": true,
 *     "format": "md"
 *   }
 *
 * Parameters:
 *   - collectionKey (string): Collection key
 *   - libraryID (number, optional): Library ID
 *   - recursive (boolean, optional): Include subcollections (default: false)
 *   - format ("org"|"md", optional): Output format (default: "md")
 *
 * Response:
 *   {
 *     "success": true,
 *     "collectionName": "AI Papers",
 *     "collectionKey": "ABC123",
 *     "recursive": true,
 *     "itemCount": 5,
 *     "totalAnnotations": 42,
 *     "format": "md",
 *     "content": "...formatted annotations...",
 *     "items": [{"title": "Paper 1", "annotationCount": 10}, ...]
 *   }
 *
 * ### 6. GET /export-org/collection/current - Get current UI selection
 * Returns the currently selected library and collection in Zotero's UI.
 *
 * Response (collection selected):
 *   {
 *     "libraryID": 1,
 *     "libraryName": "My Library",
 *     "libraryType": "user",
 *     "collection": {
 *       "key": "ABC123",
 *       "name": "AI Papers",
 *       "parentKey": "XYZ789"
 *     }
 *   }
 *
 * Response (library root selected):
 *   {
 *     "libraryID": 1,
 *     "libraryName": "My Library",
 *     "libraryType": "user",
 *     "collection": null
 *   }
 *
 * ### 7. POST /export-org/collection/select - Select library/collection in UI
 * Programmatically selects a library or collection in Zotero's collections pane.
 *
 * Request (select collection):
 *   {"libraryID": 1, "collectionKey": "ABC123"}
 *
 * Request (select library root):
 *   {"libraryID": 1, "collectionKey": null}
 *
 * Parameters:
 *   - libraryID (number, required): Target library ID
 *   - collectionKey (string|null): Collection key, or null for library root
 *
 * Response:
 *   {
 *     "success": true,
 *     "selected": {
 *       "libraryID": 1,
 *       "collectionKey": "ABC123",
 *       "collectionName": "AI Papers"
 *     }
 *   }
 *
 * ### 8. GET /export-org/collections/list - List all collections (hierarchical)
 * Returns all libraries with their collections as a nested tree structure.
 *
 * Response:
 *   {
 *     "libraries": [
 *       {
 *         "id": 1,
 *         "name": "My Library",
 *         "type": "user",
 *         "collections": [
 *           {
 *             "key": "ABC123",
 *             "name": "Research",
 *             "parentKey": null,
 *             "children": [
 *               {
 *                 "key": "DEF456",
 *                 "name": "AI Papers",
 *                 "parentKey": "ABC123",
 *                 "children": []
 *               }
 *             ]
 *           }
 *         ]
 *       },
 *       {
 *         "id": 5,
 *         "name": "Lab Group",
 *         "type": "group",
 *         "collections": [...]
 *       }
 *     ]
 *   }
 *
 * ## Output Formats
 *
 * - "md" (default): Markdown with blockquotes for highlights, hashtags for tags
 * - "org": Org-mode format with properties drawer, Zotero links
 *
 * ## Zotero Links
 *
 * Generated links use Zotero protocols:
 * - PDF: zotero://open-pdf/library/items/KEY?page=N&annotation=ANNOT_KEY
 * - EPUB: zotero://open-epub/library/items/KEY?annotation=ANNOT_KEY
 *
 * ## Error Responses
 *
 * All endpoints return JSON with "success": false and "error" message on failure.
 * HTTP status codes: 400 (bad request), 404 (not found), 500 (server error)
 */

import { Exporter, ExportFormat } from "./exporter";

// Type declarations for Zotero's server system
declare const Zotero: {
  Server: {
    Endpoints: Record<string, unknown>;
  };
  Items: {
    getAll: (libraryID: number) => Zotero.Item[];
  };
  Libraries: {
    userLibraryID: number;
  };
  getMainWindow: () => { Zotero_Tabs?: unknown } | null;
  [key: string]: unknown;
};

interface ApiResponse {
  success: boolean;
  citekey?: string;
  title?: string;
  annotationCount?: number;
  format?: string;
  content?: string;
  org?: string; // Backwards compatibility
  error?: string;
  // Batch response fields
  itemCount?: number;
  totalAnnotations?: number;
  items?: Array<{
    citekey?: string;
    title: string;
    annotationCount: number;
  }>;
}

/**
 * Find a Zotero item by its citation key.
 * Uses Better BibTeX JSON-RPC API, then falls back to Extra field search.
 * @param citekey - The citation key to look up
 * @param libraryID - Optional library ID (for group libraries)
 */
async function findItemByCitekey(citekey: string, libraryID?: number): Promise<Zotero.Item | null> {
  ztoolkit.log("Looking up citekey:", citekey, "libraryID:", libraryID);

  // Try Better BibTeX JSON-RPC API
  try {
    ztoolkit.log("Trying BBT JSON-RPC API...");

    // Get the server port from Zotero preferences
    const port = (Zotero as unknown as { Prefs: { get: (key: string) => number } }).Prefs.get("httpServer.port") || 23119;
    const url = `http://localhost:${port}/better-bibtex/json-rpc`;

    // BBT item.search accepts optional library parameter
    const params: (string | number)[] = [citekey];
    if (libraryID !== undefined) {
      params.push(libraryID);
    }

    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "item.search",
        params,
        id: 1,
      }),
    });

    if (response.ok) {
      const data = await response.json() as { result?: Array<{ id?: string; itemKey?: string; libraryID?: number }> };
      ztoolkit.log("BBT JSON-RPC response:", data);

      if (data.result && data.result.length > 0) {
        const bbtItem = data.result[0];

        // Extract item key from the id URL (format: "http://zotero.org/users/XX/items/ITEMKEY")
        let itemKey = bbtItem.itemKey;
        if (!itemKey && bbtItem.id) {
          const match = bbtItem.id.match(/\/items\/([A-Z0-9]+)$/);
          if (match) {
            itemKey = match[1];
          }
        }

        if (itemKey) {
          ztoolkit.log("Found item key:", itemKey);
          const itemLibraryID = libraryID ?? bbtItem.libraryID ?? Zotero.Libraries.userLibraryID;
          const item = await (Zotero as unknown as { Items: { getByLibraryAndKeyAsync: (lib: number, key: string) => Promise<Zotero.Item | null> } })
            .Items.getByLibraryAndKeyAsync(itemLibraryID, itemKey);
          if (item) {
            ztoolkit.log("Found item via BBT:", item.getField("title"));
            return item;
          }
        }
      }
    }
  } catch (e) {
    ztoolkit.log("BBT JSON-RPC lookup failed:", e);
  }

  // Fall back to searching Extra field for "Citation Key: xxx"
  try {
    ztoolkit.log("Trying Extra field search...");
    const s = new (Zotero as unknown as { Search: new () => ZoteroSearch }).Search();
    s.addCondition("extra", "contains", citekey);
    if (libraryID !== undefined) {
      s.addCondition("libraryID", "is", String(libraryID));
    }
    const ids = await s.search();
    ztoolkit.log("Search returned ids:", ids);

    if (ids && ids.length > 0) {
      const items = await (Zotero as unknown as { Items: { getAsync: (ids: number[]) => Promise<Zotero.Item[]> } }).Items.getAsync(ids);

      // Verify exact match
      for (const item of items) {
        if (!item.isRegularItem()) continue;
        try {
          const extra = item.getField("extra") as string;
          if (extra) {
            // Check for Citation Key: pattern or just the citekey itself
            const match = extra.match(/Citation Key:\s*(.+)/i);
            if (match && match[1].trim() === citekey) {
              return item;
            }
            // Also check if citekey appears directly
            if (extra.includes(citekey)) {
              return item;
            }
          }
        } catch {
          // Skip
        }
      }
    }
  } catch (e) {
    ztoolkit.log("Extra field search failed:", e);
  }

  return null;
}

// Type for Zotero Search
interface ZoteroSearch {
  addCondition: (field: string, operator: string, value: string) => void;
  search: () => Promise<number[]>;
}

/**
 * HTTP endpoint handler for /export-org/citekey
 * Accepts POST with JSON body:
 *   Single item: {"key": "<citekey>", "libraryID": <optional>, "format": "org"|"md"}
 *   Batch: {"keys": ["<citekey1>", "<citekey2>"], "libraryID": <optional>, "format": "org"|"md"}
 * Default format is "md" (markdown).
 */
function CitekeyEndpoint() {
  // @ts-expect-error - Zotero endpoint pattern
  this.supportedMethods = ["POST"];
  // @ts-expect-error - Zotero endpoint pattern
  this.permitBookmarklet = false;

  // @ts-expect-error - Zotero endpoint pattern
  this.init = async function (
    data: unknown,
    sendResponseCallback: (
      status: number,
      contentType?: string,
      body?: string,
    ) => void,
  ) {
    // Parse citekey(s), optional libraryID, and format from POST body
    let citekey: string | undefined;
    let citekeys: string[] | undefined;
    let libraryID: number | undefined;
    let format: ExportFormat = "md"; // Default to markdown

    if (data && typeof data === "object") {
      const dataObj = data as Record<string, unknown>;
      if (typeof dataObj.key === "string") {
        citekey = dataObj.key;
      }
      if (Array.isArray(dataObj.keys)) {
        citekeys = dataObj.keys.filter((k): k is string => typeof k === "string");
      }
      if (typeof dataObj.libraryID === "number") {
        libraryID = dataObj.libraryID;
      }
      if (dataObj.format === "org" || dataObj.format === "md") {
        format = dataObj.format;
      }
    }

    // Handle batch request (array of keys)
    if (citekeys && citekeys.length > 0) {
      ztoolkit.log("API batch request, citekeys:", citekeys.length, "libraryID:", libraryID, "format:", format);

      try {
        const items: Zotero.Item[] = [];
        const resolvedCitekeys: string[] = [];
        const notFoundKeys: string[] = [];

        // Resolve each citekey to an item
        for (const key of citekeys) {
          const item = await findItemByCitekey(key, libraryID);
          if (item) {
            items.push(item);
            resolvedCitekeys.push(key);
          } else {
            notFoundKeys.push(key);
          }
        }

        if (items.length === 0) {
          const response: ApiResponse = {
            success: false,
            error: `No items found for citekeys: ${citekeys.join(", ")}`,
          };
          sendResponseCallback(404, "application/json", JSON.stringify(response));
          return;
        }

        // Generate batch content
        const result = await Exporter.generateBatchContent(items, format, resolvedCitekeys);

        if (!result) {
          const response: ApiResponse = {
            success: false,
            error: "No annotations found for any of the specified items",
          };
          sendResponseCallback(404, "application/json", JSON.stringify(response));
          return;
        }

        const response: ApiResponse = {
          success: true,
          itemCount: result.itemCount,
          totalAnnotations: result.totalAnnotations,
          format,
          content: result.content,
          items: result.items,
          // Backwards compatibility
          ...(format === "org" ? { org: result.content } : {}),
          // Include warning if some keys weren't found
          ...(notFoundKeys.length > 0 ? { error: `Items not found: ${notFoundKeys.join(", ")}` } : {}),
        };

        sendResponseCallback(200, "application/json", JSON.stringify(response));
        return;
      } catch (e) {
        const response: ApiResponse = {
          success: false,
          error: `Error processing batch request: ${e instanceof Error ? e.message : String(e)}`,
        };
        sendResponseCallback(500, "application/json", JSON.stringify(response));
        return;
      }
    }

    // Handle single item request (original behavior)
    ztoolkit.log("API request, citekey:", citekey, "libraryID:", libraryID, "format:", format);

    if (!citekey) {
      const response: ApiResponse = {
        success: false,
        error: "Missing 'key' or 'keys' parameter. Use POST with JSON body: {\"key\": \"<citekey>\"} or {\"keys\": [\"key1\", \"key2\"]}",
      };
      sendResponseCallback(400, "application/json", JSON.stringify(response));
      return;
    }

    try {
      // Find item by citekey (with optional libraryID)
      const item = await findItemByCitekey(citekey, libraryID);

      if (!item) {
        const response: ApiResponse = {
          success: false,
          error: `Item not found for citekey: ${citekey}`,
        };
        sendResponseCallback(404, "application/json", JSON.stringify(response));
        return;
      }

      // Generate content in requested format
      const result = await Exporter.generateContent(item, format);

      if (!result) {
        const response: ApiResponse = {
          success: false,
          error: `No annotations found for citekey: ${citekey}`,
        };
        sendResponseCallback(404, "application/json", JSON.stringify(response));
        return;
      }

      // Get title
      let title = "";
      try {
        title = item.getField("title") as string;
      } catch {
        // Title not available
      }

      const response: ApiResponse = {
        success: true,
        citekey,
        title,
        annotationCount: result.annotationCount,
        format,
        content: result.content,
        // Backwards compatibility: also include 'org' field when format is org
        ...(format === "org" ? { org: result.content } : {}),
      };

      sendResponseCallback(200, "application/json", JSON.stringify(response));
    } catch (e) {
      const response: ApiResponse = {
        success: false,
        error: `Error processing request: ${e instanceof Error ? e.message : String(e)}`,
      };
      sendResponseCallback(500, "application/json", JSON.stringify(response));
    }
  };
}

/**
 * HTTP endpoint handler for /export-org/libraries
 * Returns list of available Zotero libraries
 */
function LibrariesEndpoint() {
  // @ts-expect-error - Zotero endpoint pattern
  this.supportedMethods = ["GET", "POST"];
  // @ts-expect-error - Zotero endpoint pattern
  this.permitBookmarklet = false;

  // @ts-expect-error - Zotero endpoint pattern
  this.init = async function (
    _data: unknown,
    sendResponseCallback: (
      status: number,
      contentType?: string,
      body?: string,
    ) => void,
  ) {
    try {
      const libraries: Array<{ id: number; name: string; type: string }> = [];

      // Get all libraries using Zotero API
      const ZoteroLibraries = (Zotero as unknown as {
        Libraries: {
          getAll: () => Array<{ libraryID: number; name: string; libraryType: string }>;
        };
      }).Libraries;

      const allLibraries = ZoteroLibraries.getAll();

      for (const lib of allLibraries) {
        libraries.push({
          id: lib.libraryID,
          name: lib.name || (lib.libraryType === "user" ? "My Library" : `Library ${lib.libraryID}`),
          type: lib.libraryType,
        });
      }

      sendResponseCallback(200, "application/json", JSON.stringify({
        success: true,
        libraries,
      }));
    } catch (e) {
      sendResponseCallback(500, "application/json", JSON.stringify({
        success: false,
        error: `Error listing libraries: ${e instanceof Error ? e.message : String(e)}`,
      }));
    }
  };
}

/**
 * HTTP endpoint handler for /export-org/picker
 * Returns citekey of currently selected item in Zotero using BBT API
 */
function PickerEndpoint() {
  // @ts-expect-error - Zotero endpoint pattern
  this.supportedMethods = ["GET", "POST"];
  // @ts-expect-error - Zotero endpoint pattern
  this.permitBookmarklet = false;

  // @ts-expect-error - Zotero endpoint pattern
  this.init = async function (
    _data: unknown,
    sendResponseCallback: (
      status: number,
      contentType?: string,
      body?: string,
    ) => void,
  ) {
    try {
      // Focus Zotero window
      const mainWindow = Zotero.getMainWindow() as Window | null;
      if (mainWindow) {
        mainWindow.focus();
      }

      // Use BBT's item.citationkey("selected") to get citekey of selected items
      const port = (Zotero as unknown as { Prefs: { get: (key: string) => number } }).Prefs.get("httpServer.port") || 23119;
      const response = await fetch(`http://localhost:${port}/better-bibtex/json-rpc`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          method: "item.citationkey",
          params: ["selected"],
          id: 1,
        }),
      });

      if (!response.ok) {
        sendResponseCallback(500, "application/json", JSON.stringify({
          success: false,
          error: "Failed to query Better BibTeX",
        }));
        return;
      }

      const data = await response.json() as { result?: Record<string, string | null>; error?: { message: string } };

      if (data.error) {
        sendResponseCallback(500, "application/json", JSON.stringify({
          success: false,
          error: `BBT error: ${data.error.message}`,
        }));
        return;
      }

      if (!data.result || Object.keys(data.result).length === 0) {
        sendResponseCallback(200, "application/json", JSON.stringify({
          success: false,
          error: "No item selected in Zotero. Please select an item first.",
        }));
        return;
      }

      // Get the first citekey from the result
      const entries = Object.entries(data.result);
      const [itemKey, citekey] = entries[0];

      if (!citekey) {
        sendResponseCallback(200, "application/json", JSON.stringify({
          success: false,
          error: "Selected item has no citation key. Ensure Better BibTeX is configured.",
        }));
        return;
      }

      sendResponseCallback(200, "application/json", JSON.stringify({
        success: true,
        citekey,
        itemKey,
      }));
    } catch (e) {
      sendResponseCallback(500, "application/json", JSON.stringify({
        success: false,
        error: `Error in picker: ${e instanceof Error ? e.message : String(e)}`,
      }));
    }
  };
}

/**
 * HTTP endpoint handler for /export-org/collections
 * Lists all collections in a Zotero library.
 * Accepts POST with JSON body: {"libraryID": <optional>, "recursive": <optional bool>}
 */
function CollectionsListEndpoint() {
  // @ts-expect-error - Zotero endpoint pattern
  this.supportedMethods = ["GET", "POST"];
  // @ts-expect-error - Zotero endpoint pattern
  this.permitBookmarklet = false;

  // @ts-expect-error - Zotero endpoint pattern
  this.init = async function (
    data: unknown,
    sendResponseCallback: (
      status: number,
      contentType?: string,
      body?: string,
    ) => void,
  ) {
    let libraryID: number | undefined;

    if (data && typeof data === "object") {
      const dataObj = data as Record<string, unknown>;
      if (typeof dataObj.libraryID === "number") {
        libraryID = dataObj.libraryID;
      }
    }

    const targetLibraryID = libraryID ?? Zotero.Libraries.userLibraryID;

    try {
      const ZoteroCollections = (Zotero as unknown as {
        Collections: {
          getByLibrary: (libraryID: number) => Array<{
            key: string;
            name: string;
            parentKey: string | null;
          }>;
        };
      }).Collections;

      const collections = ZoteroCollections.getByLibrary(targetLibraryID);

      const result = collections.map((col) => ({
        key: col.key,
        name: col.name,
        parentKey: col.parentKey,
      }));

      sendResponseCallback(200, "application/json", JSON.stringify({
        success: true,
        libraryID: targetLibraryID,
        collections: result,
      }));
    } catch (e) {
      sendResponseCallback(500, "application/json", JSON.stringify({
        success: false,
        error: `Error listing collections: ${e instanceof Error ? e.message : String(e)}`,
      }));
    }
  };
}

/**
 * HTTP endpoint handler for /export-org/collection
 * Exports all annotations from items in a Zotero collection.
 * Accepts POST with JSON body: {"collectionID": <number>, "recursive": <bool>, "format": "org"|"md", "libraryID": <optional>}
 */
function CollectionEndpoint() {
  // @ts-expect-error - Zotero endpoint pattern
  this.supportedMethods = ["POST"];
  // @ts-expect-error - Zotero endpoint pattern
  this.permitBookmarklet = false;

  // @ts-expect-error - Zotero endpoint pattern
  this.init = async function (
    data: unknown,
    sendResponseCallback: (
      status: number,
      contentType?: string,
      body?: string,
    ) => void,
  ) {
    let collectionKey: string | undefined;
    let recursive = false;
    let libraryID: number | undefined;
    let format: ExportFormat = "md";

    if (data && typeof data === "object") {
      const dataObj = data as Record<string, unknown>;
      // Accept collectionKey (string) or collectionID (string or number for backwards compat)
      if (typeof dataObj.collectionKey === "string") {
        collectionKey = dataObj.collectionKey;
      } else if (typeof dataObj.collectionID === "string") {
        collectionKey = dataObj.collectionID;
      } else if (typeof dataObj.collectionID === "number") {
        collectionKey = String(dataObj.collectionID);
      }
      if (typeof dataObj.recursive === "boolean") {
        recursive = dataObj.recursive;
      }
      if (typeof dataObj.libraryID === "number") {
        libraryID = dataObj.libraryID;
      }
      if (dataObj.format === "org" || dataObj.format === "md") {
        format = dataObj.format;
      }
    }

    ztoolkit.log("Collection API request, collectionKey:", collectionKey, "recursive:", recursive, "format:", format);

    if (!collectionKey) {
      sendResponseCallback(400, "application/json", JSON.stringify({
        success: false,
        error: "Missing 'collectionKey' or 'collectionID' parameter. Use POST with JSON body: {\"collectionKey\": \"<key>\"}",
      }));
      return;
    }

    try {
      // Get collection by key
      const ZoteroCollections = (Zotero as unknown as {
        Collections: {
          getByLibraryAndKeyAsync: (libraryID: number, key: string) => Promise<{
            name: string;
            libraryID: number;
            getChildItems: () => Zotero.Item[];
            getDescendents: (recursive: boolean, type: string) => Array<{ type: string; id: number }>;
          } | null>;
        };
      }).Collections;

      // Use provided libraryID or default to user library
      const targetLibraryID = libraryID ?? Zotero.Libraries.userLibraryID;
      const collection = await ZoteroCollections.getByLibraryAndKeyAsync(targetLibraryID, collectionKey);

      if (!collection) {
        sendResponseCallback(404, "application/json", JSON.stringify({
          success: false,
          error: `Collection not found: ${collectionKey}`,
        }));
        return;
      }

      const collectionName = collection.name;

      // Get items from collection
      let items: Zotero.Item[] = [];

      if (recursive) {
        // Get all descendant items (recursive)
        const descendants = collection.getDescendents(true, "item");
        const itemIDs = descendants
          .filter((d: { type: string }) => d.type === "item")
          .map((d: { id: number }) => d.id);

        if (itemIDs.length > 0) {
          items = await (Zotero as unknown as {
            Items: { getAsync: (ids: number[]) => Promise<Zotero.Item[]> };
          }).Items.getAsync(itemIDs);
        }
      } else {
        // Get direct children only
        items = collection.getChildItems();
      }

      // Filter to regular items only (skip attachments, notes)
      items = items.filter((item) => item.isRegularItem());

      if (items.length === 0) {
        sendResponseCallback(200, "application/json", JSON.stringify({
          success: false,
          collectionName,
          error: "No regular items found in collection",
        }));
        return;
      }

      ztoolkit.log("Found", items.length, "items in collection", collectionName);

      // Generate batch content
      const result = await Exporter.generateBatchContent(items, format);

      if (!result) {
        sendResponseCallback(200, "application/json", JSON.stringify({
          success: false,
          collectionName,
          itemCount: items.length,
          error: "No annotations found in any items",
        }));
        return;
      }

      sendResponseCallback(200, "application/json", JSON.stringify({
        success: true,
        collectionName,
        collectionKey,
        recursive,
        itemCount: result.itemCount,
        totalAnnotations: result.totalAnnotations,
        format,
        content: result.content,
        items: result.items,
        ...(format === "org" ? { org: result.content } : {}),
      }));
    } catch (e) {
      sendResponseCallback(500, "application/json", JSON.stringify({
        success: false,
        error: `Error processing collection: ${e instanceof Error ? e.message : String(e)}`,
      }));
    }
  };
}

/**
 * HTTP endpoint handler for /export-org/collection/current
 * Returns the currently selected library and collection in Zotero's UI.
 */
function CollectionCurrentEndpoint() {
  // @ts-expect-error - Zotero endpoint pattern
  this.supportedMethods = ["GET"];
  // @ts-expect-error - Zotero endpoint pattern
  this.permitBookmarklet = false;

  // @ts-expect-error - Zotero endpoint pattern
  this.init = async function (
    _data: unknown,
    sendResponseCallback: (
      status: number,
      contentType?: string,
      body?: string,
    ) => void,
  ) {
    try {
      const zp = (Zotero as unknown as {
        getActiveZoteroPane: () => {
          getSelectedLibraryID: () => number;
          getSelectedCollection: () => { key: string; name: string; parentKey: string | null } | null;
        };
      }).getActiveZoteroPane();

      const libraryID = zp.getSelectedLibraryID();
      const library = (Zotero as unknown as {
        Libraries: {
          get: (id: number) => { name: string; libraryType: string };
        };
      }).Libraries.get(libraryID);

      const collection = zp.getSelectedCollection();

      sendResponseCallback(200, "application/json", JSON.stringify({
        libraryID,
        libraryName: library.name,
        libraryType: library.libraryType,
        collection: collection ? {
          key: collection.key,
          name: collection.name,
          parentKey: collection.parentKey || null,
        } : null,
      }));
    } catch (e) {
      sendResponseCallback(500, "application/json", JSON.stringify({
        success: false,
        error: `Error getting current selection: ${e instanceof Error ? e.message : String(e)}`,
      }));
    }
  };
}

/**
 * HTTP endpoint handler for /export-org/collection/select
 * Selects a library or collection in Zotero's UI.
 * Accepts POST with JSON body: {"libraryID": <number>, "collectionKey": "<string>" | null}
 */
function CollectionSelectEndpoint() {
  // @ts-expect-error - Zotero endpoint pattern
  this.supportedMethods = ["POST"];
  // @ts-expect-error - Zotero endpoint pattern
  this.permitBookmarklet = false;

  // @ts-expect-error - Zotero endpoint pattern
  this.init = async function (
    data: unknown,
    sendResponseCallback: (
      status: number,
      contentType?: string,
      body?: string,
    ) => void,
  ) {
    let libraryID: number | undefined;
    let collectionKey: string | null | undefined;

    if (data && typeof data === "object") {
      const dataObj = data as Record<string, unknown>;
      if (typeof dataObj.libraryID === "number") {
        libraryID = dataObj.libraryID;
      }
      if (typeof dataObj.collectionKey === "string") {
        collectionKey = dataObj.collectionKey;
      } else if (dataObj.collectionKey === null) {
        collectionKey = null;
      }
    }

    if (libraryID === undefined) {
      sendResponseCallback(400, "application/json", JSON.stringify({
        success: false,
        error: "Missing 'libraryID' parameter",
      }));
      return;
    }

    try {
      const zp = (Zotero as unknown as {
        getActiveZoteroPane: () => {
          collectionsView: {
            selectLibrary: (libraryID: number) => Promise<void>;
            selectCollection: (collectionID: number) => Promise<void>;
          };
        };
      }).getActiveZoteroPane();

      if (!collectionKey) {
        // Select library root
        await zp.collectionsView.selectLibrary(libraryID);
        sendResponseCallback(200, "application/json", JSON.stringify({
          success: true,
          selected: {
            libraryID,
            collectionKey: null,
            collectionName: null,
          },
        }));
        return;
      }

      // Select specific collection
      const ZoteroCollections = (Zotero as unknown as {
        Collections: {
          getByLibraryAndKeyAsync: (libraryID: number, key: string) => Promise<{
            id: number;
            key: string;
            name: string;
          } | null>;
        };
      }).Collections;

      const collection = await ZoteroCollections.getByLibraryAndKeyAsync(libraryID, collectionKey);

      if (!collection) {
        sendResponseCallback(404, "application/json", JSON.stringify({
          success: false,
          error: "Collection not found",
        }));
        return;
      }

      await zp.collectionsView.selectCollection(collection.id);

      sendResponseCallback(200, "application/json", JSON.stringify({
        success: true,
        selected: {
          libraryID,
          collectionKey: collection.key,
          collectionName: collection.name,
        },
      }));
    } catch (e) {
      sendResponseCallback(500, "application/json", JSON.stringify({
        success: false,
        error: `Error selecting collection: ${e instanceof Error ? e.message : String(e)}`,
      }));
    }
  };
}

/**
 * HTTP endpoint handler for /export-org/collection/create
 * Creates a new collection in a Zotero library.
 * Accepts POST with JSON body: {"libraryID": <number>, "name": "<string>", "parentKey": "<string>" | null}
 */
function CollectionCreateEndpoint() {
  // @ts-expect-error - Zotero endpoint pattern
  this.supportedMethods = ["POST"];
  // @ts-expect-error - Zotero endpoint pattern
  this.permitBookmarklet = false;

  // @ts-expect-error - Zotero endpoint pattern
  this.init = async function (
    data: unknown,
    sendResponseCallback: (
      status: number,
      contentType?: string,
      body?: string,
    ) => void,
  ) {
    let libraryID: number | undefined;
    let name: string | undefined;
    let parentKey: string | null = null;

    if (data && typeof data === "object") {
      const dataObj = data as Record<string, unknown>;
      if (typeof dataObj.libraryID === "number") {
        libraryID = dataObj.libraryID;
      }
      if (typeof dataObj.name === "string") {
        name = dataObj.name;
      }
      if (typeof dataObj.parentKey === "string") {
        parentKey = dataObj.parentKey;
      }
    }

    if (libraryID === undefined) {
      sendResponseCallback(400, "application/json", JSON.stringify({
        success: false,
        error: "Missing 'libraryID' parameter",
      }));
      return;
    }

    if (!name) {
      sendResponseCallback(400, "application/json", JSON.stringify({
        success: false,
        error: "Missing 'name' parameter",
      }));
      return;
    }

    try {
      // Create new collection using Zotero's API
      const ZoteroCollection = (Zotero as unknown as {
        Collection: new () => {
          libraryID: number;
          name: string;
          parentKey: string | null;
          saveTx: () => Promise<void>;
          key: string;
        };
      }).Collection;

      const collection = new ZoteroCollection();
      collection.libraryID = libraryID;
      collection.name = name;
      if (parentKey) {
        collection.parentKey = parentKey;
      }

      await collection.saveTx();

      sendResponseCallback(200, "application/json", JSON.stringify({
        success: true,
        collection: {
          key: collection.key,
          name: collection.name,
          libraryID: collection.libraryID,
          parentKey: collection.parentKey,
        },
      }));
    } catch (e) {
      sendResponseCallback(500, "application/json", JSON.stringify({
        success: false,
        error: `Error creating collection: ${e instanceof Error ? e.message : String(e)}`,
      }));
    }
  };
}

/**
 * Build a hierarchical tree of collections.
 */
interface CollectionTreeNode {
  key: string;
  name: string;
  parentKey: string | null;
  children: CollectionTreeNode[];
}

function buildCollectionTree(
  collections: Array<{ key: string; name: string; parentKey: string | null }>,
  parentKey: string | null = null,
): CollectionTreeNode[] {
  return collections
    .filter((c) => (c.parentKey || null) === parentKey)
    .map((c) => ({
      key: c.key,
      name: c.name,
      parentKey: c.parentKey || null,
      children: buildCollectionTree(collections, c.key),
    }));
}

/**
 * HTTP endpoint handler for /export-org/collections/list
 * Returns all libraries and their collections as a hierarchical structure.
 */
function CollectionsListHierarchicalEndpoint() {
  // @ts-expect-error - Zotero endpoint pattern
  this.supportedMethods = ["GET"];
  // @ts-expect-error - Zotero endpoint pattern
  this.permitBookmarklet = false;

  // @ts-expect-error - Zotero endpoint pattern
  this.init = async function (
    _data: unknown,
    sendResponseCallback: (
      status: number,
      contentType?: string,
      body?: string,
    ) => void,
  ) {
    try {
      const ZoteroLibraries = (Zotero as unknown as {
        Libraries: {
          getAll: () => Array<{ libraryID: number; name: string; libraryType: string }>;
        };
      }).Libraries;

      const ZoteroCollections = (Zotero as unknown as {
        Collections: {
          getByLibrary: (libraryID: number) => Array<{
            key: string;
            name: string;
            parentKey: string | null;
            deleted: boolean;
            version: number;
            synced: boolean;
          }>;
        };
      }).Collections;

      const libraries = ZoteroLibraries.getAll();

      // Include user and group libraries
      const filteredLibraries = libraries.filter(
        (lib) => lib.libraryType === "user" || lib.libraryType === "group"
      );

      const result = {
        libraries: filteredLibraries.map((lib) => {
          const collections = ZoteroCollections.getByLibrary(lib.libraryID);
          // Filter out deleted collections and log for debugging
          const visibleCollections = collections.filter((c) => !c.deleted);
          return {
            id: lib.libraryID,
            name: lib.name || (lib.libraryType === "user" ? "My Library" : `Library ${lib.libraryID}`),
            type: lib.libraryType,
            collections: buildCollectionTree(visibleCollections),
          };
        }),
      };

      sendResponseCallback(200, "application/json", JSON.stringify(result));
    } catch (e) {
      sendResponseCallback(500, "application/json", JSON.stringify({
        success: false,
        error: `Error listing collections: ${e instanceof Error ? e.message : String(e)}`,
      }));
    }
  };
}

export class ApiEndpoints {
  /**
   * Register HTTP API endpoints with Zotero's server.
   */
  static register(): void {
    Zotero.Server.Endpoints["/export-org/citekey"] = CitekeyEndpoint;
    Zotero.Server.Endpoints["/export-org/libraries"] = LibrariesEndpoint;
    Zotero.Server.Endpoints["/export-org/picker"] = PickerEndpoint;
    Zotero.Server.Endpoints["/export-org/collections"] = CollectionsListEndpoint;
    Zotero.Server.Endpoints["/export-org/collection"] = CollectionEndpoint;
    Zotero.Server.Endpoints["/export-org/collection/current"] = CollectionCurrentEndpoint;
    Zotero.Server.Endpoints["/export-org/collection/select"] = CollectionSelectEndpoint;
    Zotero.Server.Endpoints["/export-org/collection/create"] = CollectionCreateEndpoint;
    Zotero.Server.Endpoints["/export-org/collections/list"] = CollectionsListHierarchicalEndpoint;
    ztoolkit.log("Registered API endpoints: /export-org/citekey, /export-org/libraries, /export-org/picker, /export-org/collections, /export-org/collection, /export-org/collection/current, /export-org/collection/select, /export-org/collection/create, /export-org/collections/list");
  }
}
