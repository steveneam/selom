import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { SCRNA_NORMALIZE_HELP, overlayParamKeys, paramFieldsFromSpec } from "./params";
import type { BackendParamSpec, ParamField } from "./params";
import { SKILL_PARAM_SPECS } from "@/mocks/skill-spec-fixture";

/**
 * Registry-completeness gate (architecture-consistency Task B5).
 *
 * The backend `skills/<slug>/skill.json` param_spec is the ONE source of truth for the
 * tunable knobs a skill accepts. Two frontend mirrors decorate it: the `params.ts`
 * PRESENTATION overlay (labels/widgets) and the `dev:mock` param-spec fixture (the
 * offline twin of `GET /skills/{id}`). Either can drift — an overlay key the runner
 * doesn't have, or a fixture that's missing a control live renders. `paramFieldsFromSpec`
 * only *warns* (console) on the overlay case; this gate promotes that drift to a FAILING
 * test (acceptance: a typo'd / renamed param fails CI, not just a dev console warn).
 *
 * It reads the REAL backend skill.json files — the cross-lane read is the point: the test
 * exists precisely to catch FE↔BE contract drift. No engine, no network → it stays in the
 * fast gate. (The capability half — `_capabilities.py` `_PROFILES` ↔ the registry — is
 * Python-native and lives in the backend's `tests/test_capabilities.py`.)
 */

// Resolve the backend skills dir relative to THIS file: lib/catalog → app/frontend → app → backend.
const SKILLS_DIR = fileURLToPath(new URL("../../../backend/skills", import.meta.url));

/**
 * Walk `skills/` (including the `proprietary/<id>/` namespace) → { skillId: Set<param key> },
 * keyed by each skill.json's own `id` field (robust to the proprietary nesting). Throws if the
 * dir is unreadable — a broken path must fail loudly, never yield an empty map (false green).
 */
function loadParamSpecs(): Record<string, Set<string>> {
  const out: Record<string, Set<string>> = {};
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(p);
      } else if (entry.name === "skill.json") {
        const json = JSON.parse(fs.readFileSync(p, "utf8"));
        if (json?.id) out[json.id] = new Set(Object.keys(json.param_spec ?? {}));
      }
    }
  };
  walk(SKILLS_DIR);
  return out;
}

/**
 * The same walk, keeping each param_spec ENTRY rather than just its key — the merge's real input,
 * so a test can assert what `ParamControl` will actually be handed (bounds, options, defaults)
 * instead of only which keys exist.
 */
function loadFullParamSpecs(): Record<string, BackendParamSpec> {
  const out: Record<string, BackendParamSpec> = {};
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(p);
      } else if (entry.name === "skill.json") {
        const json = JSON.parse(fs.readFileSync(p, "utf8"));
        if (json?.id) out[json.id] = (json.param_spec ?? {}) as BackendParamSpec;
      }
    }
  };
  walk(SKILLS_DIR);
  return out;
}

const SPECS = loadParamSpecs();
const FULL_SPECS = loadFullParamSpecs();
const OVERLAYS = overlayParamKeys();

describe("registry-completeness — backend skill.json is reachable", () => {
  // Guards against a silently-broken relative path: an empty SPECS would make every
  // for-loop below vacuously pass. A few known skills must always be present.
  it("loads param_specs for the on-disk skills", () => {
    expect(Object.keys(SPECS).length).toBeGreaterThan(20);
    for (const id of ["volcano", "heatmap", "umap_scrna", "erg_traces"]) {
      expect(SPECS[id], `no skill.json found for "${id}"`).toBeDefined();
    }
  });
});

describe("params.ts overlay ↔ backend param_spec (promotes warnDeadKnob)", () => {
  it("every overlay skill has a backing skill.json", () => {
    const missing = Object.keys(OVERLAYS).filter((id) => !SPECS[id]);
    expect(missing, `overlay skills with no backing skill.json: ${missing.join(", ")}`).toEqual([]);
  });

  it("every overlay param key exists in the backend param_spec (no dead knobs)", () => {
    const dead: string[] = [];
    for (const [id, keys] of Object.entries(OVERLAYS)) {
      const spec = SPECS[id];
      if (!spec) continue; // reported by the test above
      for (const key of keys) if (!spec.has(key)) dead.push(`${id}.${key}`);
    }
    expect(dead, `overlay keys absent from the backend param_spec: ${dead.join(", ")}`).toEqual([]);
  });
});

describe("dev:mock param-spec fixture ↔ backend param_spec", () => {
  it("renders the same controls as live (every overlay key in the real spec is in the fixture)", () => {
    const gaps: string[] = [];
    for (const [id, keys] of Object.entries(OVERLAYS)) {
      const spec = SPECS[id];
      if (!spec) continue;
      const fixture = SKILL_PARAM_SPECS[id];
      for (const key of keys) {
        if (!spec.has(key)) continue; // dead-knob case handled above
        if (!fixture || !(key in fixture)) gaps.push(`${id}.${key}`);
      }
    }
    expect(gaps, `fixture missing controls the live spec serves: ${gaps.join(", ")}`).toEqual([]);
  });

  it("carries no stale key (every fixture key still exists in the backend param_spec)", () => {
    const stale: string[] = [];
    for (const [id, fixture] of Object.entries(SKILL_PARAM_SPECS)) {
      const spec = SPECS[id];
      expect(spec, `fixture declares "${id}" with no backing skill.json`).toBeDefined();
      if (!spec) continue;
      for (const key of Object.keys(fixture)) if (!spec.has(key)) stale.push(`${id}.${key}`);
    }
    expect(stale, `fixture keys removed/renamed in the backend param_spec: ${stale.join(", ")}`).toEqual([]);
  });

  /**
   * Key presence in both directions is not enough. The fixture can name every key the live spec
   * names and still render a DIFFERENT control, because the widget's bounds come from the spec:
   * `mergeField` reads `min`/`max`/`default`/`options` straight through, and an `<input
   * type="range">` with no min/max silently falls back to 0–100. So a fixture drifting only in its
   * numbers gives `dev:mock` a slider that cannot express the knob while live renders one that can
   * — the exact defect class this file's slider guards exist for, in the one environment those
   * guards never look at (they read the real specs, not the fixture).
   *
   * `note` is deliberately not compared: it is help-text fallback (`help: pres.help ?? ps.note`),
   * so a divergence there is cosmetic in a dev-only mock and would make this guard noisy.
   */
  it("renders the SAME control as live (bounds, default and options match, not just the key)", () => {
    const drift: string[] = [];
    for (const [id, fixture] of Object.entries(SKILL_PARAM_SPECS)) {
      const real = FULL_SPECS[id];
      if (!real) continue; // reported by the test above
      for (const [key, fx] of Object.entries(fixture)) {
        const rl = real[key];
        if (!rl) continue; // stale-key case handled above
        for (const field of ["type", "default", "min", "max"] as const) {
          if (fx[field] !== rl[field]) {
            drift.push(`${id}.${key}.${field} (fixture ${JSON.stringify(fx[field])} vs live ${JSON.stringify(rl[field])})`);
          }
        }
        if (JSON.stringify(fx.options ?? null) !== JSON.stringify(rl.options ?? null)) {
          drift.push(`${id}.${key}.options (fixture ${JSON.stringify(fx.options ?? null)} vs live ${JSON.stringify(rl.options ?? null)})`);
        }
      }
    }
    expect(
      drift,
      `fixture params whose rendered control would differ from live — copy the value from the ` +
        `backend skill.json: ${drift.join("; ")}`,
    ).toEqual([]);
  });
});

/**
 * Reachability: a skill the backend RUNS must be nameable and runnable from the app.
 *
 * `getSkill(id)` is how ~20 surfaces resolve a skill's name, tier and icon — and the Workbench gates
 * its Apply button on `getSkill(id)?.tier === "verified"`. It used to read the static seed alone, so
 * a skill present in `GET /skills` but never hand-added to `seed.ts` rendered as its RAW ID with a
 * "Queued" badge and a DISABLED Apply: installable from the Store, then dead. Measured 2026-08-04:
 * 19 of 44 live skills, including every plot type built in the preceding sessions.
 *
 * Nothing could see it — the backend serves them, the param specs merge, the overlays exist — until a
 * real browser drove the real Workbench [[selom-shipped-not-reachable]]. `getSkill` now prefers the
 * live registry, and this is the executable form of that guarantee: it reads the same on-disk
 * `skill.json` files the rest of this file does, so the drift cannot come back silently.
 */
describe("reachability — every backend skill can be resolved by the app", () => {
  /** Catalog ids the backend actually serves as runnable (registry.py prefixes them `selom.`). */
  function backendCatalogIds(): string[] {
    const out: string[] = [];
    const walk = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(p);
        else if (entry.name === "skill.json") {
          const json = JSON.parse(fs.readFileSync(p, "utf8"));
          if (json?.id) out.push(`selom.${json.id}`);
        }
      }
    };
    walk(SKILLS_DIR);
    return out;
  }

  it("resolves every backend skill once the live registry is published", async () => {
    const { setLiveSkills } = await import("./live-skills");
    const { getSkill } = await import("./seed");
    const ids = backendCatalogIds();
    expect(ids.length).toBeGreaterThan(20);

    // Simulate what `loadCatalog()` does on a live backend: publish the registry.
    setLiveSkills(ids.map((id) => ({ id, name: id, tier: "verified" }) as never));
    const unresolved = ids.filter((id) => !getSkill(id));
    expect(unresolved, `skills the app cannot name or run: ${unresolved.join(", ")}`).toEqual([]);
  });

  it("falls back to the seed when the registry is unavailable (offline is not a crash)", async () => {
    const { setLiveSkills } = await import("./live-skills");
    const { getSkill } = await import("./seed");
    setLiveSkills([]); // backend down → `loadCatalog` keeps the seed
    // Backend-down is the ONLY state the seed answers in, so the bar is the same one the live
    // registry meets: every skill still nameable. It used to be 25 of 44 (`getSkill` returning
    // undefined for the rest), which is why the seed is generated now — see the drift guard below.
    expect(getSkill("selom.volcano")?.name).toBeTruthy();
    const unseeded = backendCatalogIds().filter((id) => !getSkill(id));
    expect(unseeded, `skills the OFFLINE app cannot name: ${unseeded.join(", ")}`).toEqual([]);
  });
});

/**
 * Control coverage: every backend knob either RENDERS a control, or is a named, tracked waiver.
 *
 * THE CLASS. Two sessions running, "shipped" turned out not to mean "reachable": 17 routes with no
 * FE call site, then 19 skills behind a disabled Apply. Both are now guarded. Neither guard can see
 * the next layer down — a skill that resolves, installs and runs, whose KNOBS the user cannot touch.
 *
 * `paramFieldsFromSpec` iterates the presentation OVERLAY, not the backend spec, so a skill with no
 * overlay renders exactly zero controls. First measured 2026-08-04: **171 of 313 knobs across 36
 * skills**, 18 of them with no overlay at all. The workbench then tells the user "Runs with smart
 * defaults — ready to apply", which reads as a product decision and is usually just an absent
 * overlay. The sharpest case was `volcano`, the flagship: it said "Tune the options" while
 * `fc_threshold`, `fdr_threshold` and `top_n` — the three knobs that decide what the volcano SHOWS
 * — were API-only.
 *
 * Worked down the same day to **148 of 313 across 27 skills** (15 with no overlay): `volcano` and
 * `proteomics_de` (both cutoffs + the labelled-gene count, and proteomics' imputation strategy,
 * which moves a result further than the test choice does), the three over-representation skills
 * that share one gene-list contract (`enrichment` · `pathway` · `go_graph`), and the one-line
 * gaps (`ridge.order` · `slope.order` · `sankey.max_links` · `heatmap.groupby`). `sankey` is worth
 * naming: `max_links` is its ONLY knob, so that skill rendered an empty parameter panel.
 *
 * Second pass 2026-08-05, worked by CLUSTER rather than down the list: the scRNA prep vocabulary
 * (`markers` · `trajectory` · `pseudotime_genes` · `mixing_metrics` · `annotate` · `violin` ·
 * `cepo`) plus the singles (`upset` · `string_network` · `corr_heatmap` · `pca` · `pvca` ·
 * `scorecard`). Two shared blocks in `params.ts` carry the vocabulary — and the interesting part is
 * what they EXCLUDE. Four skills declare a `normalize` that is not the scRNA one (`pvca` scales to
 * unit variance, `scorecard` min–max scales metric columns, `confusion` is a str enum) and
 * `pseudotime_genes.groupby` never reaches its figure at all. Sharing on a matching key name rather
 * than a matching meaning would have mislabelled all four.
 *
 * WHY A WAIVER LIST AND NOT A THRESHOLD. A count ratchets down and tells you nothing about what is
 * missing; this names every gap, so the backlog is readable and a new skill cannot quietly join it.
 * Same shape as `test_reachability_guard.py`. It is exact in BOTH directions on purpose: adding a
 * control fails until the waiver is deleted, so the list cannot rot into fiction.
 */
const API_ONLY_KNOBS: Record<string, string[]> = {
  confusion: ["true_order", "predicted_order"],
  erg_bwave_bar: ["value_col", "stimulus_type", "manual_marks", "ab_detector"],
  erg_flicker: ["mark_labels", "manual_marks", "fourier"],
  erg_intensity_response: ["value_col", "stimulus_type", "error", "spread", "points", "band_alpha",
    "boundary_lines", "band_color", "manual_marks", "ab_detector"],
  erg_traces: ["role", "stimulus_type", "marks", "mark_labels", "manual_marks",
    "ab_detector", "oscillatory_potentials", "phnr"],
  facs_gating: ["x_channel", "y_channel", "plot", "compensate", "comp_matrix", "transform",
    "transform_t", "cofactor", "bins", "max_events", "gates"],
  integration: ["n_neighbors", "n_pcs", "color_by", "max_iter_harmony"],
  lollipop: ["baseline", "order"],
  normalization_qc: ["groupby", "max_cells", "filter", "nmads", "doublets", "doublet_threshold"],
  umap_scrna: ["color_by", "embedding"],
};

describe("control coverage — a knob the backend accepts is a knob the user can reach", () => {
  /** `{skill: [knobs with no rendered control]}`, derived from the same two sources as above. */
  function uncontrolled(): Record<string, string[]> {
    const out: Record<string, string[]> = {};
    for (const [id, spec] of Object.entries(SPECS)) {
      const shown = new Set(OVERLAYS[id] ?? []);
      const gap = [...spec].filter((k) => !shown.has(k));
      if (gap.length) out[id] = gap;
    }
    return out;
  }

  it("has no UNTRACKED API-only knob (a new skill cannot join the backlog quietly)", () => {
    const untracked: string[] = [];
    for (const [id, keys] of Object.entries(uncontrolled())) {
      const waived = new Set(API_ONLY_KNOBS[id] ?? []);
      for (const k of keys) if (!waived.has(k)) untracked.push(`${id}.${k}`);
    }
    expect(
      untracked,
      `knobs with no rendered control and no waiver — add a control in params.ts, or add it to ` +
        `API_ONLY_KNOBS with the rest of the backlog: ${untracked.join(", ")}`,
    ).toEqual([]);
  });

  it("carries no STALE waiver (a knob that got a control must leave the list)", () => {
    const stale: string[] = [];
    for (const [id, keys] of Object.entries(API_ONLY_KNOBS)) {
      const gap = new Set(uncontrolled()[id] ?? []);
      for (const k of keys) if (!gap.has(k)) stale.push(`${id}.${k}`);
    }
    expect(
      stale,
      `waived knobs that now HAVE a control (or no longer exist) — delete them from ` +
        `API_ONLY_KNOBS so the backlog stays honest: ${stale.join(", ")}`,
    ).toEqual([]);
  });
});

/**
 * The other half of reachability: a control that RENDERS but misstates its own value.
 *
 * Coverage above proves a knob has a control. It cannot see whether that control can express the
 * knob. `mergeField` takes `min`/`max` straight from the backend spec and hands them to
 * `<input type="range">`, which silently falls back to **0–100** when either is absent — so a
 * float knob bounded 0–1 would render a slider whose whole meaningful range is the first 1% of the
 * track, and an unbounded int would clamp at 100 with nothing saying so. Same class as the API-only
 * knob (the user cannot reach the value), one layer further in, and invisible to every other gate
 * because the field object is perfectly well-typed either way.
 *
 * The step check is the same failure from the other side: a range input snaps its thumb to
 * `min + k*step`, so a default that is not on that lattice renders a thumb that disagrees with the
 * number printed beside it. It caught `qq.max_points` (min 200, step 500, default 6000 → the thumb
 * sits at 5700 while the readout says 6000) the first time it ran.
 */
describe("rendered controls — a slider must be able to express its own knob", () => {
  /** The merged fields for every overlay skill, keyed by runtime slug. */
  function renderedFields() {
    const out: Record<string, ParamField[]> = {};
    for (const [id, spec] of Object.entries(FULL_SPECS)) {
      if (!OVERLAYS[id]?.length) continue;
      out[id] = paramFieldsFromSpec(id, spec);
    }
    return out;
  }

  it("every slider is bounded by the backend spec (no silent 0–100 fallback)", () => {
    const unbounded: string[] = [];
    for (const [id, fields] of Object.entries(renderedFields())) {
      for (const f of fields) {
        if (f.type !== "range") continue;
        if (f.min == null || f.max == null) unbounded.push(`${id}.${f.key}`);
      }
    }
    expect(
      unbounded,
      `range controls whose skill.json declares no min/max — give the param bounds in the backend ` +
        `spec, or render it as a "number" instead: ${unbounded.join(", ")}`,
    ).toEqual([]);
  });

  /**
   * Scoped to `range` AND `number`, because the lattice is a property of the INPUT, not of the
   * widget: `<input type="number">` validates `min + k*step` exactly as a range snaps to it, so an
   * off-lattice default is a `stepMismatch` the browser marks invalid rather than a thumb that
   * merely disagrees with its readout. Widened 2026-08-05 after two new number fields
   * (`violin.known_min` min 1/step 5/default 5, `cepo.min_cells` min 2/step 5/default 20) shipped
   * off-lattice under a guard that only looked at sliders.
   */
  it("every stepped control's default lands ON a step (the value is one the input accepts)", () => {
    const offStep: string[] = [];
    for (const [id, fields] of Object.entries(renderedFields())) {
      for (const f of fields) {
        if ((f.type !== "range" && f.type !== "number") || f.step == null || f.min == null) continue;
        const steps = (Number(f.default) - f.min) / f.step;
        // Float params carry binary-representation dust (0.55 - 0 over 0.05), so compare against
        // the nearest integer rather than demanding an exact modulo of zero.
        if (Math.abs(steps - Math.round(steps)) > 1e-6) {
          offStep.push(`${id}.${f.key} (default ${f.default}, min ${f.min}, step ${f.step})`);
        }
      }
    }
    expect(
      offStep,
      `defaults the browser will snap away from or reject — change the overlay step so the default ` +
        `is reachable: ${offStep.join(", ")}`,
    ).toEqual([]);
  });

  /**
   * The shared-vocabulary rule, made executable instead of asserted in a comment.
   *
   * `normalize` is declared by fourteen skills under THREE different meanings. Eleven gate the same
   * `sc.pp.normalize_total(1e4)` + `log1p`; the three below do something else entirely, and telling
   * them apart needs the runner's body — the key, the declared `bool` type and the `true` default
   * are identical either way. A previous board asserted all its candidates agreed and was wrong
   * about `pvca` [[share-vocabulary-by-meaning-not-name]].
   *
   * So: a rendered `normalize` control either carries the shared help, or is named here WITH the
   * reason it differs. Exact in both directions, the `API_ONLY_KNOBS` shape — a new skill cannot
   * quietly diverge, and a waiver cannot outlive the divergence that justified it.
   */
  it("every `normalize` control shares the block, or is a named exception with a reason", () => {
    const NORMALIZE_IS_NOT_SCRNA: Record<string, string> = {
      pvca: "divides each feature by its SD (unit variance before PCA) — it is `pca.scale` under another name",
      scorecard: "min–max scales each METRIC COLUMN so radar axes are comparable",
      confusion: "a str enum (none/row/column/all) choosing which matrix reading to show",
    };
    const diverged: string[] = [];
    const stale: string[] = [];
    const seen = new Set<string>();

    for (const [id, fields] of Object.entries(renderedFields())) {
      const f = fields.find((x) => x.key === "normalize");
      if (!f) continue; // no rendered control — tracked by API_ONLY_KNOBS instead
      seen.add(id);
      const shared = (f.help ?? "").startsWith(SCRNA_NORMALIZE_HELP);
      if (shared && id in NORMALIZE_IS_NOT_SCRNA) stale.push(id);
      if (!shared && !(id in NORMALIZE_IS_NOT_SCRNA)) diverged.push(id);
    }

    expect(
      diverged,
      `skills whose "normalize" control neither uses scrnaNormalize() nor is a declared exception — ` +
        `read the RUNNER's body: if it gates normalize_total+log1p, spread the shared block; if not, ` +
        `add it to NORMALIZE_IS_NOT_SCRNA with the reason: ${diverged.join(", ")}`,
    ).toEqual([]);
    expect(
      stale,
      `declared exceptions that now carry the shared help — delete them from NORMALIZE_IS_NOT_SCRNA: ` +
        `${stale.join(", ")}`,
    ).toEqual([]);
    expect(
      Object.keys(NORMALIZE_IS_NOT_SCRNA).filter((id) => !seen.has(id)),
      `declared exceptions with no rendered "normalize" control at all — the waiver describes ` +
        `nothing`,
    ).toEqual([]);
  });
});

/**
 * Seed-drift guard: the generated Selom block must still match the backend's `skill.json` files.
 *
 * The seed was hand-maintained and drifted 19 skills behind the registry. Refilling it by hand would
 * only reset the clock — a hand-maintained mirror of a live registry goes stale again, which is the
 * lesson rather than the incident. So `scripts/gen-catalog-seed.mjs` writes that half, and this
 * re-runs the generator in memory and compares. Adding a skill dir is now: run `npm run gen:seed`,
 * or this fails and tells you to.
 *
 * It compares the ENTRIES, not the rendered file, so a formatting change to the emitter is not a
 * false failure — only a real content difference is.
 */
describe("seed drift — the generated Selom block matches the backend skill.json files", () => {
  it("is up to date (run `npm run gen:seed` if this fails)", async () => {
    const { buildSelomSeed } = await import("../../scripts/gen-catalog-seed.mjs");
    const { SELOM_SEED } = await import("./selom-seed.generated");
    const fresh = buildSelomSeed();

    const ids = (xs: { id: string }[]) => xs.map((x) => x.id).sort();
    const added = ids(fresh).filter((id) => !ids(SELOM_SEED).includes(id));
    const removed = ids(SELOM_SEED).filter((id) => !ids(fresh).includes(id));
    expect({ added, removed }).toEqual({ added: [], removed: [] });
    expect(SELOM_SEED).toEqual(fresh);
  });

  it("names every skill by its `title` — nothing shadows it", async () => {
    // The FE half of `test_registry.py::test_title_is_the_only_display_name`. 21 skills used to
    // carry a `catalog.name` that shadowed the title, so a retitle reached neither Store nor
    // workbench ("Box / strip plot" displayed as "Selom Box Plot").
    const { SELOM_SEED } = await import("./selom-seed.generated");
    const titles: Record<string, string> = {};
    const walk = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(p);
        else if (entry.name === "skill.json") {
          const json = JSON.parse(fs.readFileSync(p, "utf8"));
          if (json?.id) titles[`selom.${json.id}`] = json.title;
        }
      }
    };
    walk(SKILLS_DIR);
    const mismatched = SELOM_SEED.filter((s) => s.name !== titles[s.id]).map((s) => s.id);
    expect(mismatched, `seed name != skill.json title: ${mismatched.join(", ")}`).toEqual([]);
  });
});
