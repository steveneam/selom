/**
 * WS1.1 honesty predicate (RISKS #11).
 *
 * The backend stamps the RESOLVED engine posture into `provenance.environment.engine_policy`:
 * `"stub"` when a figure was fabricated by the dependency-free stub engine (the backend ran without
 * the science extras, or `SELOM_SKILLS_ENGINE=stub`), `"real"` for a genuine analysis. Only `"stub"`
 * warrants the "example data — not your results" banner.
 *
 * A real run, an older/mocked run without the field, or an absent bundle must NOT warn — over-warning
 * ("crying wolf" on real results) erodes trust as much as under-warning hides fake ones. Kept pure and
 * lib-side so this contract is unit-pinned without a DOM render harness.
 */
export function isStubEngineFigure(
  provenance?: { environment?: { engine_policy?: string } } | null,
): boolean {
  return provenance?.environment?.engine_policy === "stub";
}
