/**
 * OutlineLabeler — watches reader tabs and injects page labels
 * into the PDF outline/TOC sidebar.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

const STYLE_ID = "zotero-outline-page-labels-style";
const LABEL_CLASS = "outline-page-label";
const DEBOUNCE_MS = 150;

function log(msg: string) {
  Zotero.debug(`[Outline Page Labels] ${msg}`);
}

interface OutlineItem {
  title: string;
  location?: Record<string, any>;
  items?: OutlineItem[];
  dest?: any;
  [key: string]: any;
}

interface TrackedReader {
  observer: MutationObserver | null;
  styleEl: HTMLStyleElement | null;
  debounceTimer: number | null;
}

export class OutlineLabeler {
  private _notifierID: string | null = null;
  private _readers = new Map<string, TrackedReader>();

  init(): void {
    log("Initializing...");

    this._notifierID = Zotero.Notifier.registerObserver(
      {
        notify: (
          event: string,
          type: string,
          ids: (string | number)[],
          _extraData: Record<string, unknown>,
        ) => {
          if (type === "tab") {
            if (event === "add" || event === "select") {
              setTimeout(() => this.processExistingReaders(), 1000);
            } else if (event === "close") {
              for (const id of ids) {
                this._cleanupReader(String(id));
              }
            }
          }
        },
      },
      ["tab"],
      "OutlinePageLabels",
    );

    setTimeout(() => this.processExistingReaders(), 2000);
    log("Initialized");
  }

  destroy(): void {
    if (this._notifierID) {
      Zotero.Notifier.unregisterObserver(this._notifierID);
      this._notifierID = null;
    }

    for (const [id] of this._readers) {
      this._cleanupReader(id);
    }
    this._readers.clear();
    log("Destroyed");
  }

  processExistingReaders(): void {
    const readers = (Zotero.Reader as any)?._readers;
    if (!Array.isArray(readers)) return;

    for (const reader of readers) {
      const id = reader._instanceID;
      if (!id || this._readers.has(id)) continue;
      if (reader.type && reader.type !== "pdf") continue;
      this._processReader(reader, id);
    }
  }

  private async _processReader(reader: any, id: string, retriesLeft = 20): Promise<void> {
    if (!this._readers.has(id)) {
      this._readers.set(id, {
        observer: null,
        styleEl: null,
        debounceTimer: null,
      });
    }

    try {
      if (reader._initPromise) {
        await reader._initPromise;
      }

      if (reader.type && reader.type !== "pdf") {
        this._readers.delete(id);
        return;
      }

      const pdfDoc = this._getPdfDocument(reader);
      if (!pdfDoc) {
        if (retriesLeft > 0) {
          setTimeout(() => {
            const stillOpen = (Zotero.Reader as any)?._readers?.includes(reader);
            if (stillOpen) this._processReader(reader, id, retriesLeft - 1);
          }, 500);
        } else {
          log(`pdf.js never loaded for reader ${id}, giving up`);
        }
        return;
      }

      const pdfOutline = await pdfDoc.getOutline();
      if (!pdfOutline || pdfOutline.length === 0) {
        log(`PDF has no outline for reader ${id}`);
        return;
      }

      log(`pdf.js outline has ${pdfOutline.length} top-level items`);

      const state = reader._internalReader?._state;
      const pageLabels = await this._getPageLabels(reader, state);

      const titleToLabel = await this._buildLabelMapFromPdfJs(pdfDoc, pageLabels);

      log(`Title→label map: ${titleToLabel.size} entries`);
      for (const [title, label] of Array.from(titleToLabel.entries()).slice(0, 5)) {
        log(`  "${title}" → "${label}"`);
      }

      if (titleToLabel.size === 0) {
        log("No page labels could be resolved, giving up");
        return;
      }

      this._injectWithRetry(reader, id, titleToLabel, 10);
    } catch (e) {
      log(`Error processing reader ${id}: ${e}`);
    }
  }

  private _getPdfDocument(reader: any): any {
    try {
      return (
        reader._internalReader?._primaryView?._iframeWindow
          ?.PDFViewerApplication?.pdfDocument || null
      );
    } catch {
      return null;
    }
  }

  /**
   * Use pdf.js getOutline() + getDestination() to resolve each outline
   * entry's destination to a page number, then map to page labels.
   */
  private async _buildLabelMapFromPdfJs(
    pdfDoc: any,
    pageLabels: string[] | null,
  ): Promise<Map<string, string>> {
    const map = new Map<string, string>();

    try {
      const pdfOutline = await pdfDoc.getOutline();
      if (!pdfOutline) {
        log("pdf.js getOutline() returned null");
        return map;
      }

      log(`pdf.js outline has ${pdfOutline.length} top-level items`);

      // Debug first pdf.js outline item
      if (pdfOutline[0]) {
        log(`pdf.js first item keys: ${Object.keys(pdfOutline[0]).join(", ")}`);
        const destStr = JSON.stringify(pdfOutline[0].dest);
        log(`pdf.js first item dest: ${destStr?.substring(0, 200)}`);
      }

      await this._walkPdfOutline(pdfDoc, pdfOutline, pageLabels, map);
    } catch (e) {
      log(`Error building label map from pdf.js: ${e}`);
    }

    return map;
  }

  private async _walkPdfOutline(
    pdfDoc: any,
    items: any[],
    pageLabels: string[] | null,
    map: Map<string, string>,
  ): Promise<void> {
    for (const item of items) {
      const title = item.title;
      if (title && !map.has(title)) {
        const pageNum = await this._resolveDestToPageNumber(
          pdfDoc,
          item.dest,
        );
        if (pageNum != null) {
          const pageIndex = pageNum - 1;
          let label: string;
          if (pageLabels && pageIndex >= 0 && pageIndex < pageLabels.length) {
            label = pageLabels[pageIndex];
          } else {
            label = String(pageNum);
          }
          map.set(title, label);
        }
      }

      if (item.items?.length) {
        await this._walkPdfOutline(pdfDoc, item.items, pageLabels, map);
      }
    }
  }

  /**
   * Resolve a PDF destination to a 1-based page number.
   */
  private async _resolveDestToPageNumber(
    pdfDoc: any,
    dest: any,
  ): Promise<number | null> {
    if (dest == null) return null;

    try {
      // Named destination (string) — resolve it first
      let explicitDest = dest;
      if (typeof dest === "string") {
        explicitDest = await pdfDoc.getDestination(dest);
        if (!explicitDest) return null;
      }

      // Explicit destination: [pageRef, type, ...params]
      if (Array.isArray(explicitDest) && explicitDest.length > 0) {
        const pageRef = explicitDest[0];
        if (pageRef && typeof pageRef === "object") {
          // pageRef is a PDF object reference {num, gen}
          const pageIndex = await pdfDoc.getPageIndex(pageRef);
          if (typeof pageIndex === "number") {
            return pageIndex + 1; // 1-based
          }
        } else if (typeof pageRef === "number") {
          return pageRef + 1; // already a page index
        }
      }
    } catch (e) {
      // Some destinations may be invalid
    }

    return null;
  }

  /**
   * Fallback: try to extract page numbers from the state outline data.
   */
  private _buildLabelMapFromState(
    outline: OutlineItem[],
    pageLabels: string[] | null,
  ): Map<string, string> {
    const map = new Map<string, string>();

    const walk = (items: OutlineItem[]) => {
      for (const item of items) {
        if (item.title && !map.has(item.title)) {
          const pageNum = this._extractPageNumber(item);
          if (pageNum != null) {
            const pageIndex = pageNum - 1;
            let label: string;
            if (
              pageLabels &&
              pageIndex >= 0 &&
              pageIndex < pageLabels.length
            ) {
              label = pageLabels[pageIndex];
            } else {
              label = String(pageNum);
            }
            map.set(item.title, label);
          }
        }
        if (item.items?.length) {
          walk(item.items);
        }
      }
    };

    walk(outline);
    return map;
  }

  private _extractPageNumber(item: OutlineItem): number | null {
    const loc = item.location;
    if (loc) {
      for (const key of [
        "pageNumber",
        "pageIndex",
        "page",
        "pageLabel",
      ]) {
        const val = loc[key];
        if (val != null) {
          const num =
            typeof val === "number" ? val : parseInt(String(val), 10);
          if (!isNaN(num)) {
            return key === "pageIndex" ? num + 1 : num;
          }
        }
      }
      // position.pageIndex
      if (loc.position?.pageIndex != null) {
        const pi = loc.position.pageIndex;
        const num = typeof pi === "number" ? pi : parseInt(String(pi), 10);
        if (!isNaN(num)) return num + 1;
      }
    }

    // dest might be an explicit destination array
    if (Array.isArray(item.dest) && typeof item.dest[0] === "number") {
      return item.dest[0] + 1;
    }

    return null;
  }

  private async _getPageLabels(
    reader: any,
    state: any,
  ): Promise<string[] | null> {
    if (Array.isArray(state?.pageLabels) && state.pageLabels.length > 0) {
      log(`Using ${state.pageLabels.length} page labels from state`);
      return state.pageLabels;
    }

    try {
      const pdfDoc = this._getPdfDocument(reader);
      if (pdfDoc?.getPageLabels) {
        const labels = await pdfDoc.getPageLabels();
        if (Array.isArray(labels) && labels.length > 0) {
          log(`Using ${labels.length} page labels from pdf.js`);
          return labels;
        }
      }
    } catch (e) {
      log(`Could not get page labels from pdf.js: ${e}`);
    }

    return null;
  }

  private _injectWithRetry(
    reader: any,
    id: string,
    titleToLabel: Map<string, string>,
    retriesLeft: number,
  ): void {
    if (!this._readers.has(id)) return;

    const iframeDocs = this._getAllIframeDocuments(reader);
    for (const iframeDoc of iframeDocs) {
      const container = this._findOutlineContainer(iframeDoc);
      if (!container) continue;

      const rows = this._findOutlineRows(container);
      if (!rows.length) continue;

      this._injectStyles(iframeDoc, id);
      const injected = this._injectLabels(rows, titleToLabel);

      if (injected > 0) {
        log(`Injected ${injected} labels`);
        this._setupObserver(reader, id, titleToLabel, iframeDoc);
        return;
      }
    }

    if (retriesLeft > 0) {
      setTimeout(
        () => this._injectWithRetry(reader, id, titleToLabel, retriesLeft - 1),
        500,
      );
    } else {
      log("All retries exhausted");
    }
  }

  private _injectLabels(
    rows: Element[],
    titleToLabel: Map<string, string>,
  ): number {
    let injected = 0;
    for (const row of rows) {
      if (row.querySelector(`.${LABEL_CLASS}`)) continue;

      const titleEl = row.querySelector(".title");
      const title = (titleEl || row).textContent?.trim() || "";
      const label = titleToLabel.get(title);

      if (label) {
        const doc = row.ownerDocument;
        if (!doc) continue;
        const span = doc.createElement("span");
        span.className = LABEL_CLASS;
        span.textContent = label;
        row.appendChild(span);
        injected++;
      }
    }
    return injected;
  }

  private _getAllIframeDocuments(reader: any): Document[] {
    const docs: Document[] = [];

    try {
      const doc = reader._iframeWindow?.document;
      if (doc) docs.push(doc);
    } catch {
      /* */
    }

    // Check nested iframes
    for (const doc of [...docs]) {
      try {
        const frames = doc.querySelectorAll("iframe");
        for (const frame of frames) {
          try {
            const nested =
              (frame as HTMLIFrameElement).contentDocument ||
              (frame as HTMLIFrameElement).contentWindow?.document;
            if (nested && !docs.includes(nested)) docs.push(nested);
          } catch {
            /* cross-origin */
          }
        }
      } catch {
        /* */
      }
    }

    return docs;
  }

  private _findOutlineContainer(doc: Document): Element | null {
    for (const sel of [
      "#outlineView",
      ".outline-view",
      "#outline",
      ".outline",
    ]) {
      try {
        const el = doc.querySelector(sel);
        if (el) return el;
      } catch {
        /* */
      }
    }

    // Broader: structural elements only
    for (const el of doc.querySelectorAll("div, section, nav, ul, ol")) {
      const cls = (el.getAttribute("class") || "").toLowerCase();
      const elId = (el.getAttribute("id") || "").toLowerCase();
      if (cls.includes("outline") || elId.includes("outline")) {
        return el;
      }
    }

    return null;
  }

  private _findOutlineRows(container: Element): Element[] {
    for (const sel of [".item", ".row", "[role='treeitem']"]) {
      const rows = container.querySelectorAll(sel);
      if (rows.length > 0) return Array.from(rows);
    }
    return Array.from(container.children).filter(
      (el) =>
        el.tagName.toLowerCase() !== "style" &&
        el.tagName.toLowerCase() !== "script" &&
        el.textContent?.trim(),
    );
  }

  private _injectStyles(doc: Document, readerId: string): void {
    const styleId = `${STYLE_ID}-${readerId}`;
    if (doc.getElementById(styleId)) return;

    const style = doc.createElement("style");
    style.id = styleId;
    style.textContent = `
      .${LABEL_CLASS} {
        margin-left: auto;
        padding-left: 8px;
        color: var(--fill-secondary, #888);
        font-size: 0.85em;
        white-space: nowrap;
        flex-shrink: 0;
        opacity: 0.7;
      }
    `;
    doc.head?.appendChild(style);

    const tracked = this._readers.get(readerId);
    if (tracked) tracked.styleEl = style;
  }

  private _setupObserver(
    reader: any,
    id: string,
    titleToLabel: Map<string, string>,
    iframeDoc: Document,
  ): void {
    const container = this._findOutlineContainer(iframeDoc);
    if (!container) return;

    const tracked = this._readers.get(id);
    if (!tracked || tracked.observer) return;

    const observer = new (iframeDoc.defaultView as any).MutationObserver(
      () => {
        if (tracked.debounceTimer) clearTimeout(tracked.debounceTimer);
        tracked.debounceTimer = setTimeout(() => {
          if (!this._readers.has(id)) return;
          const cont = this._findOutlineContainer(iframeDoc);
          if (!cont) return;
          const rows = this._findOutlineRows(cont);
          this._injectLabels(rows, titleToLabel);
        }, DEBOUNCE_MS);
      },
    );

    observer.observe(container, { childList: true, subtree: true });
    tracked.observer = observer;
    log(`MutationObserver set up for reader ${id}`);
  }

  private _cleanupReader(id: string): void {
    const tracked = this._readers.get(id);
    if (!tracked) return;

    if (tracked.observer) tracked.observer.disconnect();
    if (tracked.debounceTimer) clearTimeout(tracked.debounceTimer);
    if (tracked.styleEl?.parentNode) {
      tracked.styleEl.parentNode.removeChild(tracked.styleEl);
    }

    this._readers.delete(id);
    log(`Cleaned up reader ${id}`);
  }
}
