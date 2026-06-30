/**
 * Drift guard — operator demo recordings ↔ showcase scorecard.
 *
 * The operator gateway (the canned ✨AI demo engine, SELOM_AI_GATEWAY=operator) serves each
 * showcase paper's recorded explanation VERBATIM keyed by paper_id — it never re-reads the
 * scorecard. Those recordings hardcode each paper's headline numbers in prose ("Reproducibility
 * 63/100", "confidence 92/100"). The public demo page renders that ✨AI text on the SAME panel as
 * the scorecard (REPRO_LEDGERS). So if a fixture is ever edited and the recording isn't, the
 * AI-attributed text would silently contradict the displayed score — and honesty of AI-attributed
 * output is a declared pre-launch hard gate. Nothing else ties the two; this test does.
 * (review-gauntlet 2026-06-30, finding #2.)
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { REPRO_LEDGERS } from "@/lib/reproduction/fixture";

// The recordings live in the backend lane (the operator gateway loads them at runtime); read the
// single source of truth rather than duplicating it here. A move/rename fails this guard loudly.
const recordingsPath = resolve(process.cwd(), "../backend/ai/recordings/explain.json");
const recordings = JSON.parse(readFileSync(recordingsPath, "utf-8")) as {
  explanations: { request_type: string; key: string; text: string }[];
};

function recordedExplainScore(slug: string): string {
  const entry = recordings.explanations.find(
    (r) => r.request_type === "explain_score" && r.key === slug,
  );
  if (!entry) throw new Error(`no explain_score recording for showcase paper "${slug}"`);
  return entry.text;
}

describe("operator demo recordings ↔ showcase scorecard parity", () => {
  it.each(["rpgrip1", "jev", "hani"])(
    "%s recorded ✨AI prose headline numbers match the displayed scorecard",
    (slug) => {
      const text = recordedExplainScore(slug);
      const score = REPRO_LEDGERS[slug]?.scorecard?.score;
      expect(score, `fixture ledger "${slug}" has a graded score`).toBeTruthy();

      const repro = text.match(/Reproducibility (\d+)\/100/);
      expect(repro, `recording "${slug}" states "Reproducibility N/100"`).not.toBeNull();
      expect(Number(repro![1])).toBe(score!.reproducibility);

      // selom_confidence is cited as "...confidence … M/100" — assert it when present.
      const conf = text.match(/confidence[^\d]*(\d+)\/100/i);
      if (conf) expect(Number(conf[1])).toBe(score!.selom_confidence);
    },
  );
});
