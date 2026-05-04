declare const _globalThis: {
  [key: string]: any;
  Zotero: _ZoteroTypes.Zotero;
  ztoolkit: ZToolkit;
  addon: typeof addon;
};

declare const ZoteroPane: _ZoteroTypes.ZoteroPane;

declare type ZToolkit = ReturnType<
  typeof import("../src/utils/ztoolkit").createZToolkit
>;

declare const ztoolkit: ZToolkit;

declare const rootURI: string;

declare const addon: import("../src/addon").default;

declare const __env__: "production" | "development";

// Timer functions available in the Zotero sandbox (Firefox/Gecko)
declare function setTimeout(callback: (...args: any[]) => void, ms?: number, ...args: any[]): number;
declare function clearTimeout(id: number): void;
