// Figure-render perf audit (architecture-consistency Task E2).
//
// Drives N figure switches through the REAL editor and reports cold vs warm render
// timing (p50/p95/peak, from the in-app `window.__selomPerf` telemetry) plus peak JS
// heap and the live WebGL-canvas count — the repeatable companion to the chrome-devtools
// heap-snapshot diff. Self-contained: it seeds a synthetic project (two scattergl figures)
// straight into localStorage, so it needs no backend and no curated fixtures — only a dev
// server (default http://localhost:3000; override with PERF_BASE_URL).
//
// Uses system Chrome (channel: "chrome"), matching playwright.config.ts (no Chromium
// download). Run:  node scripts/perf-audit.mjs   (with `npm run dev` already up)
//
// Exit non-zero if the live canvas count climbs past the WebGL budget — a leak signal.

import { chromium } from "@playwright/test";

const BASE_URL = process.env.PERF_BASE_URL ?? "http://localhost:3000";
const SWITCHES = Number(process.env.PERF_SWITCHES ?? 20);
const POINTS = Number(process.env.PERF_POINTS ?? 8000);
const PROJECT_ID = "perf-audit-proj";
const CANVAS_BUDGET = 8; // mirrors MAX_GL_CONTEXTS — the live canvas count must stay bounded.

/** A synthetic scattergl figure spec with `n` points (a stand-in for a real volcano). */
function scatterSpec(n, seed) {
  const x = [];
  const y = [];
  for (let i = 0; i < n; i++) {
    x.push(Math.sin((i + seed) * 0.7) * 5);
    y.push(Math.abs(Math.cos((i + seed) * 0.9)) * 6);
  }
  return {
    data: [{ type: "scattergl", mode: "markers", name: "pts", x, y, marker: { size: 5 } }],
    layout: { title: { text: `Perf ${seed}` }, xaxis: {}, yaxis: {} },
  };
}

/** The denormalized ProjectState the mock store hydrates from `selom.projects.v1`. */
function seededState() {
  const t = 1_749_000_000_000;
  return {
    projects: [{ id: PROJECT_ID, name: "Perf audit", color: "#22d3ee", createdAt: t }],
    datasets: [
      {
        id: "perf-ds",
        projectId: PROJECT_ID,
        filename: "perf.csv",
        modality: "bulk RNA-seq",
        currentSha256: "perfsha",
        createdAt: t,
      },
    ],
    installs: [{ id: "perf-i1", projectId: PROJECT_ID, skillId: "selom.volcano", installedAt: t }],
    figures: [
      { id: "perf-fA", projectId: PROJECT_ID, datasetId: "perf-ds", skillId: "selom.volcano", title: "Perf A", spec: scatterSpec(POINTS, 1), createdAt: t },
      { id: "perf-fB", projectId: PROJECT_ID, datasetId: "perf-ds", skillId: "selom.volcano", title: "Perf B", spec: scatterSpec(POINTS, 2), createdAt: t + 1 },
    ],
    geneSets: [],
  };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function clickByText(page, txt) {
  return page.evaluate((t) => {
    const el = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").includes(t));
    if (el) {
      el.click();
      return true;
    }
    return false;
  }, txt);
}

/** Poll until a button containing `txt` exists (the React app has hydrated + rendered). */
async function waitForButton(page, txt, timeoutMs = 60000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const found = await page.evaluate(
      (t) => [...document.querySelectorAll("button")].some((b) => (b.textContent || "").includes(t)),
      txt,
    );
    if (found) return true;
    await sleep(200);
  }
  return false;
}

async function waitForPlot(page, timeoutMs = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const ok = await page.evaluate(() => !!document.querySelector(".js-plotly-plot") && document.querySelectorAll("canvas").length > 0);
    if (ok) return true;
    await sleep(150);
  }
  return false;
}

async function probe(page) {
  return page.evaluate(() => ({
    canvas: document.querySelectorAll("canvas").length,
    stats: window.__selomPerf ? window.__selomPerf.stats() : null,
    heapMB: window.__selomPerf ? window.__selomPerf.heapMB() : null,
  }));
}

async function main() {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  // Seed the project before any app JS runs (every navigation, this origin).
  await context.addInitScript((state) => {
    localStorage.setItem("selom.projects.v1", JSON.stringify(state));
  }, seededState());
  const page = await context.newPage();

  await page.goto(`${BASE_URL}/p/${PROJECT_ID}`, { waitUntil: "domcontentloaded", timeout: 120000 });

  // Open figure A → first (cold) draw. Wait for the project UI to hydrate + render first.
  if (!(await waitForButton(page, "Perf A"))) throw new Error("project never rendered a 'Perf A' figure control");
  if (!(await clickByText(page, "Perf A"))) throw new Error("could not find a button to open figure 'Perf A'");
  if (!(await waitForPlot(page))) throw new Error("figure never rendered");
  await sleep(400);
  const cold = await probe(page);
  const coldMs = cold.stats?.peak ?? null;

  // Warm pass: reset telemetry, drive the switches.
  await page.evaluate(() => window.__selomPerf.reset());
  let maxCanvas = 0;
  let peakHeap = 0;
  for (let i = 0; i < SWITCHES; i++) {
    await clickByText(page, i % 2 === 0 ? "Perf B" : "Perf A");
    await waitForPlot(page);
    await sleep(180);
    const p = await probe(page);
    maxCanvas = Math.max(maxCanvas, p.canvas);
    if (p.heapMB) peakHeap = Math.max(peakHeap, p.heapMB);
  }
  const warm = await probe(page);

  console.log("\n=== Selom figure-render perf audit ===");
  console.log(`base           : ${BASE_URL}`);
  console.log(`switches       : ${SWITCHES}   points/figure: ${POINTS}`);
  console.log(`cold first draw: ${coldMs == null ? "n/a" : coldMs.toFixed(1) + " ms"}  (dev: includes route compile + Plotly chunk load)`);
  console.log(`warm renders   : count ${warm.stats.count}`);
  console.log(`  p50          : ${warm.stats.p50.toFixed(1)} ms`);
  console.log(`  p95          : ${warm.stats.p95.toFixed(1)} ms`);
  console.log(`  peak         : ${warm.stats.peak.toFixed(1)} ms`);
  console.log(`peak heap      : ${peakHeap ? peakHeap.toFixed(1) + " MB" : "n/a (no performance.memory)"}`);
  console.log(`max live canvas: ${maxCanvas}  (budget ${CANVAS_BUDGET})`);

  await browser.close();

  if (maxCanvas > CANVAS_BUDGET) {
    console.error(`\nFAIL: live canvas count ${maxCanvas} exceeded the budget ${CANVAS_BUDGET} — possible WebGL-context leak.`);
    process.exit(1);
  }
  console.log("\nOK: canvas count stayed within budget.\n");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
