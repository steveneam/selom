import { measureStage, test, expect } from "./fixtures";

/**
 * D-11 — does the artboard clip on `/extract`? (board `V-1`)
 *
 * `/extract`'s editor is the SECOND host of the artboard sizing rule (`lib/ui/artboard-frame.ts`):
 * `chart-extractor.tsx` renders the classic `EditorWorkspace`, the same one the shell wraps. But its
 * stage is squeezed harder than anywhere else in the app — a header, an amber vision-grade strip AND
 * a `StatsPanel` with `defaultOpen` all take height from the same column — which makes it the most
 * likely place for `L3-01`'s `min-h-[20rem]` (320px) floor to engage and start scrolling the stage.
 *
 * It was the one reachable §D bullet left unrun, because reaching this editor is a real interaction:
 * dropping an image is not enough, the user must mark two reference ticks on EACH axis and type
 * their values before recovery unlocks (`calibrationComplete` + `calibrationDegenerate` in
 * `lib/extract/calibrate.ts`). So this drives it.
 *
 * THE FIXTURE IMAGE IS GENERATED, NOT COMMITTED. The `editor` fixture already lands a real volcano
 * in the real editor; screenshotting that artboard card alone yields a genuine published-looking
 * chart panel to drop into `/extract` — a real rendered figure, no binary in the repo, and it stays
 * in step with the app instead of rotting.
 *
 * SCOPE. This is a LAYOUT question, deliberately not an accuracy one — whether the recovered numbers
 * are right is `D-11`'s neighbour, not `D-11`. What matters here is that a real recovery completes on
 * a real backend and the resulting editor is measured with the same snippet D-5 used everywhere else.
 */

/** Where a calibration tick goes, as a fraction of the rendered panel. Spread wide on purpose:
 *  `calibrationDegenerate` rejects two refs on one axis that land within a pixel of each other. */
const TICKS = [
  { name: "X reference 1", fx: 0.2, fy: 0.9, value: "0" },
  { name: "X reference 2", fx: 0.8, fy: 0.9, value: "10" },
  { name: "Y reference 1", fx: 0.1, fy: 0.85, value: "0" },
  { name: "Y reference 2", fx: 0.1, fy: 0.15, value: "10" },
] as const;

test("D-11 — the /extract editor's artboard, measured on a real recovery", async ({ editor }) => {
  const { page } = editor;

  // 1. Make the panel. Screenshot at 1920 so the card is ~938px — the size a published panel
  //    actually arrives at, and wide enough that four spread ticks are unambiguous.
  await editor.viewport(1920, 1080);
  const card = page.locator(".bg-artboard").first();
  await expect(card).toBeVisible();
  const panel = "test-results/browser-verify/d11-panel.png";
  await card.screenshot({ path: panel });

  // 2. Drop it on /extract.
  await page.goto("/extract");
  await page.locator('input[type="file"]').first().setInputFiles(panel);

  const image = page.getByAltText("Chart panel to recover");
  await expect(image).toBeVisible({ timeout: 30_000 });

  // A volcano is a scatter; the default form is "bar" and would mask the wrong shape.
  await page.getByRole("button", { name: /^scatter$/i }).click();

  // 3. Mark the ticks. The picker advances X1 → X2 → Y1 → Y2 on its own (`firstUnplaced`), so the
  //    clicks go in that order and each row's value input enables as its point lands.
  const box = await image.boundingBox();
  if (!box) throw new Error("the calibration image has no box — it never rendered");
  for (const tick of TICKS) {
    await image.click({ position: { x: box.width * tick.fx, y: box.height * tick.fy } });
    await page.getByLabel(`${tick.name} value`).fill(tick.value);
  }

  // 4. Recover. The button stays disabled until calibration is complete AND non-degenerate, so its
  //    enabled state is itself the check that the four clicks registered as intended.
  const extract = page.getByRole("button", { name: /Extract data/i });
  await expect(extract).toBeEnabled();
  await extract.click();

  // The result stage, gated on something ONLY it has. "Vision-grade" copy appears on the drop stage
  // and the calibration stage too, so waiting for that let a slow recovery slip through and measure
  // the CALIBRATION artboard instead — which still reports matches=1 and a real card, so every
  // geometry assertion passed while the numbers described the wrong screen. "Recover another" exists
  // only once a recovery has actually landed.
  await expect(page.getByRole("button", { name: /Recover another/i })).toBeVisible({
    timeout: 180_000,
  });
  await expect(page.locator(".bg-artboard")).toBeVisible();

  // 5. Measure, with D-5's snippet verbatim — the point is comparability with every other surface.
  //    Plus the DOCUMENT's own scroll state: a stage taller than the viewport cannot be clip-free
  //    and fit at the same time, so "overflow=0" alone would be a half-answer. Whatever scrolls,
  //    scrolls; this says which.
  const results: {
    label: string;
    geo: Awaited<ReturnType<typeof measureStage>>;
    doc: { innerHeight: number; docScroll: number; scrolls: boolean };
  }[] = [];
  for (const [w, h] of [
    [1280, 800],
    [1440, 900],
  ] as const) {
    await page.setViewportSize({ width: w, height: h });
    await page.waitForTimeout(700); // layout + Plotly's debounced resize
    const geo = await measureStage(page);
    const doc = await page.evaluate(() => {
      const el = document.scrollingElement ?? document.documentElement;
      const card = [...document.querySelectorAll(".bg-artboard")].find((c) =>
        c.parentElement?.classList.contains("overflow-auto"),
      );
      const stage = card?.parentElement as HTMLElement | undefined;
      const stageRect = stage?.getBoundingClientRect();
      // Walk up from the stage and classify each ancestor: the first one that both CAN scroll and
      // HAS overflow is the element the user actually scrolls (the app shell's <main>, not the
      // document — measuring `document.scrollingElement` alone reports 0 and reads as "cut off").
      // Ancestors that clip without scrolling are recorded too: those genuinely eat content.
      let scroller: { className: string; overflow: number } | null = null;
      const clippers: { className: string; overflowY: string; height: number }[] = [];
      for (let n = stage?.parentElement; n && n !== document.body; n = n.parentElement) {
        const oy = getComputedStyle(n).overflowY;
        const over = n.scrollHeight - n.clientHeight;
        if (!scroller && (oy === "auto" || oy === "scroll") && over > 1) {
          scroller = { className: n.className.toString().slice(0, 44), overflow: over };
        }
        if (oy === "hidden" || oy === "clip") {
          clippers.push({
            className: n.className.toString().slice(0, 44),
            overflowY: oy,
            height: Math.round(n.getBoundingClientRect().height),
          });
        }
      }
      // Is the Statistics table — the second half of what /extract delivers — actually on screen?
      // Found STRUCTURALLY, not by text: its header renders `table.title ?? "Statistics"`, so the
      // title is data-dependent, and matching loose text picks up the amber strip's "recovered as an
      // editable figure" instead (which sits at the TOP and reads as a false pass). The result view
      // stacks three bands — vision-grade strip · editor · Statistics — so the stats band is the
      // last child of the column the stage lives in.
      // Anchored on <main>, not on computed flex properties. A "first flex-column ancestor with 3+
      // children" heuristic was tried and is too clever: it depends on styles this very change
      // edits, so it broke as soon as the editor's chrome moved. The result view is the app shell's
      // <main> child, always — walk up until the parent IS <main>.
      let column: HTMLElement | null = null;
      for (let n = stage; n && n !== document.body; n = n.parentElement) {
        if (n.parentElement?.tagName === "MAIN") {
          column = n;
          break;
        }
      }
      const stats = column?.lastElementChild;
      const statsRect = stats?.getBoundingClientRect();
      return {
        innerHeight: window.innerHeight,
        docScroll: el.scrollHeight - window.innerHeight,
        scrolls: el.scrollHeight > window.innerHeight + 1,
        stageTop: Math.round(stageRect?.top ?? 0),
        stageBottom: Math.round(stageRect?.bottom ?? 0),
        /** Pixels of the stage below the fold that nothing can scroll to. */
        belowFold: Math.max(0, Math.round((stageRect?.bottom ?? 0) - window.innerHeight)),
        scroller,
        clippers,
        statsFound: !!stats,
        statsTop: statsRect ? Math.round(statsRect.top) : null,
        statsText: (stats?.textContent ?? "").trim().slice(0, 40),
        statsVisible: statsRect ? statsRect.top < window.innerHeight : false,
      };
    });
    results.push({ label: `${w}×${h}`, geo, doc });
    await page.screenshot({ path: `test-results/browser-verify/d11-extract-${w}x${h}.png` });
  }

  const lines = results.map(
    ({ label, geo, doc }) =>
      `  ${label}  stageClient=${geo.stageClient}  stageScroll=${geo.stageScroll}  card=${geo.card}  ` +
      `overflow=${geo.overflow}  cardWidth=${geo.cardWidth}  matches=${geo.matches}\n` +
      `            viewportH=${doc.innerHeight}  documentScroll=${doc.docScroll}  ` +
      `pageScrolls=${doc.scrolls}\n` +
      `            stage top=${doc.stageTop} bottom=${doc.stageBottom}  belowFold=${doc.belowFold}  ` +
      `Statistics band ${
        doc.statsFound
          ? `top=${doc.statsTop} onScreen=${doc.statsVisible} ("${doc.statsText}")`
          : "NOT FOUND"
      }\n` +
      `            scrolled by: ${
        doc.scroller ? `"${doc.scroller.className}" (${doc.scroller.overflow}px)` : "nothing"
      }  ·  clipping ancestors: ${
        doc.clippers.length
          ? doc.clippers.map((c) => `${c.overflowY}@${c.height}px "${c.className}"`).join(" · ")
          : "none"
      }`,
  );
  const floorRisk = results.filter((r) => r.geo.stageClient <= 400);
  const overTall = results.filter((r) => r.geo.stageClient > r.doc.innerHeight);
  console.log(
    `\n[D-11 — /extract editor artboard]\n${lines.join("\n")}\n\n` +
      `  → overflow > 0 here is REPORTED, not a regression: L3-01 deliberately chose to scroll a\n` +
      `    too-short stage rather than collapse the card. The number is what lets the owner judge.\n` +
      `  → the min-h-[20rem] floor engages at stageClient ≈ 352px. ${
        floorRisk.length
          ? `⚑ CLOSE: ${floorRisk.map((r) => `${r.label}=${r.geo.stageClient}px`).join(", ")}`
          : "Clear at both widths."
      }\n` +
      `  → ${
        overTall.length
          ? `⚑ THE STAGE IS TALLER THAN THE VIEWPORT at ${overTall
              .map((r) => `${r.label} (stage ${r.geo.stageClient} > viewport ${r.doc.innerHeight}, ` +
                `${r.doc.belowFold}px below the fold)`)
              .join("; ")}.\n` +
            `    The ARTBOARD does not clip (overflow=0) — the editor as a whole simply doesn't fit,\n` +
            `    so the bottom of the figure sits below the fold until the user scrolls. Which\n` +
            `    element does the scrolling is on the "scrolled by" line: content is only genuinely\n` +
            `    lost if that says "nothing".`
          : "The stage fits inside the viewport at both sizes; nothing needs to scroll."
      }\n`,
  );

  // Exactly one artboard means we are on the editor and measuring the right element — the assertion
  // that stops this silently reporting zeros from a page that never reached the result stage.
  for (const { label, geo } of results) {
    expect(geo.matches, `${label}: expected exactly one artboard on /extract's editor`).toBe(1);
    expect(geo.card, `${label}: the artboard card should have real height`).toBeGreaterThan(0);
  }

  // The regression gate this check earned. `/extract` stacks the editor above the Statistics table,
  // and `EditorWorkspace` only takes a definite height when its parent is a flex container. When
  // that was missed, the stage fell back to CONTENT height and overflowed its band — the figure
  // painted through the Statistics table and across the inspector, with every number in this file
  // still reading as a pass (overflow=0, matches=1, floor clear). Two bands of one column must not
  // occupy the same pixels; that is what no per-element measurement could see.
  for (const { label, geo, doc } of results) {
    expect(
      doc.statsFound,
      `${label}: the Statistics band should exist below the editor`,
    ).toBe(true);
    expect(
      doc.statsTop ?? 0,
      `${label}: the Statistics band must start at or below the artboard stage's bottom ` +
        `(stage ends ${doc.stageBottom}, stats starts ${doc.statsTop}) — overlapping means the ` +
        `editor is overflowing its band and painting over the table`,
    ).toBeGreaterThanOrEqual(doc.stageBottom);
    expect(
      geo.stageClient,
      `${label}: the stage must fit the viewport — a stage taller than the window means the ` +
        `editor is not height-constrained by its host`,
    ).toBeLessThanOrEqual(doc.innerHeight);
  }
});
