# Selom — AWS Materialization + AI-layer Plan

Status: **Active build plan — amended in place.** The discussion gate is passed; building in
§6 order — **steps 1–5 shipped** (all four content-addressed stores ride the one `ObjectStore`
seam; verified live on the dev S3 bucket) **+ step 2 (jobs → SQL `analysis_jobs`) shipped**
(SQLAlchemy-portable `SqlJobStore` + Alembic; SQLite-validated, **Aurora provisioning deferred** to
the prod-deploy step). **Next = step 6** (presigned upload + parsed-parquet — the one genuine flow
rewrite). Created 2026-06-28. Supersedes the roadmap's planned Supabase + Cloudflare R2
materialization shape. Companion to memory `selom-aws-materialization-decision`.

> This doc consolidates: the persistence→schema **audit**, the package **eval**, the planner
> **architect blueprint** (16 decisions / 7 risks / 3 milestone specs), and the planner
> **QR pass** (which hardened the requirements below). The QR's findings are folded in as
> explicit "must-cover" requirements rather than left in the planner's ephemeral state.

---

## 1. Locked decisions (owner, 2026-06-28 discussion gate)

| # | Decision | Over | Why |
|---|---|---|---|
| D1 | **AWS + Vercel**, Selom-specific | a shared spine with eamos | eamos stays Supabase/Vercel/Render; Selom is heavier (scverse/omics), gets its own stack |
| D2 | **Aurora Serverless v2** (Postgres) | Neon · Supabase | owner "mostly AWS" — one vendor/bill, scale-to-zero, AWS-native |
| D3 | **Clerk** auth | Cognito · defer | best Next.js/Vercel DX; issues JWT → Lambda authorizer; `user_id` = tenant key |
| D4 | **Cloudflare** edge (DNS + WAF/DDoS) | Vercel-native · CloudFront | free WAF/DDoS, owner preference; Vercel owns asset caching (avoid double-cache); SSL Full(Strict) |
| D5 | "JSON too large" = **LLM-token** problem | bytes (Parquet/Arrow/MsgPack) | the pain is the AI-chat context, not render/storage → TOON/CSV + payload-shaping |
| D6 | **Local-dev / AWS-prod** config seam | dev-on-AWS | keep the inner loop fast/offline; flip backends by config (like `make_result_store` Local↔R2) |
| D7 | AI-skills = **safe slice** | sandboxed codegen now | reuse-via-fingerprint + capture-to-admin queue; defer arbitrary code execution (security) |
| D8 | **DuckDB + Parquet** data engine | Spark/SQL-warehouse | the cross-doc convergence (AWS spec · n8n/Forj · Selom roadmap) |

---

## 2. Target topology

```
Cloudflare (DNS · WAF · DDoS · SSL Full-Strict)
   → Vercel (Next.js frontend; owns asset caching)
      → Clerk (identity; JWT)
         → AWS API Gateway → Lambda authorizer (verifies Clerk JWT → user_id)
            ├─ Light zip Lambda (FastAPI+Mangum): /skills /gene-sets /papers/route
            │                                     /methods /citations /describe — catalog/routing/text
            └─ Heavy Docker/ECR Lambda (≤10GB): /skills/{id}/run /data/inspect /data/combine
                                                /papers/{id}/reproduce /figures/export — scverse + Kaleido
         → Aurora Serverless v2 (Postgres; in-app RLS) ── rows / pointers
         → S3 (presigned upload · Parquet · result JSON · artifacts) ── bytes
         → Secrets Manager (Clerk/DB/API keys)
   Observability: Sentry (errors) · PostHog (product)   Billing: Stripe
```

**Core invariant (threaded through every workstream):**
> content SHA = cache key = ETag = idempotency key = S3 object key = Postgres pointer.
> **Bytes live in S3; rows/pointers live in Postgres; the dev path never requires AWS.**

---

## 3. Workstreams (3 vertical-slice DRAFT specs)

Each becomes its own `docs/<slug>/spec.md` on sign-off. Foundation-first order.

### M-001 — AWS materialization foundation → `docs/aws-materialization/spec.md`
The win: Selom's backend was **built content-addressed + interface-swapped**, so 3 of 4 disk
stores are a backend swap (`storage/results.py:R2ResultStore` is already an S3-API twin behind a
`Protocol`; `_result_cache.py` and `engine/lineage.py` carry the same shape). Scope:
- **Postgres schema** (§4) with **in-app RLS** tenancy; **S3 key layout** (§5).
- **The config-seam swap** for all four stores (results · result_cache · lineage · the
  not-yet-abstracted reproduction `Ledger`) — local backend for dev, S3 for prod.
- **Three genuinely-new seams:**
  1. **Statelessness** — `jobs/store.py` in-memory `JobStore` → an `analysis_jobs` Postgres
     table (a Lambda poll hits a cold instance and sees nothing today).
  2. **Presigned S3 PUT upload** — replaces direct multipart (API Gateway ~6–10 MB cap;
     `main.py:_save_capped` buffers whole files; `engine/ingest.py` leaks `delete=False` temps).
  3. **Users / auth / tenancy** — there is no `user_id` anywhere today.
- **Gated** Docker/ECR heavy-Lambda lane vs the light zip lane.
- **FE state migration** — `lib/projects` · `lib/workspace` · `lib/catalog` localStorage →
  Postgres behind the existing store interfaces (the types are already DB-shaped).
- Migration order (§6), cost model (§7 R-1), IAM least-privilege draft, **local↔S3 parity test**,
  tier/quota/retention mechanism (§7 D-monetization).

**QR-hardened must-cover (M-001):**
- **T1 — Tenant isolation is structural, not conventional.** A `TenantQuery`/data-access
  wrapper that makes a forgotten `user_id` filter *impossible* (not just "remember to filter");
  **the Lambda derives tenant from the verified Clerk `user_id`, never a caller-supplied param**;
  an **S3 bucket policy / IAM condition** enforces `uploads/{user_id}/*` prefix isolation so a
  presigned URL can't read/write another tenant's prefix; **an automated cross-tenant isolation
  test is an acceptance gate.**
- **T2 — Presigned upload failure path.** PUT-succeeds-but-notify-POST-fails → orphaned object;
  spec a reconciliation (S3 event → confirm row, or a sweep) so it's not silent data loss.
- **T3 — Aurora cold-start.** Scale-from-0-ACU latency (10–30 s) → spec a min-ACU floor and/or
  client retry/backoff; flag the cost trade of a non-zero floor.
- **T4 — Cloudflare rationale** logged (over Vercel-native WAF / CloudFront): free WAF+DDoS,
  owner preference, DNS bundle; caching boundary = Vercel owns assets, Cloudflare = edge security.

### M-002 — AI-chat context serialization → `docs/ai-chat-context/spec.md`
"JSON too large" as an **LLM-token** problem. Scope: a **TOON-primary** serializer (markdown /
CSV fallback) + **schema-plus-sampled/aggregated-slice payload shaping** (never the whole matrix),
scoped to the lineage node / Ask-Selom dock; the **shared AI gateway = backend** (existing
decision, `selom-ask-selom-chat` / `selom-claude-acts-as-ai-gateway`).

**QR-hardened must-cover (M-002):**
- **A1 — Sampling-bias risk.** A sampled/aggregated slice can yield statistically misleading
  answers (aggregation masking, non-representative sample); spec how the slice is chosen and how
  the model is told what it is *not* seeing (honest framing + caveat surfaced to the user).
- **A2 — Log the gateway + context-scoping decision** (it currently has no on-topic DL entry).

### M-003 — AI-skills safe slice → `docs/ai-skills-safe-slice/spec.md`
Fingerprint(task+data) → **reuse** an existing skill via the keyword index / Workspace Library
(the n8n "schema-hash cache" = Selom's existing content-addressing = the ratchet) + **capture**
edge-case requests from the AI chat into an **admin queue** (we build it properly next time).
The deferred half (sandboxed codegen) is **fenced**: read-only / SELECT-only boundary, no
secrets-in-generated-code, capture-now-don't-execute.

**QR-hardened must-cover (M-003):**
- **S1 — Admin-queue PII.** Captured requests may hold tenant PII / sensitive query content;
  spec redaction, a retention limit, and access control on the queue.

---

## 4. Postgres schema (superset of the eamos UserProfile/AnalysisJob spec)

12 tenant tables; every one carries `user_id` directly or via `project_id`/`workspace_id` for
in-app RLS. Content-hash SHAs become PKs (`intermediate_tables.artifact_id`) or pointers
(`analysis_jobs.result_cache_key`, `input_sha256`). Full DDL goes in the M-001 spec.

`users` (Clerk user_id PK · email · stripe_customer_id · is_subscribed · tier · **max_projects /
max_datasets / max_storage_bytes** quota) · `workspaces` · `projects` · `datasets` (→ S3 keys ·
current_sha256 · qc · size_bytes) · `figures` (editable Plotly spec or S3 key · provenance ·
parent_figure_id · frozen) · `analysis_jobs` (status · params · input_sha256 · result_cache_key ·
result_json_s3_key · artifact_id — **replaces the in-memory JobStore**) · `intermediate_tables`
(artifact_id = sha PK · lineage) · `artifact_parents` (the D3 DAG edges) · `cleaning_recipes` ·
`gene_sets` · `papers` (+ `supplements`) · `reproduction_runs` (the Ledger) · `skill_installs`.

The internal gate's `inventory.md §3` named the workspace/project/dataset/figure/etc. set but
**never modeled users/auth/billing** (it was single-tenant) — those are the net-new tables.

---

## 5. S3 object layout (content-hash keyed, so disk→S3 is a prefix change)

```
uploads/{user_id}/{project_id}/{dataset_id}/{filename}   raw drop (presigned PUT)
uploads/{user_id}/supplements/{sha256}.{ext}             paper supplements
data/{sha256}.parquet                                    parsed/cleaned matrix
artifacts/{artifact_id}.csv + .meta.json                 D3 lineage (artifact_id = sha)
results/{job_id}.json                                    figure bundle (ETag = content hash → 304)
cache/result/{cache_key}.json · cache/render/{key}.json  C1/C2 caches
repro/{run_id}.json                                      reproduction Ledger
```

---

## 6. Lowest-risk migration sequence (build phase — gated on prerequisites §8)

1. ✅ **Result store → S3** (near config-only — proves the seam). **SHIPPED.**
2. ✅ **Jobs → SQL `analysis_jobs`** (kills the statelessness blocker; required before multi-instance). **SHIPPED** — SQLAlchemy-portable `SqlJobStore` + Alembic, `SELOM_JOB_STORE=memory|sql`; SQLite-validated, Aurora provisioning deferred to prod-deploy.
3. ✅ **Result-cache durable tier → S3** (the named C4; `_disk_read/_write` → the `ObjectStore`). **SHIPPED.**
4. ✅ **Artifact/lineage store → S3** (the named D4; `artifact_id` is already the key). **SHIPPED.**
5. ✅ **Reproduction Ledger → S3** (the new `LedgerStore` seam the others already had). **SHIPPED** (S3 side; the Postgres pointer row lands with step 2).
6. **Presigned S3 upload + parsed-parquet** (the one genuine flow rewrite; do after 1–5).
7. **Auth + users/billing + RLS, then FE localStorage → Postgres** (largest product lift; types pre-shaped).
8. **Split deploy** (light zip + heavy Docker Lambda); secrets → Secrets Manager; SSE → polling/WS.

Steps 1–5 (the four-store seam) + step 2 (jobs → SQL) are SHIPPED — the backend swaps the code was
built to absorb, plus the statelessness store. **6 is the genuine flow rewrite (presigned upload);
7 is the product/auth lift (where Aurora is provisioned + RLS/users/the JWT `user_id` land).**

---

## 7. Risks & deferrals

**Risks (with mitigation):**
- **R-1 Aurora idle cost** — verify min-ACU/idle billing; cost model before commit (cf. T3 latency trade).
- **R-2 API Gateway payload cap** — forces presigned upload (T2 covers the orphan path).
- **R-3 Cross-tenant leak** — the headline production risk; mitigated structurally by T1 (wrapper +
  JWT-derived tenant + S3 IAM prefix + isolation test).
- **R-4 Cold-start weight** — scverse + Kaleido need the Docker Lambda; light router stays zip.
- **R-5 AI sampling bias** (A1) · **R-6 admin-queue PII** (S1) · **R-7 TOON fidelity** (round-trip test).

**Deferrals (flagged, not silent):**
- **Docker/ECR image build** — `ask-before-docker-wsl`; owner approval before the build phase.
- **Sandboxed AI codegen** — security-fenced; capture now, execute later.
- **Tier/quota numbers** — LAUNCH-GATES "build now, gate later"; schema carries the fields.
- **pyarrow + duckdb** — adopt as an *extra* when the substrate lands, never the main solve
  (`selom-uv-sync-footgun`).

---

## 8. Prerequisites (before any AWS driving — build phase, not now)

- **AWS access:** an AWS MCP **or** AWS CLI v2 + a **least-privilege IAM** credential (not root).
  Not currently connected (I have render/vercel/supabase MCPs, no AWS). I'll spec the exact IAM
  policy so it stands up from one login.
- Owner approval on the **Docker/ECR** lane.

---

## 9. Packages (resolved — no spec needed)

Skip **mygene** (gene-clean already offline in `engine/cleaning.py`; live API breaks the offline
design), **bioinfokit** (duplicates native Plotly skills, emits static matplotlib — the OmicVerse
trap), **DESeq2** (R; already covered by `pydeseq2`; oracle-only). **scipy + numpy already core.**
Adopt **pyarrow + duckdb** as an extra **when the data substrate lands** (per §7 deferral).

---

## 10. Resolved at the gate (owner, 2026-06-28) + status

**The three DRAFT specs are authored:** `docs/aws-materialization/spec.md` (M-001),
`docs/ai-chat-context/spec.md` (M-002), `docs/ai-skills-safe-slice/spec.md` (M-003).

**Final owner rulings:**
- **Aurora cold-start** → **scale-to-zero now** (retry/backoff + a "warming up" state) + add a
  **0.5-ACU floor at launch** when real users arrive. Aurora is prod-only; dev stays local.
- **AI-layer PII** → **balanced**: the gateway **redacts identifier-like columns/values before any
  data leaves to the external LLM** (M-002), and the admin queue keeps a **redacted, length-capped**
  one-line summary (M-003) — not raw, not dropped.
- **Defaults locked:** keep both app-`TenantQuery` + DB RLS · denormalized `user_id` on every table ·
  parsed data stays CSV until the D4/D8 substrate lands · wire tier/quota/Stripe mechanism now, numbers
  at launch · Alembic migrations · hand-rolled TOON encoder (no venv dep) · Claude + a cheaper tier for
  simple chat Q&A · 90-day queue retention · reuse confidence cut-points tuned at build.
- **Docker** → approved for the AWS/ECR image (local Docker still unused).

**Two reconciliation items to apply when building:** (1) fold M-003's `skill_requests` into M-001's
unified schema; (2) M-002 owns LLM-context redaction (distinct from M-003's queue redaction).

**Next gate = AWS access** (owner sets up AWS CLI v2 + a least-privilege IAM per
`aws-access-setup.md`). Then build in the §6 order. Specs are amended in place as we go.
