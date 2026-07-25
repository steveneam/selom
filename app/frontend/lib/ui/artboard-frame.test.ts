import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { artboardFrame } from "./artboard-frame";

/**
 * Ratchets for "the artboard is the hero, and fixed chrome must justify its pixels"
 * (docs/integration-robustness/proposal.md §3.3). Both findings this file pins — A24 (the hero
 * clipped inside its own stage) and A25 · B13 (an inert band spending the vertical budget) — were
 * CSS-only claims with no gate, which is exactly why they shipped. `fe-build` cannot see them and a
 * browser is not always drivable, so the invariant lives here, gated on an exit code.
 */
const SHELL = join(process.cwd(), "components", "figure", "shell");
const HOST = join(SHELL, "artboard-host.tsx");

describe("artboardFrame — the stage sizes the card (A24)", () => {
  it("gives a responsive figure NO height of its own — the stage owns the vertical axis", () => {
    const { cardStyle } = artboardFrame(false);
    // The regression being pinned: `height: min(74vh, 720px)` asked for 720px inside a 548px stage,
    // so ~24% of the figure sat below the visible area (measured 1512x1050). Any exact height here
    // — px, vh, % — can exceed what the shell's bands left over, so there must not be one.
    expect(cardStyle).toBeDefined();
    expect(Object.keys(cardStyle!).sort()).toEqual(["maxWidth", "width"]);
  });

  it("stretches a responsive card to the stage, bracketed by a floor and a cap", () => {
    const { alignClass, cardClass } = artboardFrame(false);
    expect(alignClass).toBe("items-stretch");
    // A min/max can only resize the card AWAY from the stage's height; neither can overflow it the
    // way an exact height does. The floor keeps a card usable (and non-collapsing) if a host ever
    // gives the stage no definite height; the cap is the vertical peer of the 88rem width cap.
    expect(cardClass).toMatch(/\bmin-h-\[/);
    expect(cardClass).toMatch(/\bmax-h-\[/);
  });

  it("leaves a fixed-size figure at its declared size, top-aligned so it stays scrollable", () => {
    // ERG trace grids / multi-panel figures declare `layout.width`. Their size is a property of the
    // FIGURE, not a guess about the viewport, so the stage must not stretch or shrink them —
    // top-aligned (never centred, which would push the top out of view AND out of scroll reach).
    expect(artboardFrame(true)).toEqual({
      alignClass: "items-start",
      cardClass: undefined,
      cardStyle: undefined,
    });
  });
});

describe("the figure shell's fixed chrome (A24 · A25 · B13)", () => {
  it("sizes the artboard through the declared rule, never with a viewport-relative guess", () => {
    const src = readFileSync(HOST, "utf8");
    expect(src).toContain("artboardFrame");
    // `vh` measures the WINDOW; the artboard only gets what the shell's bands leave over. A viewport
    // unit here is A24 in a different unit, so it must not come back — in the host or in the rule.
    expect(src).not.toMatch(/\d\s*vh\b/);
    // …and the rule itself hands back no viewport unit either, in a class or a style.
    expect(JSON.stringify([artboardFrame(false), artboardFrame(true)])).not.toMatch(/\d\s*vh\b/);
  });

  it("docks no inert 'coming soon' band around the artboard", () => {
    // A25 · B13: the palette strip was permanent chrome that returned nothing for the ~34px it took
    // out of an already-clipped artboard — aria-hidden, and hardcoded to Okabe–Ito no matter what
    // `layout.colorway` said, so it asserted the WRONG palette as soon as Style swapped it. It was
    // RETIRED, not restyled. A live palette board is welcome back in this dir; a placeholder that
    // charges the hero its pixels is not — every band here has to earn them.
    const offenders = readdirSync(SHELL)
      .filter((f) => /\.tsx?$/.test(f))
      // Comments are stripped first: the invariant is about what the shell RENDERS, so a comment
      // recording WHY a band was retired must not read as the band coming back.
      .filter((f) => /coming\s*soon/i.test(stripComments(readFileSync(join(SHELL, f), "utf8"))))
      .sort();
    expect(offenders).toEqual([]);
  });
});

function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}
