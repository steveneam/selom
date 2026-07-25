/**
 * Single accessor for app-config environment variables (single-env-reader ratchet, M-002).
 *
 * App-config `process.env` reads live ONLY here; every other module imports the typed value from
 * this file. The structure guard (`lib/structure.guard.test.ts`) fails if an app-config var is read
 * anywhere else. Two reads stay outside on purpose and are allowlisted there:
 *   - `NODE_ENV` — framework/environment detection, not app config (read wherever needed).
 *   - `API_PROXY_TARGET` — read by `next.config.ts` at build time to wire the /api dev proxy; that
 *     framework config file is allowlisted (it runs before the app bundle and app aliases exist).
 *
 * `NEXT_PUBLIC_*` vars are inlined by Next at build time, so this must be a direct static property
 * read (`process.env.NEXT_PUBLIC_API_MOCKING`) — a dynamic index would not survive bundling.
 */

/**
 * True when the MSW mock worker should run — the `dev:mock` script sets
 * `NEXT_PUBLIC_API_MOCKING=enabled`. In every other run (`dev`, production) it is a transparent
 * passthrough so the real backend proxy is untouched.
 */
export const apiMockingEnabled = process.env.NEXT_PUBLIC_API_MOCKING === "enabled";

/**
 * True when the hand-annotation layer (the Annotate inspector tab + the rail's draw tools) is
 * exposed. **Off by default**, opt in with `NEXT_PUBLIC_ANNOTATION_LAYER=enabled`.
 *
 * Gated after the 2026-07-25 milestone review (`docs/milestone-review-2026-07-25/findings.md`, §B/§C):
 * the layer's primitives are sound and unit-tested, but 31 of 35 user tasks have no affordance — no
 * canvas selection model, a re-run silently destroys every annotation, repeat adds land
 * pixel-identically, and hand-typed significance stars would export as an unattributed statistical
 * claim. The engine-side computed significance brackets (`sig_brackets`, provenance-recorded) are
 * NOT affected — they arrive in the figure spec and list under Marks either way.
 *
 * Flip this on in the slice that adds the selection model, carry-through-re-run, and the computed-p
 * bracket path; the gate is what keeps a half-built claim surface out of a user's figure meanwhile.
 */
export const annotationLayerEnabled = process.env.NEXT_PUBLIC_ANNOTATION_LAYER === "enabled";
