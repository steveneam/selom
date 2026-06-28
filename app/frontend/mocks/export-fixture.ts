import type { ExportPreset } from "@/lib/figure/export";

/** Mirror of export.PRESETS (app/backend/export.py) for offline `dev:mock`. */
export const EXPORT_PRESETS: ExportPreset[] = [
  { id: "nature-single", label: "Nature — single column", width_mm: 89, dpi: 300, note: "89 mm @ 300 dpi" },
  { id: "nature-double", label: "Nature — double column", width_mm: 183, dpi: 300, note: "183 mm @ 300 dpi" },
  { id: "cell-single", label: "Cell — single column", width_mm: 85, dpi: 300, note: "85 mm @ 300 dpi" },
  { id: "cell-double", label: "Cell — double column", width_mm: 174, dpi: 300, note: "174 mm @ 300 dpi" },
  { id: "science-single", label: "Science — single column", width_mm: 57, dpi: 300, note: "57 mm @ 300 dpi" },
  { id: "science-double", label: "Science — double column", width_mm: 121, dpi: 300, note: "121 mm @ 300 dpi" },
  { id: "plos-full", label: "PLOS — full width", width_mm: 190, dpi: 300, note: "190 mm @ 300 dpi" },
  { id: "hi-res-square", label: "High-res square", width_mm: 150, dpi: 600, note: "150 mm @ 600 dpi" },
];

// 1×1 transparent PNG — the real backend renders the figure via Kaleido; the mock
// only needs to prove the download flow (no Chrome in dev:mock).
const PNG_1x1 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

function pngBlob(type: string): Blob {
  const bin = atob(PNG_1x1);
  const bytes = new Uint8Array(bin.length); // narrow to Uint8Array<ArrayBuffer> for BlobPart
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type });
}

const MOCK_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="120"><rect width="240" height="120" fill="#fff"/>' +
  '<text x="14" y="64" font-family="sans-serif" font-size="13" fill="#33404d">Selom mock export</text></svg>';

const MOCK_PDF = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 240 120]>>endobj
trailer<</Root 1 0 R>>
%%EOF`;

const MEDIA: Record<string, string> = {
  png: "image/png",
  svg: "image/svg+xml",
  pdf: "application/pdf",
};

/** A small per-format payload + media type for the mock export endpoint. */
export function mockExportFile(format: string): { body: BodyInit; type: string } {
  const type = MEDIA[format] ?? "application/octet-stream";
  if (format === "png") return { body: pngBlob(type), type };
  if (format === "pdf") return { body: MOCK_PDF, type };
  return { body: MOCK_SVG, type };
}
