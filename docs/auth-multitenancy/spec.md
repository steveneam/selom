# P-E — auth and real multi-tenancy

Spec, written 2026-08-02. Implementation is **sequential, after the Sprint 3 merge train**: it lands
in `app/frontend/lib/api/client.ts`, the sprint's frozen contract, so it cannot share the road with
an FE lane.

Status: **written, not built.** The founder gate is keys only (§7).

---

## 1. The problem, stated honestly

Selom cannot have two users. Not "auth is unpolished" — **two people cannot use this product at the
same time without seeing each other's data.**

`docs/build-plan-2026-08/plan.md` records this as one-sided: *"The backend is ready … the frontend
has nothing."* The frontend half of that is exactly right. **The backend half is not**, and the
difference is the whole reason this needs a spec rather than a ticket.

### What is genuinely ready

- `auth/context.py` is a clean seam: `DevVerifier` (every request is one fixed dev tenant) and
  `ClerkVerifier` (verifies the bearer JWT, or honours an API-Gateway authorizer's pre-verified
  context in prod). `make_auth_verifier` picks by `SELOM_AUTH_MODE`.
- **The tenant is always a verified claim, never a request param** — a handler cannot source a
  `user_id` from user input.
- Config refuses to start in `clerk` mode without an issuer.
- `test_auth.py`, `test_tenant_isolation.py`, `test_tenant_query.py`, `test_tenant_schema.py` exist.

### What is not (measured 2026-08-02, by AST over `routers/*.py`)

**39 of 78 routes take no `AuthContext` at all.** Flipping `SELOM_AUTH_MODE=clerk` today
authenticates half the API and leaves the other half open — and *open* here does not only mean
unauthenticated, it means **unscoped**: those handlers have no tenant to scope by, so they answer
for whoever asks.

Most of the 39 are legitimately public and must stay that way (§3). But these are not:

| Route | What it leaks | Severity |
|---|---|---|
| `GET /artifacts/{artifact_id}` | The lineage record for any materialized intermediate table, by id | **cross-tenant read** |
| `GET /artifacts/{artifact_id}/table` | **The table bytes themselves** — the exact matrix a skill consumed | **cross-tenant read** |
| `GET /reproduction-runs/{run_id}` · `…/events` | Another tenant's run state and event stream, by id | cross-tenant read |
| `POST /papers/{paper_id}/reproduce` · `…/assess-data` | Starts work against another tenant's paper id | cross-tenant write/compute |
| `PUT /uploads/local/{key:path}` | Accepts any key under `uploads/` — including another tenant's prefix | cross-tenant **write** |
| `POST /data/inspect` · `/data/combine` · `/data/assemble-scrna` · `POST /extract/chart` · `POST /skills/{id}/run` | No tenant leak (they act on uploaded bytes, not stored ids), but unauthenticated **compute** | abuse surface |

`GET /artifacts/{id}/table` is the sharpest of these: an opaque id is not an authorization check, and
"you would have to guess the id" is not a control. `PUT /uploads/local/{key:path}` is dev-only (the
`LocalObjectStore` stand-in for an S3 presigned PUT, where the URL *is* the credential), so it is a
deployment-shape problem rather than a prod hole — but it must be **refused** when the object store
is S3, not merely unused.

**So P-E is two halves, not one:** build the frontend, *and* close the backend authorization gap.
Shipping only the frontend half would produce a product that authenticates its users and still
serves their data to each other.

---

## 2. Goal

A second person can sign up, use Selom, and be unable to observe anything of the first person's —
**proved by a test that tries and fails**, not by inspection.

Non-goals: orgs/teams, roles, sharing, invitations, billing. One user = one tenant.

---

## 3. Decisions

**D1 — Clerk, as already chosen.** The backend verifier, the config seam and the prod authorizer path
are written against it. Nothing here revisits that.

**D2 — Deny by default, with an explicit public allow-list.** The audit found the gap by *searching
for what was missing*, which is exactly the method that will miss the next one. Invert it: attach the
verifier as a **router-level dependency**, and make `public` an explicit, named decision per route.
A new route is then private unless someone writes down that it is not — the ratchet strength ladder's
structural rung, instead of a documentary "remember to add `require_user`".

The public set, stated once and guarded:

- `GET /health`, `GET /ready` — liveness, must not require a token.
- `GET /skills`, `GET /skills/{id}` — the skill catalog is product surface, identical for everyone.
- `GET /cloud/providers` — the frozen provider contract; server-owned, no tenant data.
- `GET /figures/export/presets`, `GET /figures/styles` — static reference data.
- `GET /citations/search`, `GET /citations/by-doi`, `GET /papers/metadata/by-doi` — external
  bibliographic lookups, no tenant data.
- `GET /papers`, `GET /papers/{slug}` and its `scorecard` / `methods` / `legends` — the **curated
  reproduction catalog** shipped with the product, not user papers. (User papers live under
  `/workspace/papers`, which is already authenticated. If that ever stops being true, these move.)

Everything else is private. Where a private route currently has no tenant to scope by, scoping is
part of this change, not a follow-up: `/artifacts/*` and `/reproduction-runs/*` must resolve through
the tenant's own row exactly as `library.py` already does.

**D3 — `dev` mode stays the default and stays exactly as it is.** The inner loop, `verify.sh`,
`browser-verify.sh` and every existing test run unauthenticated against one fixed dev tenant. Auth
being real must not make local development need a network round trip to Clerk. The guard is that
`SELOM_AUTH_MODE=clerk` is what the deployed app sets, and the isolation test (§5) runs in `clerk`
mode with a fake issuer so CI proves the real path.

**D4 — The token is attached in one place.** `lib/api/client.ts` already has `_authHeader()` and its
own comment says Clerk is "a one-liner here, not a sweep across call sites". Honour that: the client
asks Clerk for a token; **no feature module learns about auth.** This is the single reason P-E cannot
run inside a lane.

**D5 — The route split is a real product decision, and it is owed to Thalon.** Today `/` **is** the
signed-in dashboard, so there is nowhere for a signed-out visitor to land. Thalon is building the
marketing site (owner-directed 2026-08-02) and needs to know where the app lives.

Decide it here: **the app moves under `/app`**, `/` becomes public and unowned by Selom, and
`middleware.ts` protects `/app/**` only. This is a redirect-level change for existing users and it
un-blocks Thalon without either build guessing. Deep links (`/p/[id]`, `/library`, `/paper/[id]`, …)
move with it and get permanent redirects from their old paths.

> **This is the one decision in P-E that deserves a founder beat.** It is cheap now and expensive
> after the marketing site ships against an assumption. Recommended, not assumed — flagged in §7.

**D6 — Sign-in is Clerk's hosted component, not a bespoke form.** Selom's differentiation is
nowhere near its login screen.

---

## 4. Build order

1. **Backend: deny-by-default.** Router-level dependency + the §3 public allow-list. No FE change
   yet; `dev` mode keeps everything green.
2. **Backend: scope the unscoped.** `/artifacts/*` and `/reproduction-runs/*` resolve through the
   tenant's row; `PUT /uploads/local/{key:path}` refuses to exist unless the store is local.
3. **The isolation test (§5).** Written before the frontend, so the frontend is built against a
   backend already proved to keep tenants apart.
4. **Frontend:** `@clerk/nextjs`, `ClerkProvider` in `app/layout.tsx`, `middleware.ts` protecting
   `/app/**`, sign-in/sign-up routes, and a user button in the shell.
5. **Frontend: the token,** in `_authHeader()` in `lib/api/client.ts`, and nowhere else.
6. **The route split (D5)** — after the founder beat.
7. **Browser-verify spec:** sign in as A, create a project, sign out, sign in as B, and confirm B
   sees an empty workspace and cannot open A's project by direct URL.

---

## 5. The isolation test — the acceptance criterion

`app/backend/tests/test_tenant_isolation.py` exists; this **extends** it rather than adding a second
home (ratchet doctrine: one invariant, one guard, extended in the same change).

Runs in `clerk` mode against a fake issuer. Two tenants, A and B. For **every private route** — not a
sample — B must be unable to:

- **read** A's row by id (404, never 403 — a 403 confirms the id exists),
- **list** anything of A's (empty, not filtered-but-present),
- **mutate or delete** A's row by id,
- **export** A's data to B's cloud account (the `A1` path: `dataset_id` resolves from the tenant's
  own row, so this must 404),
- **fetch A's artifact table bytes** (`/artifacts/{id}/table`) — the sharpest hole found in §1.

"For every private route" is enforced, not aspirational: the test **enumerates the routes by AST**
the same way §1 did, subtracts the public allow-list, and **fails on any private route it has no
case for**. A new private route with no isolation case is then a failing test, not an oversight —
this is the same shape as `test_reachability_guard.py`, which found 17 unreachable routes where a
full human review found 2.

---

## 6. What could go wrong

- **Every existing test breaks.** Mitigated by D3: `dev` stays the default, so the suite is unaffected
  until a test opts into `clerk` mode.
- **`browser-verify.sh` breaks**, because it drives a real browser with no session. It runs in `dev`
  mode; only the new sign-in spec (§4.7) runs authenticated. Its `webServer` env must pin
  `SELOM_AUTH_MODE=dev` explicitly rather than relying on the default.
- **The route split breaks bookmarks and the deployed Vercel URL.** Permanent redirects from every
  old path, and the redirect list is a test.
- **Clerk keys reach git.** They go in the repo-root `.env` (gitignored, the one home the backend
  loads) and Vercel's env; the hygiene scan already refuses secrets in tracked files.
- **A public route later starts returning tenant data.** The allow-list is a small named set in one
  file, and D2 makes adding to it a deliberate act.

---

## 7. Founder gates

1. **Clerk keys** — publishable + secret, plus the issuer URL. Nothing in P-E can be verified end to
   end without them; steps 1–3 (the backend half) can be built and proved without.
2. **D5, the route split** — app moves to `/app` and `/` becomes public. Recommended above; it is a
   product-shape decision, it affects Thalon's build, and it is much cheaper before that ships.

Everything else in this spec is pre-authorised autonomous work.
