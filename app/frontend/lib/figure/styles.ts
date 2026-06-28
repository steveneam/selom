import type { FigureSpec } from "./figure-spec";

/** A journal style pack from the backend (skills/styles.py). */
export interface FigureStyle {
  id: string;
  label: string;
  description: string;
  attribution: string;
}

/** The installed journal styles. Mirrors GET /figures/styles (app/backend/main.py). */
export async function fetchStyles(): Promise<FigureStyle[]> {
  const res = await fetch("/api/figures/styles");
  if (!res.ok) throw new Error("Couldn't load figure styles.");
  const json = (await res.json()) as { styles?: FigureStyle[] };
  return json.styles ?? [];
}

/**
 * Re-skin a figure in a journal style and return the styled spec.
 *
 * Posts to POST /figures/style/apply, where the single Python theme transform runs
 * (no TS duplicate). The caller commits the result as one undoable edit, so the
 * restyle is WYSIWYG and fully editable afterwards.
 */
export async function applyStyle(
  figure: FigureSpec,
  skillId: string | undefined,
  style: string,
): Promise<FigureSpec> {
  const res = await fetch("/api/figures/style/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ figure, skill_id: skillId, style }),
  });
  if (!res.ok) {
    let detail = res.status >= 500 ? "the styling service is temporarily unavailable" : `the request was rejected (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`Couldn't apply this style — ${detail}.`);
  }
  const json = (await res.json()) as { figure?: FigureSpec };
  if (!json.figure || !Array.isArray(json.figure.data)) {
    throw new Error("Server returned a malformed figure spec.");
  }
  return json.figure;
}
