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
 * It began as sizing evidence and is now ALSO the regression gate for `W-1`: the figure must reflow
 * when its CONTAINER resizes, not only when the window does. Before the fix, collapsing the rail
 * grew the card 208px and the plot 0px, and a window nudge then added 205px. After it, the plot
 * gains on the collapse alone and the nudge has nothing left to fix — which is what the two
 * assertions at the bottom pin, in that order.
 */
test("remedy sizing — what collapsing the existing rail buys the hero at 1280", async ({ editor }) => {
  await editor.viewport(1280, 800);

  // Since `W-2` the workrail ARRIVES collapsed at ≤1700 (owner decision #13), so "collapse it and
  // measure the gain" has to start by expanding it. That is not a workaround — driving both
  // directions is strictly better evidence, because it proves the rail's own control still round
  // trips AND that the reflow follows it either way.
  const expandRail = editor.page.getByRole("button", { name: "Expand rail" });
  if (await expandRail.count()) {
    await expandRail.click();
    await editor.page.waitForTimeout(600);
  }

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

  const fromCollapse = (after.plotArea ?? 0) - (before.plotArea ?? 0);
  const fromNudge = (afterNudge.plotArea ?? 0) - (after.plotArea ?? 0);
  const gain = (afterNudge.plotArea ?? 0) - (before.plotArea ?? 0);
  const pct = (v: number | null) => `${Math.round(((v ?? 0) / 1280) * 100)}%`;

  console.log(
    `\n[remedy sizing @1280×800]\n` +
      `  rail EXPANDED   stage=${before.stage}  card=${before.card}  plotArea=${before.plotArea} (${pct(before.plotArea)})\n` +
      `  rail COLLAPSED  stage=${after.stage}  card=${after.card}  plotArea=${after.plotArea} (${pct(after.plotArea)})\n` +
      `  + window nudge  stage=${afterNudge.stage}  card=${afterNudge.card}  plotArea=${afterNudge.plotArea} (${pct(afterNudge.plotArea)})\n` +
      `\n` +
      `  → the card gained ${(after.card ?? 0) - (before.card ?? 0)}px from collapsing alone, and the plot ` +
      `gained ${fromCollapse}px.\n` +
      `  → a window-resize event then added ${fromNudge}px more (${gain}px total).\n` +
      `  → §D's target is 506px; still short by ${Math.max(0, 506 - (afterNudge.plotArea ?? 0))}px, which is\n` +
      `    what the inspector dock (330px, no collapse control) + zoom-to-fit would have to cover.\n`,
  );

  await editor.page.screenshot({ path: "test-results/browser-verify/remedy-rail-collapsed-1280x800.png" });

  // W-1's contract, in the order that makes a regression legible. The first assertion is the fix
  // itself; the second is what proves it happened for the right reason — if the plot only grows
  // once a window event arrives, the container-resize path is dead again and the first assertion
  // alone would still pass on the nudge.
  expect(
    fromCollapse,
    "W-1: the figure must reflow when its CONTAINER resizes — collapsing the rail, no window event",
  ).toBeGreaterThan(0);
  expect(
    fromNudge,
    "W-1: a window resize must find nothing left to fix (>2px means the container path is broken)",
  ).toBeLessThanOrEqual(2);
});
