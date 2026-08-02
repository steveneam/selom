# Selom build plan — August 2026

Written 2026-08-02 for a run of autonomous sessions (owner away several days). This is the
**master sequencing doc**; the per-track boards it points at stay the detail.

## 0. Where Selom actually is — measured, not remembered

| Thing | State (verified 2026-08-02) |
|---|---|
| Shipped skills | **36** in `skills/registry.py`; **35 have a real engine** (`run_real.py`). Only `umap_scrna` is stub-only. |
| App routes | 12 (`/`, `/p/[id]`, `/library`, `/extract`, `/gene-sets`, `/skill-match`, `/reproduction`, `/store`, `/paper/[id]`, …) |
| Marketing site | **None.** `app/page.tsx` is the signed-in dashboard (projects/datasets/figures), not a public landing page. No pricing, no signup, no product story. |
| Unreachable routes | **~15**, waived with `R-xx` ids, enforced by `test_reachability_guard.py` (stale waivers fail). |
| Cloud export | `E-1`/`E-2` done, `E-3` built — **real round trip owed**. |
| Gate of record | `scripts/verify.sh` 7/7, ~78s. |

### Correcting one assumption

"Not all the skills are working properly" is **half right, and the half that is wrong matters**.
The engines are largely real — 35 of 36 skills have a real `run_real.py` path, and the golden-test
+ table-contract guards hold them. What is actually broken is **reach and affordance**:

- ~15 routes have no FE call site at all (`R-01`…`R-06`) — including the **entire lit-synthesizer**
  and the **Reproducibility Score**, which is a named part of the product thesis and currently
  cannot be shown for a paper.
- The milestone review found **31 of 35 user tasks had no affordance** — the capability existed,
  the user could not get to it.

So the fix is **not** "rewrite the skills". It is: wire them, then audit the workspace they live in.
That is why Phase 1 and Phase 2 below are ordered the way they are.

---

## 1. The phases

Timeline is in **sessions**, not dates — a session is one working block. At roughly one a day the
calendar reads as shown, but the ordering is the commitment, not the dates.

| Phase | What | Sessions | Needs owner? |
|---|---|---|---|
| **P-A** | Finish cloud export + close the reachability backlog | 2–3 | no |
| **P-B** | Workspace UX audit (Mobbin-driven) → fix pass | 2–3 | decisions batched at the end |
| **P-C** | Public landing page + onboarding | 2 | **yes — positioning/pricing copy** |
| **P-D** | Skill quality + coverage pass | 2 | no |
| **P-E** | Platform: job store, style packs | 2 | no |

Total ≈ **10–13 sessions**. P-A → P-B → P-D can run without the owner. P-C is drafted
autonomously but **cannot ship** without founder input.

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

## P-C — landing page + onboarding (2 sessions) · **NEEDS THE OWNER**

There is no public face. `app/page.tsx` is the signed-in dashboard; a visitor who is not logged in
has nothing to read.

### What I can do without the owner

- **Structure and build** the marketing route (`/` public vs `/app` signed-in split, or a
  marketing route group), responsive, themed, accessible.
- **Mobbin-source the section inventory** (hero, proof, feature walk, pricing, FAQ, footer) —
  `search_sections` is exactly this.
- Draft copy from `PRODUCT.md` + `docs/records/pricing-demo-strategy` as a **strawman**.
- Wire the pipeline-flow hero animation already built and parked (`cb813cf`,
  [[selom-pipeline-flow-animation]]).

### What I will not decide

**Positioning, pricing, and claims are founder calls**, and a landing page is an outward-facing
artifact. So:

- I will build it behind a route that is **not linked** and not indexed (`noindex`), with copy
  clearly marked `DRAFT`.
- **No pricing numbers, no customer claims, no testimonials, no logos** get written by me.
- Publishing is the owner's call on return.

Memory says pricing is decided in principle (**no free tier; promo-code beta**,
[[selom-pricing-demo-strategy]]) — that is enough to structure a pricing section, not to fill in
numbers.

**Spec owed:** `docs/landing/spec.md` — IA, section inventory, the public/private route split, and
the auth boundary (Clerk owns auth; see [[selom-resend-email-decision]]).

---

## P-D — skill quality + coverage (2 sessions)

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

## P-E — platform (2 sessions)

1. **`OH-01` arq + Redis job-status store** — unparked and owner-decided. **Strictly after `A2`**,
   or it ships with no reader. Redis is already on `:6380`.
2. **Journal style packs** — the cheapest item on the whole board: `docs/journal-styles/spec.md` is
   **already written**; refactor `skills/theme.py` into a named style registry.

---

## 2. Founder gates — batched for the owner's return

Nothing below gets decided autonomously.

| # | Decision | Blocks | Recommendation |
|---|---|---|---|
| 1 | **Cloud §Scope** — Selom can only read files it created, so import is nearly useless | cloud import | Google Picker, not a broader scope (`drive.readonly` is *restricted* → annual CASA assessment) |
| 2 | **Landing positioning + pricing copy** | P-C ships | Draft ready for edit; no numbers written by me |
| 3 | **`R-05`** — surface DOI enrichment or waive permanently | one waiver | Waive; it is internal plumbing |
| 4 | **syd2 public backend** (spend + 5 data-plane answers) | public deploy | Deferred; not on this plan's path |
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
