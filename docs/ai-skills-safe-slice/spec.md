# Selom — AI Skills Safe Slice (M-003)

Status: **DRAFT — not yet built (spec only).** Created
2026-06-28. Workstream **M-003** of the AWS materialization plan.

> Primary source of truth: [`docs/aws-materialization/plan.md`](../aws-materialization/plan.md)
> — §3 M-003 and **locked decision D7** ("AI-skills = safe slice; reuse-via-fingerprint +
> capture-to-admin queue; defer sandboxed codegen for security"). This doc expands that one
> line into an implementable shape and folds in the QR-hardened must-cover **S1**.

---

## 1. Goal

Give Selom an "AI writes/reuses skills" capability **without** ever executing AI-generated
code. Two halves are built now; one is fenced off.

1. **REUSE** — the AI chat fingerprints *(task intent + data shape)* and matches it to a skill
   the account **already has** (the deterministic keyword router + the Workspace Library). This
   is the owner's "barcode/tag to identify which skills they already have." It is a **thin
   layer over Selom's existing content-addressing** (`_result_cache.canonical_params` +
   `input_sha256`, `lineage.artifact_id`) — not new infra.
2. **CAPTURE** — when the user hits an edge case no installed skill covers, the chat captures a
   **structured request** into an admin queue (the ratchet / feedback loop). It reaches us
   (admin); we build the skill properly; the next user with that fingerprint reuses it.
3. **DEFER (fenced)** — on-the-fly AI codegen/execution is **NOT built**. §7 states the security
   boundary and the explicit gate that must be crossed before it is ever built. *Capture now,
   execute later.*

The pattern is the owner's n8n/Forj orchestrator/worker reference: an LLM either **reuses** an
existing deterministic skill matched by a *schema-hash cache*, or (deferred) writes a new
sandboxed script. Selom's "schema-hash cache" already exists — it is the content-addressing
below — so the REUSE half is a small adapter, and the CAPTURE half is the durable artifact that
turns each miss into a built skill (the Ratchet).

### Non-goals (this slice)
- No AI code generation, no code execution, no sandbox, no SELECT-runner. (§7.)
- No new skills authored by this feature — it **routes to** existing skills and **queues**
  requests for new ones.
- No change to the skill **runner**, the catalog schema, or the router's scoring math — M-003
  consumes them read-only and adds a fingerprint adapter + a request queue + an admin surface.

---

## 2. Decision log

| # | Decision | Why | Rejected |
|---|---|---|---|
| L1 | The reuse **fingerprint reuses existing content-addressing**, it does not invent a hash. Task side = the router's keyword/canonical terms; data side = a coarse **schema signature** (column-group + modality), NOT the row-level `input_sha256`. | `input_sha256` (`_result_cache.cache_key`) is *exact-bytes* — perfect for the result cache, useless for "which skill fits this kind of data." Reuse needs a **shape** key, not a bytes key. Two layers, same discipline. | A brand-new ML embedding index (over-engineering; the deterministic router already ranks skills by evidence). |
| L2 | **Match = the existing router** (`route.py:route_text` → `FeasibilityMap`) restricted to **installed** skills (Workspace Library), re-scored only by intersecting with `WorkspaceState.skills`. | The 4-layer L1–L4 router is the production paper→skill matcher already; reuse is "route, then filter to what you own." No second matcher to keep in sync. | A separate reuse-only matcher (would drift from the router's curated synonym moat). |
| L3 | **Confidence threshold gates the three outcomes**: `reuse` (high) · `suggest-install` (mid, skill exists in catalog but not installed) · `capture` (low / no in-scope skill). | Mirrors the router's own `FigureRoute.confidence` semantics (`models.py:132`) so there is one confidence vocabulary across the app. | A binary match/no-match (loses the "you could install this" middle path, which is a conversion surface). |
| L4 | **Capture writes to Postgres** (`skill_requests`, a net-new tenant table peer to `skill_installs` from M-001 §4), **not** localStorage. | The queue must reach *admin* across tenants; localStorage is per-browser. This is the one M-003 table that is **cross-tenant by design** (admin reads all) — hence the S1 controls. | A file drop / email (no structure, no dedup, no retention control, no access control → fails S1). |
| L5 | **Redaction at capture time, before the row is written** (S1). The request stores a **fingerprint + structured descriptors**, never raw query text or data bytes by default. | A miss is described by its *shape* (terms, column-groups, modality), which is exactly the non-PII fingerprint. Storing the shape, not the payload, makes redaction the natural state, not a scrub afterward. | Store raw, redact on read (PII already at rest; one missed reader leaks it). |
| L6 | **Loop closure is automatic**: a request is `resolved` when a skill whose fingerprint covers it lands in the catalog; the next matching chat turn reuses it and the request's `resolved_by_skill_id` is stamped. | Closes the ratchet without manual bookkeeping; the request's own fingerprint is the join key back to the new skill. | Manual "mark done" only (requests rot; no proof the gap actually closed). |

---

## 3. REUSE half — fingerprint → match an installed skill

### 3.1 The fingerprint (what goes in)

A reuse fingerprint is the **task side** + the **data side**, both derived from infra that
already exists. It is deliberately *coarse* (a shape, not bytes) so that two structurally-similar
asks collide on the same skill.

```
ReuseFingerprint = {
  task:  { terms: [canonical method-nouns], oos: [out-of-scope reasons] },   # from the router
  data:  { modality: str, column_groups: [str], n_numeric_cols_bucket: str }, # from compat/cleaning
  fp_hash: sha256(canonical-json(task ⊕ data))                                # the "barcode/tag"
}
```

| Component | Source (existing, file:line) | Note |
|---|---|---|
| `task.terms` | `extract/routing/route.py:159` `route_text(text)` → `FeasibilityMap`; canonicalized by `extract/routing/index.py:54` `canon()` | The chat turn's intent text is run through the **same** router that routes a paper. Exact (L1) `index.py:93 find_in` + relaxed (L3) `index.py:105 find_relaxed`. |
| `task.oos` | `FeasibilityMap.out_of_scope` (`extract/routing/models.py:150`) | If the ask is an out-of-scope modality (atac/spatial/grn/wet_lab) we never pretend a skill fits — straight to suggest/capture. |
| `data.modality` | `engine/cleaning.py` `profile_data` → `DataProfile.code` (`cleaning.py:123`) | The friendly modality label + confidence already computed on ingest/inspect. |
| `data.column_groups` | `engine/compat.py:212` `_check_schema` against `engine/compat.py:205 _SCHEMA`; `engine/compat.py:174 _frame_signature` | The named column-group contract per skill (e.g. volcano needs a log2FC + p-value group). The signature is "which declared groups are present," not the column values. |
| `data.n_numeric_cols_bucket` | `engine/compat.py:88` `FileAssessment.n_numeric_cols` (bucketed: 0 / 1 / 2-3 / many) | Coarse shape so near-identical tables collide. |
| `fp_hash` | **new, thin** — `sha256` of canonical-json, mirroring `_result_cache.py:96 canonical_params` + `:129 cache_key` discipline (sort_keys, stable float rounding, drop-defaults) | The "barcode" the owner described. Reuses the **canonicalization recipe**, not the bytes. |

> **Explicit mapping to existing content-addressing.** Selom already content-addresses two
> things: the *exact run* (`_result_cache.cache_key(skill_id, version, param_spec, data_path,
> params)`, `_result_cache.py:129`, whose data side is `input_sha256` of the bytes,
> `_result_cache.py:68`) and the *exact table* (`lineage.materialize` → `artifact_id =
> sha256(csv_bytes)`, `engine/lineage.py:104,248`). M-003 adds **one coarser tier above them**:
> where `input_sha256` answers "have I run *this exact file* through *this exact skill*?", the
> reuse `fp_hash` answers "do I already own *a* skill for *this kind of* task+data?". Same
> hashing discipline, one rung up the abstraction ladder. The reuse layer is therefore an
> adapter (~one module), not new infrastructure.

### 3.2 The match path

```
chat turn (intent text) + active dataset (DataFit / FileAssessment already on the project)
   │
   ├─ task side:  route_text(intent) → FeasibilityMap.paper_targets        (route.py:159)
   ├─ data side:  profile_data + _frame_signature → modality + column_groups (cleaning.py / compat.py:174)
   │
   ├─ candidate skills = FeasibilityMap.skills  (in-scope skill ids; models.py:149)
   ├─ FILTER to owned:  candidates ∩ WorkspaceState.skills[].skillId        (workspace/types.ts:88,96)
   ├─ DATA-FIT re-rank:  engine/compat.py:323 fit(skill_id, fa) → DataFit.score per surviving candidate
   │
   └─ outcome by confidence (L3):
        high  → REUSE      : open the skill pre-filled for this dataset (no install step)
        mid   → SUGGEST    : skill is in list_catalog() (registry.py:82) but NOT in WorkspaceState
                             → one-click installSkill() (workspace/store.ts:237) then reuse
        low   → CAPTURE    : §4 (no in-scope or no compatible skill)
```

The match is the router's own ranking (`RoutingCandidate.score`, `models.py:84`) **intersected**
with the data-fit score (`DataFit.score`, `compat.py:271`) — task-fit AND data-fit must both
clear. A high task score on data the skill can't read (column groups absent) is a **suggest at
best**, never a silent reuse.

### 3.3 Confidence threshold

One confidence axis, reusing the router's vocabulary (`FigureRoute.confidence`,
`models.py:132`). Concrete cut-points are **for owner review** (Open Question Q1):

| Band | Condition (draft) | Outcome |
|---|---|---|
| **High** | top task candidate `in_scope` **and** owned **and** `DataFit.compatible` is true **and** confidence margin ≥ θ_high | `reuse` |
| **Mid** | in-scope candidate exists in `list_catalog()` but not owned, **or** owned-but-`DataFit` partial | `suggest-install` |
| **Low** | no in-scope candidate, **or** `out_of_scope` reason present, **or** all candidates fail data-fit | `capture` |

Honest framing (consistent with M-002 A1 and the router's "never falsely certain"): a `mid`/`low`
outcome is shown as "I don't have a skill for this yet" + the capture affordance, never a
fabricated answer.

---

## 4. CAPTURE half — the ratchet / admin queue

When the outcome is `capture` (or the user rejects a `suggest`/`reuse` as wrong), the chat
captures a **structured request**. This is the feedback loop: miss → queue → admin builds it →
next user reuses it (the Ratchet — every edge case leaves a durable artifact).

### 4.1 Request data model (`skill_requests` — Postgres, M-001 §4 peer table)

```
skill_requests
  id                 uuid pk
  user_id            text     -- Clerk user_id (tenant; M-001 T1 — JWT-derived, never caller-supplied)
  created_at         timestamptz
  status             text     -- 'new' | 'triaged' | 'building' | 'resolved' | 'wont_do' | 'duplicate'
  -- WHAT was asked (redacted; see S1) ------------------------------------------------
  fp_hash            text     -- the §3.1 reuse fingerprint (the dedup + loop-closure join key)
  task_terms         text[]   -- canonical method-nouns from the router (NOT raw chat text)
  oos_reasons        text[]   -- out-of-scope modalities the ask touched
  intent_summary     text     -- a SHORT, redacted one-line restatement (S1: PII-stripped, length-capped)
  -- WHAT data shape ------------------------------------------------------------------
  data_modality      text     -- DataProfile.code
  data_column_groups text[]   -- present named column-groups (shape, not values)
  data_numeric_bucket text    -- coarse numeric-col bucket
  -- WHAT was missing / tried ----------------------------------------------------------
  skills_tried       text[]   -- candidate skill ids the router/data-fit surfaced + rejected
  reject_reason      text     -- 'no_skill' | 'data_unmatched' | 'wrong_result' | 'oos'
  -- loop closure ---------------------------------------------------------------------
  resolved_by_skill_id text   -- the skill id that closed this fingerprint (L6)
  resolved_at        timestamptz
  -- governance (S1) ------------------------------------------------------------------
  expires_at         timestamptz  -- retention horizon; a sweep purges past this
  vote_count         int default 1 -- same fp_hash from N tenants → demand signal (deduped row)
```

Dedup: a second tenant hitting the same `fp_hash` **increments `vote_count`** on the existing row
(one row per fingerprint, not per user) — this both ranks admin priority and **minimizes PII
surface** (fewer rows, no per-user free text accumulating).

### 4.2 The queue + admin review surface

- **Queue**: the `skill_requests` table itself, ordered by `vote_count desc, created_at`.
- **Admin surface**: an **admin-only** view (separate from the tenant app) listing requests with
  their fingerprint, demand (`vote_count`), shape descriptors, and `skills_tried`. Admin actions:
  `triage` → `building` → `resolved | wont_do | duplicate`. Backed by `GET /admin/skill-requests`
  (admin-scoped; §6).
- **Build path (manual, by us)**: admin authors the skill the proper way — a new `skills/<id>/`
  with its `skill.json` (`skills/contract.py:16 SkillSpec`), discovered automatically by
  `registry.py:34 list_skill_ids` and indexed into the router by `extract/routing/vocab.py:41
  registry_entries`. **No new wiring** — an authored skill enters the reuse path the moment it
  ships, because the router and catalog already enumerate on-disk skills.

### 4.3 Closing the loop (L6)

When a newly-shipped skill's fingerprint covers an open request's `fp_hash`, the next chat turn
with that fingerprint resolves to `reuse`; the request is stamped `resolved` +
`resolved_by_skill_id`. Optionally, admin closure can notify upvoting tenants ("the skill you
asked for is now available"). The artifact that closed the gap is the **built skill**, not a chat
note — exactly the durable-home rule.

---

## 5. S1 (acceptance-gating) — admin-queue PII, retention, access control

Captured requests can carry tenant PII / sensitive query content / data snippets. This is an
**explicit hard requirement**, not an afterthought.

**R-S1.1 Redaction at capture (write-time).** The chat **never** writes raw query text or data
bytes to `skill_requests`. It writes the **fingerprint + structured descriptors** (`task_terms`,
`data_column_groups`, `data_modality`). `intent_summary` is the only free-text field and MUST be
(a) PII-stripped by a deny-list/transform pass (emails, names, accessions, IDs, file paths,
free-form patient/sample identifiers), and (b) length-capped. If redaction cannot be confidently
applied, `intent_summary` is dropped (the fingerprint alone still captures the demand). **No
column names that could be PII are stored raw** — column-groups are the *contract group names*
(`_SCHEMA` keys, `compat.py:205`), not the dataset's literal headers.

**R-S1.2 Retention limit.** Every row carries `expires_at`; a scheduled sweep purges expired rows
(default horizon **for owner review**, Q4 — e.g. 90 days for `new`, longer for `building`). A
`resolved` row may keep only its non-PII fingerprint + outcome for analytics; the free-text
`intent_summary` is purged on resolution.

**R-S1.3 Access control.** `skill_requests` is the **only** cross-tenant table in M-003. Tenant
API roles have **no read** on it. Reads are admin-only (`GET /admin/skill-requests`), behind an
admin claim on the Clerk JWT (M-001 D3) verified by the Lambda authorizer — a tenant `user_id`
can never list the queue. Writes are append/upsert-only from the authenticated chat path and
carry the JWT-derived `user_id` (M-001 T1), never a caller-supplied tenant id. The admin surface
is not part of the tenant Next.js app.

---

## 6. API surface (additive)

| Method | Path | Scope | Purpose |
|---|---|---|---|
| `POST` | `/ai/reuse/match` | tenant | intent + active-dataset assessment → `{outcome, skill_id?, confidence, candidates}` (§3.2). Pure read over router + catalog + workspace. |
| `POST` | `/ai/reuse/capture` | tenant | write/upsert a redacted `skill_requests` row (§4.1, S1). Returns the row id + `vote_count`. |
| `GET` | `/admin/skill-requests` | **admin** | the queue, ranked (§4.2). S1-gated. |
| `PATCH` | `/admin/skill-requests/{id}` | **admin** | status transitions; stamp `resolved_by_skill_id`. |

`/ai/reuse/match` reuses, unchanged: `route.py:159 route_text`, `registry.py:82 list_catalog`,
`compat.py:323 fit`, and (FE) `workspace/store.ts` selectors. No runner, catalog-schema, or
router-scoring change.

---

## 7. DEFERRED half — sandboxed codegen is FENCED (security boundary)

**On-the-fly AI code generation and execution is NOT built in this slice and MUST NOT be added
under M-003.** The chat may *describe* what a missing skill would do (to write a good
`intent_summary`); it may **never** generate or run code, query a database, or touch tenant bytes
through generated logic. Capture-now, execute-later.

If/when an "AI writes a new skill" capability is ever built, it is a **separate, gated**
workstream that MUST satisfy **all** of:

1. **Isolated sandbox** — generated code runs only in a single-tenant, network-egress-restricted
   isolate (Lambda/Firecracker microVM, or an equivalent ephemeral sandbox — cf. Vercel Sandbox /
   Firecracker), never in the API process, the skill runner, or the heavy Docker Lambda that holds
   real data.
2. **Read-only / SELECT-only data access** — no writes, no DDL; data reached only through a
   read-only/SELECT-only view scoped to the calling tenant's prefix (consistent with M-001 T1 S3
   prefix isolation). Generated code cannot widen its own scope.
3. **No secrets in generated code** — secrets stay in Secrets Manager (M-001); the sandbox gets
   none. Generated code cannot read credentials, env, or another tenant's prefix.
4. **Human review before promotion** — generated code is *captured* and reviewed by a human before
   it can ever become an installed skill or run against real data. It does not self-promote.

**The gate that must be crossed before it is ever built** (all required):
- Owner sign-off on the sandbox vendor/runtime + cost (`ask-before-docker-wsl` applies to any
  Firecracker/Docker isolate).
- A threat model + isolation acceptance test (no egress, no cross-tenant read, no secret reach)
  passing as a build gate — the same bar T1's cross-tenant isolation test sets in M-001.
- A human-review workflow defined for generated artifacts.
- Explicit removal of this fence in a successor spec, owner-approved.

Until that gate is crossed, the only "AI skill authoring" Selom does is: **a human (us) builds the
skill from a captured request.** (R-7 / the plan's "Sandboxed AI codegen — security-fenced;
capture now, execute later" deferral, plan §7.)

---

## 8. Acceptance criteria

**Reuse**
- A1. An intent + dataset whose fingerprint matches an **owned** skill returns `outcome=reuse`
  with that `skill_id` and opens it pre-filled — no install step. Verified on a real dataset
  (not `dev:mock`), per `verify-on-real-data-not-mock`.
- A2. An intent matching a catalog skill **not** in `WorkspaceState.skills` returns
  `outcome=suggest-install`; one click installs (`workspace/store.ts:237`) and re-matching then
  returns `reuse`.
- A3. The reuse `fp_hash` is computed from the router terms + `_frame_signature`/`DataProfile`
  via the **same** canonicalization discipline as `_result_cache.canonical_params` (sorted keys,
  stable rounding, drop-defaults) — demonstrated by a test asserting two shape-equal asks collide
  on one `fp_hash` while a different modality forks it.
- A4. A high task-score on data that fails the column-group contract (`compat._check_schema`)
  never returns `reuse` — it returns `suggest` or `capture` (data-fit AND task-fit both gate).

**Capture / loop**
- A5. A `capture` outcome writes exactly one `skill_requests` row; a second tenant with the same
  `fp_hash` increments `vote_count` and does **not** add a row.
- A6. Shipping a `skills/<id>/skill.json` that covers an open request's fingerprint makes the next
  matching turn return `reuse` and stamps `resolved_by_skill_id` — with **no** code wiring beyond
  the new skill dir (proves `list_skill_ids` + `vocab.registry_entries` auto-discovery).

**S1 (gating)**
- A7. No `skill_requests` row contains raw chat text, raw dataset headers, or data bytes;
  `intent_summary` passes the PII deny-list/transform and length cap, or is null.
- A8. A tenant JWT cannot read `GET /admin/skill-requests` (admin-claim required); the row's
  `user_id` is JWT-derived, never accepted from the request body.
- A9. Rows past `expires_at` are purged by the sweep; a `resolved` row retains no free-text
  `intent_summary`.

**Fence**
- A10. The shipped slice contains **no** code path that generates or executes code, runs SQL from
  model output, or reaches tenant bytes through generated logic. (Static gate / review checklist.)

---

## 9. Rejected alternatives

- **Reuse the row-level `input_sha256` as the reuse key** — rejected: it is exact-bytes (great for
  the result cache, `_result_cache.py:129`), so it never collides across two structurally-similar
  datasets; reuse needs a *shape* key (L1).
- **A new ML/embedding skill index** — rejected: the deterministic L1–L4 router already ranks
  skills with a curated synonym moat (`vocab.py`, `route.py`); a parallel matcher would drift.
- **localStorage capture queue** — rejected: cannot reach admin across tenants; no retention/access
  control → fails S1 (L4).
- **Store raw requests, redact on read** — rejected: PII at rest; one un-scrubbed reader leaks
  (L5). Redact at write.
- **Build the sandbox now behind a flag** — rejected: D7 fences it; the gate (§7) is unmet.

---

## 10. Open questions (for owner)

> **RESOLVED (owner, 2026-06-28):** PII posture = **balanced** → **keep** the redacted, length-capped
> `intent_summary` (Q6: not dropped), behind the deny-list + drop-if-uncertain rule (R-S1.1). Q4 →
> **90-day** retention default. Q1/Q2/Q5 → tune at build on real transcripts (bias toward `capture`
> early to seed the queue). The structured fingerprint stays the primary record.

- **Q1.** Confidence cut-points (θ_high / mid / low, §3.3) — tune on real chat transcripts, or set
  conservative defaults now? (Bias toward `capture` early to seed the queue?)
- **Q2.** Does `suggest-install` auto-install on accept, or always require the explicit install
  click? (Conversion vs. consent.)
- **Q3.** `vote_count` dedup is cross-tenant (one row per fingerprint). Acceptable that admin sees
  aggregated demand but not per-tenant identities? (This is the S1-preferred shape.)
- **Q4.** Retention horizon for `skill_requests` (S1 R-S1.2) — 90 days default? Different per
  status? Any compliance constraint from the eventual data-processing terms?
- **Q5.** Loop-closure notification — do we tell upvoting tenants when their requested skill ships,
  or silently let the next match reuse it? (Re-engagement vs. noise; needs the notification
  channel that doesn't exist yet.)
- **Q6.** Should `intent_summary` exist at all, or is the structured fingerprint enough? (Dropping
  it removes the last free-text PII vector entirely — strongest S1 posture, at some triage cost.)

---

## 11. Evidence index (existing infra this builds on)

| Infra | File:line | Used for |
|---|---|---|
| Content-addressed result cache; `canonical_params`, `cache_key(skill_id, version, param_spec, data_path, params)`, `input_sha256` | `app/backend/skills/_result_cache.py:96,129,68` | The hashing discipline the reuse `fp_hash` mirrors (§3.1) |
| Artifact lineage; `artifact_id = sha256(bytes)`, `materialize` | `app/backend/engine/lineage.py:104,248` | The existing content-addressing tier reuse sits above (§3.1) |
| Deterministic skill router; `route_text → FeasibilityMap` | `app/backend/extract/routing/route.py:159` | Task-side match (§3.2) |
| Keyword index; `find_in` (L1), `find_relaxed` (L3), `canon` | `app/backend/extract/routing/index.py:93,105,54` | Term extraction + canonicalization (§3.1) |
| Routing models; `FigureRoute.confidence`, `FeasibilityMap.skills/out_of_scope`, `RoutingCandidate.score` | `app/backend/extract/routing/models.py:132,149,150,84` | Confidence vocabulary + candidate shape (§3) |
| Vocab build from on-disk skills; `registry_entries`, `build_vocab` | `app/backend/extract/routing/vocab.py:41,76` | Auto-discovery — a new skill enters the router with no wiring (§4.2, A6) |
| Skill manifest; `SkillSpec` (`version`, `origin`, `omics_type`, `catalog`), `load_skill` | `app/backend/skills/contract.py:16,18,31,39,43,67` | What a built skill is; the catalog match target |
| Registry; `list_skill_ids`, `to_catalog_entry`, `list_catalog` | `app/backend/skills/registry.py:34,42,82` | Enumerate catalog for `suggest` + auto-discover built skills |
| Data-fit scorer; `FileAssessment`, `_frame_signature`, `_SCHEMA`, `_check_schema`, `DataFit`, `fit` | `app/backend/engine/compat.py:88,174,205,212,271,323` | Data-side fingerprint + the data-fit re-rank gate (§3) |
| Data profile; `DataProfile`, `Candidate`, `profile_data` | `app/backend/engine/cleaning.py:123,111` | `data.modality` for the fingerprint (§3.1) |
| Workspace Library types; `SavedPaper`, `WorkspaceSkill`, `WorkspaceState` | `app/frontend/lib/workspace/types.ts:50,88,96` | "What skills the account owns" — the reuse filter (§3.2) |
| Workspace store; `savePaper`, `installSkill`/`uninstallSkill`, `wselect` | `app/frontend/lib/workspace/store.ts:136,237` | Own/install affordances for `reuse`/`suggest` |
| Catalog entry shape | `app/frontend/lib/catalog/types.ts:44` | The FE shape `suggest-install` renders |
| M-001 Postgres schema (`skill_installs`, `analysis_jobs`, in-app RLS, JWT-derived tenant T1) | `docs/aws-materialization/plan.md:121-130,76-82` | Where `skill_requests` lives + the tenancy controls S1 inherits |
