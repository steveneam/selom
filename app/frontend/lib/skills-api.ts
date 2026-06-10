import type { FigureSpec } from "./figure-spec";

export interface SkillRunResponse {
  figure: FigureSpec;
}

export type SkillParams = Record<string, string | number | boolean>;

/**
 * Run a skill on an uploaded file and return the editable figure spec.
 *
 * Matches the live contract (app/backend/main.py): a one-shot multipart POST with
 * the file in field `matrix` and tuning params as query string, responding with
 * `{ figure: { data, layout } }`. The MSW mock (mocks/handlers.ts) mirrors it, so
 * this path works with the backend down (`npm run dev:mock`).
 */
export async function runSkill(
  skillId: string,
  file: File,
  params: SkillParams = {},
): Promise<FigureSpec> {
  const fd = new FormData();
  fd.append("matrix", file);

  const entries = Object.entries(params).map(([k, v]) => [k, String(v)] as [string, string]);
  const qs = new URLSearchParams(entries).toString();
  const url = `/api/skills/${encodeURIComponent(skillId)}/run${qs ? `?${qs}` : ""}`;

  const res = await fetch(url, { method: "POST", body: fd });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`Skill run failed (${detail}).`);
  }

  const json = (await res.json()) as Partial<SkillRunResponse>;
  if (!json.figure || !Array.isArray(json.figure.data)) {
    throw new Error("Server returned a malformed figure spec.");
  }
  return json.figure;
}
