import type { FigureStyle } from "@/lib/styles-api";
import type { FigureSpec } from "@/lib/figure-spec";

/** Mirror of skills/styles.py STYLES for offline `dev:mock`. */
export const FIGURE_STYLES: FigureStyle[] = [
  { id: "selom", label: "Selom default", description: "Selom's house publication look.", attribution: "" },
  { id: "nature", label: "Nature", description: "Nature house style — gridless, colourblind-safe.", attribution: "Follows Nature figure guidelines; font Arimo." },
  { id: "cell", label: "Cell", description: "Cell house style — light grid, CB-safe palette.", attribution: "Follows Cell Press STAR Methods; font Arimo." },
  { id: "science", label: "Science", description: "Science house style — compact, thin lines.", attribution: "Follows Science figure-prep; font Arimo." },
  { id: "grayscale", label: "Grayscale (print-safe)", description: "Greyscale-only, print/accessibility-safe.", attribution: "Print-safe variant; font Arimo." },
];

// Enough of each style's tokens to make the offline preview visibly change. The real
// backend runs the full theme transform; the mock just remaps palette + font + bg.
const TOKENS: Record<string, { colorway: string[]; font: string; paper: string; ink: string }> = {
  selom: { colorway: ["#2f6db0", "#e08a2b", "#3f9b6b", "#c0392b", "#7d5ba6", "#1f9aa6"], font: "Inter, Helvetica, Arial, sans-serif", paper: "#ffffff", ink: "#33404d" },
  nature: { colorway: ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"], font: "Arimo, Arial, Helvetica, sans-serif", paper: "#ffffff", ink: "#000000" },
  cell: { colorway: ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"], font: "Arimo, Arial, Helvetica, sans-serif", paper: "#ffffff", ink: "#1a1a1a" },
  science: { colorway: ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"], font: "Arimo, Arial, Helvetica, sans-serif", paper: "#ffffff", ink: "#1a1a1a" },
  grayscale: { colorway: ["#111827", "#4b5563", "#6b7280", "#9ca3af", "#1f2937", "#374151"], font: "Arimo, Arial, Helvetica, sans-serif", paper: "#ffffff", ink: "#000000" },
};

/** Restyle a figure the way the backend would (palette/font/bg) — enough for a live mock preview. */
export function mockApplyStyle(figure: FigureSpec, styleId: string): FigureSpec {
  const t = TOKENS[styleId] ?? TOKENS.selom;
  const layout = {
    ...figure.layout,
    colorway: t.colorway,
    paper_bgcolor: t.paper,
    plot_bgcolor: t.paper,
    font: { ...(figure.layout?.font ?? {}), family: t.font, color: t.ink },
  };
  // Remap any explicit per-trace marker colour onto the new palette by index, so the
  // mock preview actually changes colour (real traces often pin marker.color).
  const data = (figure.data ?? []).map((tr, i) => {
    const marker = tr.marker as Record<string, unknown> | undefined;
    if (marker && typeof marker.color === "string") {
      return { ...tr, marker: { ...marker, color: t.colorway[i % t.colorway.length] } };
    }
    return tr;
  });
  return { data, layout };
}
