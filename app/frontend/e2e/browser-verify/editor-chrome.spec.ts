import { expect, test } from "./fixtures";

/**
 * The rest of the Lane 3 §D list that lives on the figure editor: D-4, D-1, D-7, D-6, D-3, D-9, D-10.
 *
 * Each was an arithmetic-backed prediction from CSS that no browser had observed. These report the
 * real numbers and assert the stated PASS criterion, so each bullet can be closed or re-filed
 * honestly rather than on reasoning.
 *
 * Everything here runs in a DEFAULT build (annotation flag off) — which is what ships. D-2 and the
 * flag-on variants of D-1/D-6/D-7 are deferred Plan C territory and are deliberately not run here;
 * `ANNOTATION=on scripts/browser-verify.sh` reaches them, and results file against the annotation
 * remediation spec, never as shipped-and-fine.
 */

test("D-4 — retiring the palette strip bought the artboard its pixels", async ({ editor }) => {
  await editor.viewport(1280, 800);
  const bands = await editor.shellBands();

  console.log(
    "\n[D-4] shell bands at 1280×800\n" +
      bands.map((b) => `  ${String(b.height).padStart(4)}px  ${b.className}`).join("\n") +
      "\n",
  );

  // PASS: no band below the artboard row — no swatch row, no "Palette board — coming soon".
  const strip = editor.page.getByText(/Palette board|coming soon/i);
  expect(await strip.count(), "a retired placeholder band is back below the artboard").toBe(0);

  // What the remaining fixed chrome costs — §3.3's principle and the reason L3-01 was needed.
  const total = bands.reduce((a, b) => a + b.height, 0);
  const stage = bands.find((b) => b.height === Math.max(...bands.map((x) => x.height)));
  console.log(
    `[D-4] ${bands.length} bands, ${total}px total; the tallest (the artboard row) is ` +
      `${stage?.height}px — everything else is fixed chrome charged to the hero.\n`,
  );

  // The CommandBar is `shrink-0`, so every row it wraps into is stolen from the artboard. Take the
  // INNERMOST element containing the hint (an outer ancestor also matches and would report the whole
  // page height, which is how a measurement quietly becomes a fiction).
  const bar = await editor.page.evaluate(() => {
    const all = [...document.querySelectorAll("div")].filter((d) =>
      /Editing live/.test(d.textContent ?? ""),
    );
    const el = all[all.length - 1];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const rowH = parseFloat(getComputedStyle(el).lineHeight) || 20;
    return { height: Math.round(r.height), width: Math.round(r.width), approxRows: Math.max(1, Math.round(r.height / rowH)) };
  });

  // The ToolContextStrip's ~130-char hint: does it wrap to a second line at 1280?
  const strip2 = await editor.page.evaluate(() => {
    const el = [...document.querySelectorAll("div")].reverse().find((d) =>
      /Select tool — click a trace/.test(d.textContent ?? ""),
    );
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const lh = parseFloat(getComputedStyle(el).lineHeight) || 16;
    return { height: Math.round(r.height), lines: Math.max(1, Math.round(r.height / lh)) };
  });

  console.log(
    `[D-4] CommandBar cluster at 1280: ${JSON.stringify(bar)}\n` +
      `[D-4] ToolContextStrip at 1280: ${JSON.stringify(strip2)}\n`,
  );
});

test("D-10 — the frozen / read-only inspector", async ({ editor }) => {
  await editor.viewport(1280, 800);

  await editor.page.getByRole("button", { name: /^Freeze$/ }).click();

  // The frozen dock: a centred lock chip + max-w-[18rem] copy + "Edit a copy".
  const editCopy = editor.page.getByRole("button", { name: /Edit a copy/i });
  await expect(editCopy.first()).toBeVisible({ timeout: 30_000 });

  const geo = await editor.page.evaluate(() => {
    const btns = [...document.querySelectorAll("button")].filter((b) =>
      /Edit a copy/i.test(b.textContent ?? ""),
    );
    return {
      editCopyCount: btns.length,
      frozenLabel: /Frozen/i.test(document.body.textContent ?? ""),
    };
  });

  // A frozen figure renders through the SAME ArtboardHost — readOnly changes gestures, not sizing.
  const m = await editor.measureStage();
  console.log(
    `\n[D-10] frozen: ${JSON.stringify(geo)}\n` +
      `[D-10] artboard while frozen: stageClient=${m.stageClient} card=${m.card} ` +
      `overflow=${m.overflow} (expected card=${m.stageClient - 32})\n`,
  );
  await editor.page.screenshot({ path: "test-results/browser-verify/d10-frozen-1280x800.png" });

  expect(m.overflow, "a frozen figure must size exactly like an editable one").toBe(0);
  expect(m.card).toBe(m.stageClient - 32);

  // §D's duplicate-affordance question: the top bar's "Edit a copy" and the dock's are two buttons
  // for one action. Reported as a founder call, not asserted.
  if (geo.editCopyCount > 1) {
    console.log(
      `[D-10] FOUNDER CALL: "Edit a copy" appears ${geo.editCopyCount}× on one screen (the frozen ` +
        `command cluster AND the inspector dock) — a duplicated affordance for a single action.\n`,
    );
  }
});

test("D-1 / D-7 — the inspector tab strip at its real worst case", async ({ editor }) => {
  await editor.viewport(1280, 800);

  // Since `W-2` the dock ARRIVES collapsed at ≤1700 (owner decision #13) — the editor's room budget.
  // The tab strip's worst case is a property of the EXPANDED dock, so open it first. Doing this
  // through the spine's own control is deliberate: if the collapsed dock ever stopped offering a way
  // back, this check would fail here rather than quietly measuring nothing.
  const expand = editor.page.getByRole("button", { name: "Expand inspector" });
  if (await expand.count()) {
    await expand.click();
    await editor.page.waitForTimeout(300);
  }

  const tabs = await editor.page.evaluate(() => {
    const list = document.querySelector('[role="tablist"]');
    if (!list) return null;
    return {
      dockWidth: Math.round((list.closest("div")?.getBoundingClientRect().width ?? 0)),
      tabs: [...list.children].map((t) => {
        const label = t.querySelector("span");
        return {
          text: (t.textContent ?? "").trim(),
          track: Math.round(t.getBoundingClientRect().width),
          label: label ? Math.round(label.getBoundingClientRect().width) : 0,
        };
      }),
    };
  });

  expect(tabs, "no [role=tablist] found — the inspector did not render").not.toBeNull();
  console.log(
    `\n[D-1] inspector tabs (${tabs!.tabs.length} tabs, dock ${tabs!.dockWidth}px)\n` +
      tabs!.tabs
        .map((t) => `  ${t.text.padEnd(8)} track=${t.track}  label=${t.label}  slack=${t.track - t.label}`)
        .join("\n") +
      "\n",
  );

  // D-7: a volcano carries skill-emitted gene labels, so Marks is expected to be PRESENT here.
  // That is the transition that changes the strip's width class, and it is the 6-tab worst case
  // that survives the flag being off.
  const names = tabs!.tabs.map((t) => t.text);
  console.log(`[D-7] tabs present: ${names.join(" · ")}\n`);

  // D-1 PASS: every label's own width ≤ its trigger's content box; no neighbour collision.
  const overflowing = tabs!.tabs.filter((t) => t.label > t.track);
  expect(
    overflowing,
    `labels wider than their track (they spill — TabsTrigger is whitespace-nowrap with no truncate):\n` +
      overflowing.map((t) => `  "${t.text}": label ${t.label}px in a ${t.track}px track`).join("\n"),
  ).toEqual([]);
});

test("D-6 — the tools rail ships as a one-button column", async ({ editor }) => {
  await editor.viewport(1280, 800);

  const rail = await editor.page.evaluate(() => {
    const el = [...document.querySelectorAll("div")].find((d) =>
      /(^|\s)w-12(\s|$)/.test(d.className.toString()) && d.querySelector("button"),
    );
    if (!el) return null;
    const buttons = [...el.querySelectorAll("button")].map((b) => ({
      name: b.getAttribute("title") || b.getAttribute("aria-label") || (b.textContent ?? "").trim(),
      pressed: b.getAttribute("aria-pressed"),
      disabled: b.hasAttribute("disabled"),
    }));
    const r = el.getBoundingClientRect();
    return { width: Math.round(r.width), height: Math.round(r.height), buttons };
  });

  expect(rail, "tools rail not found").not.toBeNull();
  console.log(`\n[D-6] tools rail: ${JSON.stringify(rail)}\n`);

  // Not an assertion — a founder call (the same §3.3 "fixed chrome must justify its pixels"
  // question the palette strip failed). Reported, not closed.
  if (rail!.buttons.length === 1) {
    console.log(
      `[D-6] FOUNDER CALL: a ${rail!.width}px column holding exactly one always-pressed button ` +
        `("${rail!.buttons[0].name}", aria-pressed=${rail!.buttons[0].pressed}). Does that read as a ` +
        `toolbar or as a leftover gutter? It is ${rail!.width}px of the ${266}px the hero gets at 1280.\n`,
    );
  }
});

test("D-3 — the Export popover is not clipped by the shell's overflow-hidden", async ({ editor }) => {
  await editor.viewport(1280, 800);

  await editor.page.getByRole("button", { name: /^Export$/ }).click();
  const pop = editor.page.locator('[class*="w-72"]').first();
  await expect(pop).toBeVisible({ timeout: 15_000 });

  const geo = await editor.page.evaluate(() => {
    const p = document.querySelector('[class*="w-72"]');
    const box = p?.closest(".overflow-hidden");
    if (!p || !box) return null;
    return {
      popBottom: Math.round(p.getBoundingClientRect().bottom),
      boxBottom: Math.round(box.getBoundingClientRect().bottom),
      popHeight: Math.round(p.getBoundingClientRect().height),
    };
  });

  console.log(`\n[D-3] export popover: ${JSON.stringify(geo)}\n`);
  await editor.page.screenshot({ path: "test-results/browser-verify/d3-export-1280x800.png" });

  expect(
    geo!.popBottom,
    `the Export popover is clipped by ${geo!.popBottom - geo!.boxBottom}px — the cut-off region is ` +
      `the primary Export PNG/SVG/PDF button`,
  ).toBeLessThanOrEqual(geo!.boxBottom);
});

test("D-9 — the AI panel overlay vs the inspector dock", async ({ editor }) => {
  await editor.viewport(1280, 800);
  await editor.page.getByRole("button", { name: /^AI$/ }).click();

  const geo = await editor.page.evaluate(() => {
    const panel = document.querySelector('[class*="w-[360px]"]');
    const art = document.querySelector(".bg-artboard");
    if (!panel) return null;
    const pr = panel.getBoundingClientRect();
    const ar = art?.getBoundingClientRect();
    const z = (el: Element | null) => (el ? getComputedStyle(el).zIndex : null);
    // What actually paints at the panel's centre. Since `W-2` the artboard legitimately extends
    // UNDER the panel (the dock collapsed, so the hero is wider), which makes a geometric overlap
    // test meaningless — an overlay is SUPPOSED to overlap. The defect D-9 cares about is the
    // artboard poking THROUGH, and only hit-testing can tell the two apart.
    const probe = document.elementFromPoint(
      Math.round(pr.left + pr.width / 2),
      Math.round(pr.top + pr.height / 2),
    );
    return {
      panel: { left: Math.round(pr.left), width: Math.round(pr.width), z: z(panel) },
      artboardZ: z(art?.closest("[class*='z-']") ?? null),
      artboardRight: ar ? Math.round(ar.right) : null,
      overlaps: ar ? ar.right > pr.left : null,
      /** True when the panel (or something inside it) is what the user actually sees there. */
      panelOnTop: !!probe && (panel === probe || panel.contains(probe)),
      topmost: probe ? probe.tagName + "." + String(probe.className).slice(0, 30) : null,
    };
  });

  console.log(`\n[D-9] AI panel: ${JSON.stringify(geo)}\n`);
  await editor.page.screenshot({ path: "test-results/browser-verify/d9-ai-panel-1280x800.png" });

  // (a) the close affordance must be reachable while the panel is open.
  const close = editor.page.getByRole("button", { name: /close/i }).first();
  expect(
    await close.count(),
    "the AI panel has no reachable close affordance",
  ).toBeGreaterThan(0);

  // (c) the artboard must not poke THROUGH the panel.
  //
  // This used to assert the artboard's right edge never reached the panel's left edge, which held
  // only because the 330px inspector dock kept the hero narrow. `W-2` collapses that dock, so the
  // artboard now legitimately extends under the panel — and an overlay overlapping content is the
  // whole point of an overlay, not a defect. The question was always "what does the user SEE
  // there?", so it is hit-tested now: the panel must own the pixels it covers, whatever the
  // geometry underneath. Verified visually first (test-results/browser-verify/d9-ai-panel-*.png):
  // the figure is cleanly cut off at the panel's edge.
  expect(
    geo!.panelOnTop,
    `the AI panel does NOT own the pixels at its own centre — topmost element there is ` +
      `${geo!.topmost}. The artboard (right edge ${geo!.artboardRight}, z=${geo!.artboardZ}) is ` +
      `poking through the panel (left ${geo!.panel.left}, z=${geo!.panel.z}).`,
  ).toBe(true);
});
