import { expect, test } from "./fixtures";

/**
 * REMEDY SIZING for the 1280 width defect (D-5's also-confirm failure).
 *
 * The defect: at 1280×800 the plotting area is 90px because fixed columns take ~70% of the viewport
 * (sidebar 256 + project workrail 256 + tools rail 48 + inspector dock 330).
 *
 * The proposal's §3.4 ("Give the figure room: collapse, and zoom-to-fit") assumed the shell ships no
 * collapse control. That is only partly true — the WORKRAIL already collapses to a spine of stage
 * dots (`workrail.tsx`, `aria-label="Collapse rail"`). So before planning any build, measure what
 * the controls that ALREADY EXIST buy, and what is left over for new work.
 *
 * This is sizing evidence, not a pass/fail gate — it asserts only that collapsing helps at all.
 */
test("remedy sizing — what collapsing the existing rail buys the hero at 1280", async ({ editor }) => {
  await editor.viewport(1280, 800);

  const before = await editor.horizontalChrome();

  await editor.page.getByRole("button", { name: "Collapse rail" }).click();
  await editor.page.waitForTimeout(600);

  const after = await editor.horizontalChrome();

  // If the card grew but the plot did not, the figure is not reflowing into the room it was given.
  // Plotly's responsive resize listens on WINDOW resize; a container that changes size on its own
  // (a rail collapsing) fires no window event. Nudge the viewport to force one and re-measure — the
  // difference between `after` and `afterNudge` isolates "no room" from "room, but no reflow".
  await editor.viewport(1281, 800);
  await editor.viewport(1280, 800);
  const afterNudge = await editor.horizontalChrome();

  const gain = (afterNudge.plotArea ?? 0) - (before.plotArea ?? 0);
  const pct = (v: number | null) => `${Math.round(((v ?? 0) / 1280) * 100)}%`;

  console.log(
    `\n[remedy sizing @1280×800]\n` +
      `  rail EXPANDED   stage=${before.stage}  card=${before.card}  plotArea=${before.plotArea} (${pct(before.plotArea)})\n` +
      `  rail COLLAPSED  stage=${after.stage}  card=${after.card}  plotArea=${after.plotArea} (${pct(after.plotArea)})\n` +
      `  + window nudge  stage=${afterNudge.stage}  card=${afterNudge.card}  plotArea=${afterNudge.plotArea} (${pct(afterNudge.plotArea)})\n` +
      `\n` +
      `  → the card gained ${(after.card ?? 0) - (before.card ?? 0)}px from collapsing alone, and the plot ` +
      `gained ${(after.plotArea ?? 0) - (before.plotArea ?? 0)}px.\n` +
      `  → after a window-resize event the plot gained ${gain}px total.\n` +
      `  → §D's target is 506px; still short by ${Math.max(0, 506 - (afterNudge.plotArea ?? 0))}px, which is\n` +
      `    what the inspector dock (330px, no collapse control) + zoom-to-fit would have to cover.\n`,
  );

  await editor.page.screenshot({ path: "test-results/browser-verify/remedy-rail-collapsed-1280x800.png" });

  expect(gain, "collapsing the rail should give the artboard more room").toBeGreaterThan(0);
});
