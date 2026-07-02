"use client";

import { AlertTriangle } from "lucide-react";
import { isStubEngineFigure } from "@/lib/skills/engine-policy";
import type { SkillProvenance } from "@/lib/skills/api";

/**
 * WS1.1 honesty banner (RISKS #11). When a figure was produced by the fabricated STUB engine —
 * the backend ran without the science extras, or `SELOM_SKILLS_ENGINE=stub` — say so loudly right
 * above the artboard: the numbers are example data, NOT an analysis of the user's data.
 *
 * Reads the RESOLVED engine policy the backend stamps into provenance
 * (`environment.engine_policy === "stub"`, see `companions/provenance.py` /
 * `skills/_engine.resolve_engine_policy`). Since `provenance` is persisted on the durable Figure
 * record, the banner survives reload too. Renders nothing for a real run (policy `"real"`) or when
 * provenance is absent. The prod boot guard makes the stub state unreachable off-dev; this banner
 * is the honest label for the dev / canned-demo path where a stub can legitimately render.
 */
export function StubEngineBanner({ provenance }: { provenance?: SkillProvenance }) {
  if (!isStubEngineFigure(provenance)) return null;
  return (
    <div
      role="alert"
      data-testid="stub-engine-banner"
      className="flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-400"
    >
      <AlertTriangle className="size-4 shrink-0" />
      <span>
        <strong className="font-semibold">Example data — not your results.</strong>{" "}
        This figure was produced by the stub engine (the analysis extras aren’t installed), so the
        values are placeholders, not a real analysis of your data.
      </span>
    </div>
  );
}
