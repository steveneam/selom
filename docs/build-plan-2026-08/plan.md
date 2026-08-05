# Selom build plan — August 2026

Written 2026-08-02 for a run of autonomous sessions (owner away several days). This is the
**master sequencing doc**; the per-track boards it points at stay the detail.

## 0. Where Selom actually is — measured, not remembered

**Re-measured 2026-08-05.** The 2026-08-02 column is kept because the DELTA is the point: every row
that moved, moved because a phase below closed, and the two that did not move are the two things
still owed (a marketing site, which is not ours, and the FE auth half, which is owner-blocked).

| Thing | 2026-08-02 (as planned against) | **2026-08-05 (now)** |
|---|---|---|
| Shipped skills | 36 registered; 35 real engines | **44 registered; 43 real engines.** Still only `umap_scrna` is stub-only. `skill-smoke` runs **43 pass / 0 fail / 1 skip** on the real corpus (the skip is `facs_gating` — no `.fcs` staged) |
| App routes | 12 | **12** (unchanged) |
| Marketing site | **None** — not Selom's job (Thalon, 2026-08-02) | **Unchanged.** `app/page.tsx` is still the signed-in dashboard; the `/app` route split is still owed to Thalon |
| Auth | Backend ready; frontend none | **Backend hardened** — deny-by-default (`enforce_auth` + a named public allow-list), artifacts namespaced per owner, the cross-tenant artifact leak closed. **Frontend still none — blocked on Clerk keys** |
| Unreachable routes | **~15** waived `R-xx` | **3 waived** — `R-04` (artifact retrieval ×2) + `R-05` (DOI metadata). R-01/02/03/06/07 all CLOSED |
| Cloud export | `E-3` built — real round trip owed | **DONE** — a real figure reached a real Drive and Dropbox, was downloaded back and verified, in `A1` |
| Gate of record | `verify.sh` 7/7, ~78s | **`verify.sh` 9/9**, ~140–250s (adds `be-slow` + `wf-lint`) |

**Reachability backlogs opened since (not in the original plan — see §1a):** `API_ONLY_KNOBS`
**75 across 12 skills** (from 171/36; measured, not derived) · `PROSE_SILENT` **166 untriaged** prose waivers (from 261) ·
the fe-review **JTBD backlog ~23 items**, recorded and unfixed.

### Correcting one assumption

"Not all the skills are working properly" is **half right, and the half that is wrong matters**.
The engines are largely real — **43 of 44** skills have a real `run_real.py` path, and the
golden-test + table-contract guards hold them. What is actually broken is **reach and affordance**:

- ~~~15 routes have no FE call site at all (`R-01`…`R-06`)~~ **→ 3 now** (`R-04` ×2, `R-05`).
  The lit-synthesizer and the Reproducibility Score both have surfaces (the Paper shell's Write-up
  stage).
- The milestone review found **31 of 35 user tasks had no affordance** — the capability existed,
  the user could not get to it.

So the fix is **not** "rewrite the skills". It is: wire them, then audit the workspace they live in.
That is why P-A and P-B are ordered the way they are.

⚑ **This diagnosis was RIGHT and it under-called the depth.** "Reach and affordance" turned out to
have at least **seven layers**, each invisible to all nine gates: unreachable route → unrunnable
skill → untouchable knob → a slider that cannot reach its own value → a control silently OVERRIDDEN
by another → an API-only *contract capability* → **a catalog telling users a capability does not
exist when it ships** (17 skills declared `outputs:["figure"]` while emitting tables). Expect an
eighth. Ask the question of the FEATURE, not the code — a denied capability looks like a product
decision, so nothing looks broken [[selom-shipped-not-reachable]].

### What "complete" still means beyond these phases

Honest remainder, so the plan is not read as the whole product:

- **Persistence** — Supabase is parked pre-launch (`build-now-gate-later`); the app runs on SQLite
  + local object store today.
- **Command-center C/B phases** — Skill Store install backend and real intake; parked until the
  spine is solid (`ROADMAP.md`, [[selom-command-center-architecture]]).
- **Ask-Selom chat** (Pillar 3), **BAM ingest**, **accession auto-fetch** — all parked on product
  decisions, not blocked work (`docs/on-hold/README.md` is the one register).
- **Public deploy on syd2** — founder-gated on spend.

These are deliberately *not* pulled forward. P-A→P-E is what makes the thing users touch actually
work end to end; the list above is what comes after.

---

## 1. The phases

Timeline is in **sessions**, not dates — a session is one working block. At roughly one a day the
calendar reads as shown, but the ordering is the commitment, not the dates.

| Phase | What | Sessions | Needs owner? | **Status (2026-08-05)** |
|---|---|---|---|---|
| **P-A** | Finish cloud export + close the reachability backlog | 2–3 | no | ✅ **DONE** — `A1` round trip verified against real accounts; `R-01/02/03/06/07` closed, 3 waivers left |
| **P-B** | Workspace UX audit (Mobbin-driven) → fix pass | 2–3 | decisions batched at the end | ◐ **Audit done, fix pass partial** — gauntlet + fe-review ran at each milestone and their confirmed defects were fixed; the **~23 JTBD feature gaps are recorded and open** |
| **P-C** | Skill quality + coverage pass | 2 | no | ✅ **DONE and overshot** — Phase F1+F2 (cnsplots parity), 8 new plot types, the 43-skill smoke matrix. F3/F4 styling rows remain |
| **P-D** | Platform: job store, style packs | 2 | no | ◐ **Job store DONE** (`R-02`, run-activity dock). **Style packs: the registry exists** (`skills/styles.py`) — the per-journal packs need each journal's own guidelines |
| **P-E** | Auth + real multi-tenancy (FE half) | 2 | keys only | ⛔ **BLOCKED ON OWNER** — backend hardened (deny-by-default, tenant-scoped artifacts, leak closed). FE half needs **Clerk keys** + the `/app` route-split call |

Total ≈ **10–12 sessions**, all runnable without the owner.

> ### ⚑ Where the sessions actually went (2026-08-05)
> P-A and P-C closed early, and the reachability sweep in P-A **kept finding deeper layers of the
> same class** — routes → unrunnable skills → 171 untouchable knobs → a slider that cannot reach its
> value → an overridden control → an API-only contract capability → **a catalog denying a capability
> that ships**. That opened three backlogs no phase here anticipated (§0), and roughly ten sessions
> since have been spent on them rather than on P-B/P-D/P-E.
>
> **That work is real and keeps finding real defects** — but it is open-ended, and none of it moves
> Selom toward being usable by anyone but the owner. **P-E is the only phase that does, and it is the
> one blocked on the owner.** Treat "keep burning down the honesty backlogs vs. unblock P-E" as a
> live founder call, not a default.

> ### The landing page is NOT on this plan — owner-directed 2026-08-02
> Building the public marketing site is **delegated to Thalon**. Selom's job is to be a complete
> product; the page that sells it is a separate build. Nothing in this plan touches marketing copy,
> positioning, or pricing, and `app/page.tsx` stays the signed-in dashboard.
>
> Two things Selom still owes Thalon when that build starts, and should not duplicate: the
> **public/private route split** (today `/` is the dashboard, so a marketing route needs a decision
> about where the app moves to) and the **parked hero animation** (`cb813cf`,
> [[selom-pipeline-flow-animation]]) — already built, currently unused.

---

## P-A — finish what is half-built (2–3 sessions)

**Goal:** nothing is left "built but not done", and the reachability list shrinks.

### A1 · the cloud-export round trip — FIRST, before any new code

`E-1`/`E-2`/`E-3` are coded and green, but **every test is a mock, and a mock proves the wire, not
the product** ([[selom-mock-is-wire-only-verify-real]]). No byte has reached a real Drive.

1. Turn on `SELOM_CLOUD_GOOGLE` / `SELOM_CLOUD_DROPBOX`; confirm `bash deploy/nango/preflight.sh`
   passes against the live broker (syd2, `nango.swordfish.cfd`).
2. Editor → export menu → **Save to Google Drive** in a real browser. The file must land **and
   open** — a 200 is not proof the bytes are a valid PNG.
3. Repeat for Dropbox. **Delete both test files** afterwards, as `V-2` did.
4. Add the `browser-verify` spec that locks it in.

**Two failure modes a mock cannot catch, both likely:**
- Drive returns the resumable **session URI** in a `Location` header that a real client may see on a
  200 *or* a 308.
- Dropbox's `Dropbox-API-Arg` header **rejects non-ASCII**. A figure named with "µV" or an en-dash —
  very likely in this repo — fails on a real call while every mock passes. Fix: ASCII-escape the
  header value.

**Acceptance:** a real file in a real account, opened, then deleted. Spec: `docs/cloud-export/spec.md`.

### A2 · `R-02` — the async job pipeline has no FE consumer

**Do this before `OH-01`**, not after. `OH-01` (arq + Redis job-status store) is unparked and
queued; if it ships first, the store ships **with no reader**. Nothing in the FE polls a job today.

Wiring: `jobs/` router → a job-status hook in `lib/jobs/` → progress surfaced wherever a long run is
launched (skill run, reproduction). Deletes the `R-02` waiver.

### A3 · `R-01` + `R-03` — lit-synthesizer and paper-level outputs

The largest user-visible loss on the board, and they overlap on methods, so do them together:
`/methods/compose`, citations, legends, and the **Reproducibility Score**.

**Check first** whether the Workspace Library's Methods/legend slot was the intended home
([[selom-workspace-library]]) — do not invent a second one.

**Spec owed** (small): where paper-level outputs live in the IA. Write it before building; this is a
placement decision that will be expensive to move later.

### A4 · `R-04` → unblocks `F1`; then `R-06`; then the `R-05` decision

`R-04` (artifacts fetchable by id) also lets `E-2` switch from an inline figure to an artifact id —
**check `docs/cloud-export/spec.md` D2 before building so the two do not duplicate**. `R-05` is a
decision, not a build: surface DOI enrichment or waive it permanently.

---

## P-B — workspace UX audit + fix (2–3 sessions)

**Goal:** the workspace stops being "rough around the edges" in a way that is *documented and
measured*, not vibes.

### B1 · the audit

Run **`fe-review`** (V·R·D·A·R·N + G1 user-task walkthrough + G2 rendered-in-context) across the
whole workspace, **not** a diff — this is the milestone-scale use it was built for. Pair it with
**Mobbin** per surface, which is the part that is new:

| Surface | Mobbin query |
|---|---|
| First run / empty project | onboarding with a first-project setup step |
| Data intake | file upload with validation and progress |
| Skill picking | browsing a catalog and configuring an item before running |
| The editor | canvas editor with a properties inspector panel |
| Library | a grid of saved documents with filters |

Mobbin is a **comparison instrument, not a template**. Last session it earned its place by ruling a
pattern *out*: Drive's folder-picker modal is impossible for Selom under `drive.file`. Expect the
same — record what does **not** apply and why.

**Deliverable:** `docs/workspace-audit-2026-08/findings.md` — one row per finding with surface,
severity, the user task it blocks, and a fix verdict. Founder-decision rows batched into a single
list at the end for the owner's return.

### B2 · the fix pass

Work the audit's confirmed rows, highest-severity first. Re-run `browser-verify` after each.
**Do not** open new feature work here — the point is finishing edges.

---

## P-C — skill quality + coverage (2 sessions)

Not a rewrite. Three concrete things:

1. **`umap_scrna` is the last stub-only skill** — give it a real engine path or record why not.
2. **A skill-level smoke matrix**: run every one of the 36 against a real dataset from
   `SELOM_DATASETS_DIR` and record pass/fail + runtime. There is no such sweep today, which is
   exactly why "are all the skills working?" cannot currently be answered with evidence. This
   becomes a ratchet.
3. **Close the OSCA reference-annotation gap** (the last one) or formally park it.

**Acceptance:** a committed matrix showing every skill's real-data status, and a guard that fails
when a skill regresses.

---

## P-D — platform (2 sessions)

1. **`OH-01` arq + Redis job-status store** — unparked and owner-decided. **Strictly after `A2`**,
   or it ships with no reader. Redis is already on `:6380`.
2. **Journal style packs** — the cheapest item on the whole board: `docs/journal-styles/spec.md` is
   **already written**; refactor `skills/theme.py` into a named style registry.

---

## P-E — auth + real multi-tenancy (2 sessions)

**The largest remaining "not actually a product" gap, and it is one-sided.**

Measured 2026-08-02: the **backend is ready** — `auth/clerk.py` verifies the Clerk JWT,
`auth/context.py` derives the tenant from the verified `sub`, and every handler already takes
`ctx.user_id` and resolves keys from the tenant's own row (the T1 rule). The **frontend has
nothing**: no `@clerk/nextjs` dependency, no provider, no middleware, no sign-in surface. `auth_mode`
defaults to `dev`, so *every request runs as the same dev tenant*.

So Selom today cannot have two users. Everything downstream of that — quotas, the library, project
ownership, sharing — is single-tenant by default rather than by design.

1. Add the Clerk provider + middleware + sign-in/sign-up surface, behind the **existing `auth_mode`
   flag** so `dev` stays the local default and nothing breaks offline.
2. Wire the bearer at `lib/api/client.ts` — it is deliberately a one-liner there ("step 8"), not a
   sweep across call sites.
3. **Then prove the isolation**: two tenants, and tenant A cannot read, list, or export tenant B's
   datasets, figures, or library rows. A test per boundary, not a claim.

**Owner needs to supply Clerk keys** (free tier is enough to build against). That is the only
dependency, and step 1–2 can be built and tested against a dev issuer before the keys land.

**Not in scope:** Supabase persistence stays parked (pre-launch infra, `build-now-gate-later`), and
Clerk owns auth email — Resend is product/lifecycle only ([[selom-resend-email-decision]]).

---

## 2. Founder gates — batched for the owner's return

Nothing below gets decided autonomously.

| # | Decision | Blocks | Recommendation |
|---|---|---|---|
| 1 | **Cloud §Scope** — Selom can only read files it created, so import is nearly useless | cloud import | Google Picker, not a broader scope (`drive.readonly` is *restricted* → annual CASA assessment) |
| 2 | **Clerk keys** (free tier) | P-E finishes | Build proceeds against a dev issuer until they land |
| 3 | **`R-05`** — surface DOI enrichment or waive permanently | one waiver | Waive; it is internal plumbing |
| 4 | **syd2 public backend** (spend + 5 data-plane answers) | public deploy | Deferred; not on this plan's path |
| 6 | **Where the app lives once a marketing site exists** (`/` vs `/app`) | Thalon's landing build | Decide before Thalon starts, not after |
| 5 | Anything P-B's audit surfaces as a product call | its own rows | Batched list at the end of the audit |

---

## 3. Standing rules for these sessions

- **Gate of record** is `scripts/verify.sh`, read raw, never piped ([[read-gate-output-raw-not-piped]]).
- **Verify on real data, not mock** — `dev:mock` skips the paths that break
  ([[verify-on-real-data-not-mock]]).
- **Review cadence**: `review-gauntlet` + `fe-review` at a **phase boundary**, not per task.
- **A change that wires a surface deletes its own waiver** — never banked ahead.
- Commit per slice with the real reasoning; owner pushes are no longer required (owner authorised
  push 2026-08-02).
- **Nothing outward-facing ships** without the owner: no publishing, no public deploy, no pricing.
