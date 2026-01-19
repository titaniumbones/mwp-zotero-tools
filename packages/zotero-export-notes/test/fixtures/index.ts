/**
 * Test fixtures and helpers for zotero-export-notes tests.
 */

import * as fs from "fs";
import * as path from "path";
import { ZoteroAnnotation } from "../../src/modules/annotationFormatter.js";

// Path to shared fixtures
const FIXTURES_DIR = path.join(
  __dirname,
  "..",
  "..",
  "..",
  "..",
  "shared",
  "fixtures",
);

/**
 * Load a JSON fixture file.
 */
export function loadFixture<T>(relativePath: string): T {
  const fullPath = path.join(FIXTURES_DIR, relativePath);
  const content = fs.readFileSync(fullPath, "utf-8");
  return JSON.parse(content);
}

/**
 * Create a mock ZoteroAnnotation object for testing.
 */
export function createMockAnnotation(
  overrides: Partial<{
    annotationType: "highlight" | "underline" | "note" | "image" | "ink";
    annotationText: string;
    annotationComment: string;
    annotationPageLabel: string;
    annotationPosition: string;
    annotationColor: string;
    key: string;
    tags: Array<{ tag: string }>;
  }> = {},
): ZoteroAnnotation {
  const defaults = {
    annotationType: "highlight" as const,
    annotationText: "Sample highlighted text",
    annotationComment: "",
    annotationPageLabel: "5",
    annotationPosition: '{"pageIndex":4,"rects":[[100,200,500,220]]}',
    annotationColor: "#ffd400",
    key: "ANNOT001",
    tags: [],
  };

  const merged = { ...defaults, ...overrides };
  const tags = merged.tags;

  return {
    annotationType: merged.annotationType,
    annotationText: merged.annotationText,
    annotationComment: merged.annotationComment,
    annotationPageLabel: merged.annotationPageLabel,
    annotationPosition: merged.annotationPosition,
    annotationColor: merged.annotationColor,
    key: merged.key,
    getTags: () => tags,
  };
}

/**
 * Load PDF annotations fixture and convert to mock annotations.
 */
export function loadPdfAnnotations(): ZoteroAnnotation[] {
  const rawAnnotations = loadFixture<Array<{ data: Record<string, unknown> }>>(
    "annotations/pdf-highlights.json",
  );

  return rawAnnotations.map((ann) => {
    const data = ann.data;
    const tags = (data.tags as Array<{ tag: string }>) || [];

    return createMockAnnotation({
      annotationType: data.annotationType as
        | "highlight"
        | "underline"
        | "note"
        | "image"
        | "ink",
      annotationText: data.annotationText as string,
      annotationComment: data.annotationComment as string,
      annotationPageLabel: data.annotationPageLabel as string,
      annotationPosition: data.annotationPosition as string,
      annotationColor: data.annotationColor as string,
      key: data.key as string,
      tags: tags,
    });
  });
}
