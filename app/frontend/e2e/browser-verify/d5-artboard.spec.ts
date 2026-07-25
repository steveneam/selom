import { expect, test } from "./fixtures";

/**
 * D-5 · "The artboard is the hero — does it still clip?" (lane-wraps/lane3.md §D)
 *
 * A24 was: the white card kept the pre-shell `height: min(74vh, 720px)` after it became a flex child
 * of a host whose height is only what the shell's bands leave over — so it asked for 720px inside a
 * ~548px stage and ~24% of the hero (x-axis title, legend) sat below the visible area. `L3-01`
 * removed the inline height and made a responsive figure stretch to the stage, bracketed by
 * `min-h-[20rem] max-h-[56rem]`.
 *
 * That fix was reasoned + unit-pinned, never observed. This is the observation.
 *
 *   PASS  overflow === 0  AND  card ≈ stageClient − 32   (the stage's lg:p-4 gutter, 16px × 2)
 *   FAIL  card ≈ min(0.74 × innerHeight, 720) with stageScroll > stageClient  (A24 returning)
 *
 * It also reports `stageClient` at each viewport: `min-h-[20rem]` (320px) is a floor chosen by
 * arithmetic, and if a real stage comes near 352px the floor is wrong for real screens.
 */

// Desktop only — Selom has no mobile. 1920 is here for the `88rem` (1408px) centring cap.
const VIEWPORTS = [
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
];

const GUTTER = 32; // lg:p-4 → 16px top + 16px bottom
const MAX_W = 1408; // 88rem

test("D-5 — the responsive artboard fills its stage and never clips", async ({ editor }) => {
  const rows: string[] = [];
  const failures: string[] = [];

  for (const vp of VIEWPORTS) {
    await editor.viewport(vp.width, vp.height);
    const m = await editor.measureStage();

    // Visual evidence at every viewport — a number can satisfy `card === stageClient - 32` while the
    // figure is still unusable, and only a picture shows that.
    await editor.page.screenshot({ path: `test-results/browser-verify/d5-${vp.width}x${vp.height}.png` });

    // Exactly one artboard stage, or we are not on the figure editor and every number below is noise.
    expect(m.matches, `expected exactly one .bg-artboard stage at ${vp.width}×${vp.height}`).toBe(1);

    const expectedCard = m.stageClient - GUTTER;
    const cardDelta = m.card - expectedCard;
    // The A24 signature, computed so the report can say "not this" rather than merely "fine".
    const a24Card = Math.min(0.74 * vp.height, 720);

    rows.push(
      `  ${vp.width}×${vp.height}  stageClient=${m.stageClient}  stageScroll=${m.stageScroll}  ` +
        `card=${m.card}  (expected ${expectedCard}, Δ${cardDelta >= 0 ? "+" : ""}${cardDelta})  ` +
        `overflow=${m.overflow}  cardWidth=${m.cardWidth}  ` +
        `gutters L${m.gutterLeft}/R${m.gutterRight}  [A24 would be card≈${Math.round(a24Card)}]`,
    );

    if (m.overflow !== 0) failures.push(`${vp.width}×${vp.height}: overflow=${m.overflow} (must be 0)`);
    if (Math.abs(cardDelta) > 2) {
      failures.push(
        `${vp.width}×${vp.height}: card=${m.card} but stageClient−32=${expectedCard} (Δ${cardDelta})`,
      );
    }

    // The floor is the new risk L3-01 introduced — only a browser can settle it.
    if (m.stageClient < 400) {
      rows.push(
        `    ⚠ stageClient=${m.stageClient} is within 80px of the 352px floor-engagement point — ` +
          `min-h-[20rem] may be too high for real screens.`,
      );
    }

    // Horizontal centring once the card caps at 88rem (only visible above ~1470px of stage width).
    if (m.stageClientWidth > MAX_W) {
      expect(m.cardWidth, `card should cap at ${MAX_W}px at ${vp.width}px`).toBeLessThanOrEqual(MAX_W + 1);
      expect(
        Math.abs(m.gutterLeft - m.gutterRight),
        `card should be horizontally centred at ${vp.width}px (L${m.gutterLeft}/R${m.gutterRight})`,
      ).toBeLessThanOrEqual(2);
    }
  }

  // The hero's own parts must be visible WITHOUT scrolling inside the stage — that is what A24 broke,
  // and a pure height match would not prove it.
  await editor.viewport(1280, 800);
  const parts = await editor.page.evaluate(() => {
    const cards = [...document.querySelectorAll(".bg-artboard")].filter((el) =>
      el.parentElement?.classList.contains("overflow-auto"),
    );
    const stage = cards[0]?.parentElement as HTMLElement | undefined;
    const plot = document.querySelector(".js-plotly-plot");
    if (!stage || !plot) return null;
    const sb = stage.getBoundingClientRect();
    const within = (el: Element | null) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: Math.round(r.top), bottom: Math.round(r.bottom), inside: r.bottom <= sb.bottom + 1 && r.top >= sb.top - 1 };
    };
    // Plotly's x-axis title carries the `xtitle` class; the legend is `.legend`.
    const plotArea = plot.querySelector(".xy .nsewdrag, .xy rect.nsewdrag") as SVGGraphicsElement | null;
    return {
      xTitle: within(plot.querySelector(".xtitle")),
      legend: within(plot.querySelector(".legend")),
      xTitleText: plot.querySelector(".xtitle")?.textContent ?? null,
      plotWidth: plotArea ? Math.round(plotArea.getBoundingClientRect().width) : null,
      stageBottom: Math.round(sb.bottom),
    };
  });

  expect(parts, "could not locate the stage + plotly plot at 1280×800").not.toBeNull();
  rows.push(
    `  1280×800 hero parts: xTitle=${JSON.stringify(parts!.xTitle)} (“${parts!.xTitleText}”)  ` +
      `legend=${JSON.stringify(parts!.legend)}  plotWidth=${parts!.plotWidth}`,
  );

  if (parts!.xTitle && !parts!.xTitle.inside) {
    failures.push(`1280×800: the x-axis title is below the stage's visible area (A24's exact symptom)`);
  }
  if (parts!.legend && !parts!.legend.inside) {
    failures.push(`1280×800: the legend is below the stage's visible area (A24's exact symptom)`);
  }

  console.log("\n[D-5] artboard geometry\n" + rows.join("\n") + "\n");

  expect(editor.pageErrors, `page errors during D-5:\n${editor.pageErrors.join("\n")}`).toEqual([]);
  expect(failures, `D-5 FAILURES:\n${failures.join("\n")}`).toEqual([]);
});

/**
 * D-5's "also confirm" clause, kept as its own test so the A24 verdict above stays unambiguous.
 *
 * §D asked to confirm the figure "is still LEGIBLE at 1280 (tick labels, legend, colour bar at
 * ~506px of plot width, per §D's own number)". 506px was an assumption about how much width the
 * stage gets — never measured. The height fix (`L3-01`) is orthogonal to this and is not the cause;
 * the cause is how many FIXED COLUMNS stand between the viewport edge and the hero.
 */
test("D-5 (also-confirm) — the figure is legible at 1280", async ({ editor }) => {
  const EXPECTED_PLOT_W = 506; // §D's own number

  const report: string[] = [];
  let widest = 0;
  for (const vp of VIEWPORTS) {
    await editor.viewport(vp.width, vp.height);
    const m = await editor.horizontalChrome();
    widest = Math.max(widest, m.plotArea ?? 0);
    report.push(
      `  ${vp.width}×${vp.height}  main=${m.main}  stage=${m.stage}  card=${m.card}  ` +
        `plotArea=${m.plotArea}  ` +
        `fixed=[${m.columns.filter((c2) => !c2.isAncestor).map((c2) => c2.width).join(",")}]`,
    );
  }
  console.log("\n[D-5 also-confirm] horizontal chrome\n" + report.join("\n") + "\n");

  await editor.viewport(1280, 800);
  const c = await editor.horizontalChrome();

  // Attribute the shortfall to the fixed columns actually standing beside the artboard, measured
  // rather than guessed: everything in the walk that is NOT an ancestor of the stage.
  const fixed = c.columns.filter((col) => !col.isAncestor);
  const fixedTotal = c.sidebar! + fixed.reduce((a, col) => a + col.width, 0);
  const breakdown = [`sidebar ${c.sidebar}`, ...fixed.map((col) => `${col.width}`)].join(" + ");

  expect(
    c.plotArea,
    `at 1280×800 the plotting area is ${c.plotArea}px — not the ~${EXPECTED_PLOT_W}px §D assumed.\n` +
      `  chain: viewport ${c.viewport} → main ${c.main} → stage ${c.stage} → card ${c.card} → ` +
      `plot ${c.plotArea}\n` +
      `  fixed columns: ${breakdown} = ${fixedTotal}px ` +
      `(${Math.round((fixedTotal / c.viewport!) * 100)}% of the viewport) — the sidebar, the project ` +
      `workrail (w-64), the 48px tools rail and the 330px inspector dock.\n` +
      `  The hero gets ${Math.round((c.card! / c.viewport!) * 100)}% of the viewport and the plotting ` +
      `area ${Math.round((c.plotArea! / c.viewport!) * 100)}%. Gene labels overlap into an unreadable ` +
      `cluster (see test-results/browser-verify/d5-1280x800.png).\n` +
      `  This is a WIDTH defect, independent of A24's height fix — L3-01 is working exactly as ` +
      `specified — and it is worst precisely where a laptop user lives. The same figure is legible ` +
      `at the widest viewport checked (${widest}px of plot).`,
  ).toBeGreaterThanOrEqual(EXPECTED_PLOT_W);
});
