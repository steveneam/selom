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
