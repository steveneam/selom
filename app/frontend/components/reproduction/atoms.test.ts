import { describe, expect, it } from "vitest";

import { ReadingProvenanceBadge } from "./atoms";

/**
 * The synthesized-read badge's GATING RULE (DECISIONS #16, docs/provenance-stamping/spec.md).
 *
 * Called as a plain function rather than rendered: a React component is one, `null` is a real
 * return value, and the whole claim here is *when* the badge appears. That needs no DOM.
 *
 * Worth pinning because nothing else can catch it: none of the three published ledgers exercises
 * this path (they are captured replays — see spec §7), so the badge cannot appear on any current
 * fixture, and a component that silently rendered on every panel — or on none — would look exactly
 * the same in the app today. [[selom-shipped-not-reachable]]
 */
describe("ReadingProvenanceBadge", () => {
  it("renders for a synthesized read", () => {
    expect(ReadingProvenanceBadge({ readingProvenance: "synthesized" })).not.toBeNull();
  });

  it("renders NOTHING for a native read — a marker on every panel is a marker nobody reads", () => {
    expect(ReadingProvenanceBadge({ readingProvenance: "" })).toBeNull();
    // `table` / `figure` are real `Reading.source` values that are NOT synthesized. The badge is
    // keyed to the one case that caps confidence, not to "any provenance string is present".
    expect(ReadingProvenanceBadge({ readingProvenance: "table" })).toBeNull();
    expect(ReadingProvenanceBadge({ readingProvenance: "figure" })).toBeNull();
  });
});
