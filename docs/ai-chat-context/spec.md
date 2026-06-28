# Selom — AI-chat Context Serialization Layer (M-002)

Status: **DRAFT — not yet built (spec only).** Created 2026-06-28. Workstream **M-002** of the AWS +
AI-layer plan.

> Primary source of truth: `docs/aws-materialization/plan.md` §3 (M-002) and locked
> decision **D5** — *"JSON too large" is an LLM-**token** problem, not a byte problem.*
> Byte-level concerns (Parquet/Arrow/MsgPack for render/storage) are out of scope here;
> they live in M-001. This spec is the **serialization + payload-shaping contract** the
> future "Ask Selom" chat will call.

> Feature status: **deferred — spec-before-build.** No AI-chat / "Ask Selom" surface
> exists today. A repo sweep of `app/frontend` and `app/backend` for `ask-selom` / AI-chat
> / a lineage-rail dock found only a *forward reference*: `workrail.tsx:46` notes the rail's
> active-section colour is "the visual language the future Ask-Selom chat will scope itself
> by." So this is a **contract spec** for the layer that future chat plugs into, written now
> so the data shapes and honesty guarantees are settled before any chat code is typed.

---

## 1. The problem (two-part)

Feeding a scientist's data into the chat so the model can answer questions about it is the
core need. The naive path — JSON-serialize the table/matrix into the prompt — **burns
tokens** and, for a real omics matrix, is impossible (an AnnData of 24×18,102 or a 5M-row
combined tree blows any context window). D5 reframes this as a token problem with a
**two-part fix**, and the order matters:

| Part | Lever | One-line |
|---|---|---|
| **(a) Serialization format** | smaller | encode whatever we *do* send in a token-lean format (not JSON) |
| **(b) Payload shaping** | **bigger** | decide *what* to send — never the whole matrix; a schema + a representative slice + summary stats |

Payload shaping is the dominant lever (per the n8n principle in the source plan: *push
compute to the engine, fetch only the relevant rows*). Serialization is the multiplier on
top. A spec that only swapped JSON→TOON would still try to ship the whole matrix and still
fail. **Shape first, then serialize.**

---

## 2. Where it plugs in (the contract)

```
Ask-Selom dock (FE, future)            ── scoped to the workrail's active lineage node
   │  user question + the selected node's id (dataset | stats-table | figure)
   ▼
Backend AI gateway (this layer)        ── the shared gateway = backend (Decision D-M2-1)
   1. resolve the node → its Selom object (DataBundle | StatsTable | FigureSpec | provenance)
   2. PAYLOAD-SHAPE it  (§5)  → schema + representative slice + summary stats + scope-meta
   3. SERIALIZE the shaped payload (§4)  → TOON | CSV | markdown | JSON
   4. assemble the context envelope (§6) → hand to the LLM provider
   ▼
LLM provider (Claude, via the gateway)
```

The FE ships only a **node reference + the question**, never bytes. The gateway owns
resolution, shaping, serialization, the provider call, and the honesty framing. This keeps
the whole-matrix problem on the server, where the data already lives.

**Selom objects this layer must serialize** (real shapes, cited):

| Object | Shape | Source |
|---|---|---|
| **StatsTable** | `{columns: string[], rows: (str\|num)[][], title?}` | backend `skills/_table.py:24`; FE `lib/skills-api.ts:47` |
| **DE table** (a StatsTable, already ranked + capped) | `gene·log2FC·padj·direction`, sorted by padj, capped `max_rows=300` with an honest truncated title | `skills/_table.py:44` (cap at `:67`, honest title at `:71`) |
| **Data matrix** (`DataBundle`) | wraps `AnnData \| DataFrame \| dict` + `kind`/`source`/`design`/`qc` | `engine/databundle.py:32` |
| **Dataset schema** (the `/data/inspect` view) | `kind` · `profile` · `source` · `qc` · `routing` · `data_fit` (no cell payload) | `main.py:375`; column list pattern `main.py:465` (`[str(c) for c in df.columns]`) |
| **Figure spec** | Plotly `{data, layout}` dict | `skills/contract.py:88`; FE `FigureSpec` `lib/skills-api.ts:1,112` |
| **Skill provenance** | `SkillSpec{origin, background, references[], catalog}` | `skills/contract.py:16` (origin `:31`, refs `:50`) |
| **Repro provenance** | `SourceTag{ref, faithful, note, badge}` | `reproduction.py:157` |

---

## 3. Decision log

| # | Decision | Rationale (the WHY — 2+ steps) |
|---|---|---|
| **D-M2-1** | **The shared AI gateway = the backend.** All chat → LLM traffic goes through one backend gateway; the FE never calls a provider and never holds a key. | (1) Keys/secrets live in one place (Secrets Manager, M-001 §2) — a FE-side provider call would leak them. (2) The data the chat reasons over already lives backend-side; shaping a matrix there avoids shipping it to the browser only to ship it back out. (3) One gateway = one audit point for cost, redaction, and the honesty framing (§7 A1). (4) Consistent with the existing `VisionClassifier` dev-gateway precedent and memory `selom-claude-acts-as-ai-gateway` / `selom-ask-selom-chat`. This **logs A2** — the gateway + context-scoping decision had no prior on-topic entry. |
| **D-M2-2** | **Context is scoped to the selected lineage node**, not the whole project. | The workrail already models the working context as a single active section/node (`workrail.tsx:46`, `RailView` `:49`). Scoping the payload to that node (the selected dataset / stats-table / figure + its lineage) bounds the token budget *by construction* and matches the user's mental focus — they asked about *this* panel. Whole-project context would reintroduce the matrix-too-large problem. |
| **D-M2-3** | **Payload shaping is the primary fix; serialization is secondary.** | Shaping caps the token cost at the *what-to-send* layer (orders of magnitude); format choice trims a further ~30–60%. Order is load-bearing: serialize-only still ships the whole matrix and still fails (§1). |
| **D-M2-4** | **TOON is the primary serializer**, with CSV and markdown-table fallbacks; tiny payloads may stay JSON. | TOON (Token-Oriented Object Notation) declares an array's fields once and streams rows tab/space-delimited — ~30–60% fewer tokens than JSON on **uniform arrays-of-objects** (exactly the StatsTable/DE-table shape), while keeping structure JSON loses in CSV. Selection rules in §4. |
| **D-M2-5** | **Every context payload carries a hard token ceiling** (default budget in §5), enforced server-side before the provider call. | A silent over-budget payload is the failure mode D5 names. A ceiling makes shaping *mandatory*, not best-effort, and makes cost predictable per call. |
| **D-M2-6** | **Honest scope framing is part of the serialized payload, not an afterthought.** | A sampled/aggregated slice can mislead (§7 A1). The model must be *told in-band* what it is not seeing, and the user must see the same caveat. This is a structural requirement, mirroring Selom's "honest classification" rule (`data_unmatched` not forced success). |

---

## 4. Serialization format (Part a)

### 4.1 Primary: TOON

Encode the shaped payload as **TOON** when it is a uniform array-of-objects (the common
case: a StatsTable, a DE table, a sampled row slice). TOON writes the field header once and
each record as a delimited row, so per-row key repetition (JSON's main token tax) is paid
once. Expected saving on uniform tabular data: **~30–60% vs pretty JSON**, with structure
(types, nesting for the schema/summary blocks) preserved where CSV would flatten it away.

### 4.2 Fallbacks and the selection rule

The gateway picks **one** format per payload block by shape, not globally:

| Payload shape | Format | Why |
|---|---|---|
| Uniform array-of-objects, ≥ a few rows (StatsTable, DE rows, sampled slice) | **TOON** | leanest that *keeps* columns + structure |
| Flat, single homogeneous table where structure is obvious and the model only needs values | **CSV** | leanest of all; acceptable structure loss because the column header + the §6 schema block already carry the structure |
| Nested / heterogeneous (schema block, summary-stats block, provenance, mixed dtypes) | **TOON** | preserves nesting JSON-style without JSON's token cost |
| Tiny (a handful of scalars, a 1–3 row table, the figure's title/axis labels) | **JSON** ok | below the break-even where TOON's header overhead pays off; readability wins |
| Free-text / methods / legend | **markdown** | it is prose, not a table; markdown is the readable, model-native form |

Markdown-table is the **human-readable fallback** when a payload will also be surfaced to
the user (e.g. echoed in the dock) — readability over raw token-minimality.

### 4.3 Round-trip fidelity (REQUIRED — R-7)

A serialization that the model silently mis-reads is worse than verbose JSON. The layer
ships with a **round-trip fidelity gate** as an acceptance test:

- **Reconstruction test:** for each format, encode a set of representative fixtures
  (a StatsTable, a 300-row DE table, a stratified matrix slice, a nested schema+summary
  block) and assert the values can be **reconstructed exactly** — cell-for-cell, dtypes
  intact, column order intact. Reconstruction is checked both by a deterministic decoder
  *and* (advisory, not gating) by asking the model to echo the parsed table back.
- **Token-win assertion:** assert TOON's token count is materially below JSON's on the
  uniform fixtures (the ~30–60% claim must hold for the shapes we actually send, or the
  format choice is wrong for that shape and falls back).
- **Rectangularity preserved:** the encoded→decoded StatsTable must still pass the existing
  result-seam guard `validate_result_table` (`engine/frame_schema.py:146`) — no ragged rows
  introduced by encoding. Reuse that validator; don't fork a second notion of "valid table."

---

## 5. Payload shaping (Part b — the bigger lever)

**Invariant: NEVER serialize the whole matrix.** Every payload the gateway builds is, at
most, three bounded blocks:

1. **Schema block** — always sent. Columns + dtypes + shape (e.g. `n_obs × n_vars` for an
   AnnData, `n_rows × n_cols` + column dtypes for a frame), the modality `kind`, the design
   groups (`DataBundle.design`), and a missingness/QC summary. Drawn from the `/data/inspect`
   view (`main.py:375`) and the column-list pattern (`main.py:465`) — **no cell payload**.
2. **Representative slice** — a *bounded* sample or aggregate of actual rows (strategy
   below), so the model sees real values without the whole matrix.
3. **Summary-stats block** — per-column / per-group distribution: n, mean, min/max, key
   quantiles (e.g. 5/25/50/75/95), missing-count, and for grouped designs the per-group
   versions. This is what stops a sample from hiding the tails (§7 A1).

### 5.1 Sampling / aggregation strategy

The slice must be **representative by construction**, not a naive `head()`:

- **Stratified by design group.** Sample proportionally across the `DataBundle.design`
  groups (control/treatment, genotype, cluster) so no group is dropped — directly answering
  the `scrna batch≈genotype confound` lesson (a head() of a group-sorted matrix is a single
  condition). Guarantee ≥1 row per non-empty group even when proportional rounding would
  zero a small group.
- **Rank-aware for already-ordered tables.** A DE/StatsTable is already sorted (most
  significant first, `_table.py:54`). Send **head + tail + a strided/random middle** so the
  model sees the significant rows *and* the null bulk — never just the top, which would
  imply everything is significant. The existing `de_table` cap (`max_rows=300`,
  `_table.py:67`) is the *upstream* cap; the chat layer applies a **tighter token cap** on
  top of it.
- **Deterministic seed.** The sample is reproducible (a fixed seed keyed on the content
  SHA) so the same question yields the same context — required for the fidelity test and for
  not surprising the user on a re-ask.
- **Aggregate instead of sample when a sample can't be representative.** For a question
  about group-level structure (cluster abundance, per-condition means), send the
  **aggregate** (group-by summary) rather than rows — but flag it (§7 A1: aggregation can
  mask within-group spread, so the summary-stats block must still carry the dispersion).

### 5.2 Size budget / token ceiling

- **Default context budget: ~2–4k tokens** for the data blocks (DRAFT — owner to set the
  real number against the chosen model's window and cost). Schema + summary blocks are
  cheap and **always** fit; the **slice flexes to fill the remainder**, never the reverse.
- **Hard ceiling enforced server-side** before the provider call (D-M2-5). If the shaped
  payload would exceed it, shrink the slice (fewer rows, then aggregate-only) — never drop
  the schema or the scope-meta. Over-budget is a logged event, not a silent truncation.
- **Token accounting, not byte accounting** — measured with the provider's tokenizer (D5),
  since the whole point is tokens.

---

## 6. The context envelope (wire shape)

What the gateway hands the model, per scoped node:

```
scope-meta     (REQUIRED, plain language, model-readable + user-surfaced — §7 A1):
   "Context for <node>: <kind>, full shape <R × C>. You are seeing a
    <stratified|rank-aware|aggregate> sample of N of R rows (seed S), plus
    per-group summary stats. You are NOT seeing the other R−N rows; do not
    state exact counts/totals beyond the schema + summary blocks."
schema block        (TOON/JSON — §5.1)
summary-stats block (TOON — §5.3)
representative slice (TOON/CSV — §4.2)
provenance          (which skill/params produced this; SkillSpec.references / SourceTag)
user question
```

The **scope-meta line is non-optional** — it is the in-band honesty contract (D-M2-6). The
same sentence (or its structured fields) is surfaced to the user in the dock as a caveat
chip (§7 A1), so the model and the scientist share one honest account of what was sent.

---

## 7. Risks & mitigations

### A1 — Sampling/aggregation bias can mislead the model (HEADLINE RISK)

A sampled or aggregated slice can produce statistically **misleading** answers:
- *Non-representative sample* — a naive head() of a group-sorted matrix shows one condition;
  the model concludes a difference that is an artefact of ordering.
- *Aggregation masking* — a group mean hides bimodality / outliers / within-group spread;
  the model calls a noisy effect "clean."

**Mitigation (structural, not a footnote):**
1. **Representative by construction** — stratified-by-design + rank-aware + per-group
   guarantees (§5.1); deterministic seed. The sample is *designed* not to drop a group or a
   tail.
2. **Carry the distribution, not just the sample** — the summary-stats block (§5, quantiles
   + dispersion + n + missingness) travels with every slice, so even an aggregate can't fully
   hide spread. The model gets the shape of what it can't see.
3. **Tell the model what it is NOT seeing — in-band** — the scope-meta line (§6) states the
   full shape, sampled N of R, the method, and an explicit instruction not to assert exact
   counts/totals beyond the schema + summary. Honest framing is part of the payload.
4. **Surface the caveat to the user** — the dock shows "answer based on a sample of N of R
   rows (method)" so the scientist is never silently misled. Mirrors Selom's honest-
   classification rule (`data_unmatched` over a forced success).
5. **Prefer engine-computed answers over model-inferred ones** — when the question is a
   computable statistic (a count, a p-value, a fold-change), the gateway should route to the
   real engine/skill and feed the model the *computed* result, not ask it to infer from a
   sample (the n8n "push compute to the engine" principle). Inference-from-sample is the
   fallback, and it is always caveated.

### Other risks

- **R-7 — TOON fidelity** (model mis-parses the lean format) → the round-trip fidelity gate
  (§4.3) is an acceptance test, and any shape that fails it falls back to a safer format.
- **Format mis-selection** — picking CSV for a payload whose structure the model needs →
  selection is per-block by shape (§4.2), and the schema block always carries the structure
  CSV drops.
- **Stale context** — the node mutates after the context was built → key the sample/seed on
  the content SHA (the core invariant from the source plan §2); a changed SHA = a fresh
  context, never a silently-stale one.
- **PII / sensitive content in the payload (gateway-owned; balanced posture — owner 2026-06-28).**
  The gateway **redacts identifier-like columns/values before any data leaves to the external LLM** —
  sample/patient IDs, names, accessions, file paths, and free-form identifiers are stripped/transformed
  at the single choke point (D-M2-1). This is a surface **distinct from** M-003's admin-queue redaction
  (S1): here it is the *context sent to the provider*. **Balanced** = strip the obvious identifiers and
  send identifier-stripped sample rows (not maximum-strip, not minimal). Shares M-003's redaction
  utilities but runs as its own pass on the payload.

---

## 8. Acceptance criteria

A future build of this layer is done when:

1. **Shaping is mandatory and bounded.** No code path serializes a whole `DataBundle`
   matrix; every payload is schema + bounded slice + summary, under the §5.2 token ceiling,
   enforced server-side. A test feeds a large matrix and asserts the payload stays under
   budget. *(D-M2-3, D-M2-5)*
2. **Format is chosen by shape.** Uniform tables encode as TOON (or CSV per §4.2), nested
   blocks as TOON, tiny as JSON, prose as markdown — a unit test covers each branch.
   *(D-M2-4)*
3. **Round-trip fidelity gate passes.** The §4.3 reconstruction + token-win + rectangularity
   tests pass on the fixture set (StatsTable, 300-row DE table, stratified matrix slice,
   nested schema block). *(R-7)*
4. **The slice is representative.** A test with a group-sorted / class-imbalanced fixture
   asserts every design group appears in the slice and the summary-stats block carries
   per-group dispersion. *(A1.1, A1.2)*
5. **Honesty is in-band and surfaced.** Every serialized envelope contains the scope-meta
   line with true shape + sampled N-of-R + method; a test asserts it is present and accurate;
   the dock contract surfaces the same caveat to the user. *(A1.3, A1.4, D-M2-6)*
6. **Single gateway.** The FE ships only `{node-ref, question}`; no provider key or whole
   payload crosses to the browser; the decision + rationale are logged here. *(D-M2-1, A2)*
7. **Computable answers route to the engine.** Where the question maps to a skill/stat, the
   gateway feeds the computed result rather than asking the model to infer from a sample.
   *(A1.5)*

---

## 9. Open questions (for owner review)

> **RESOLVED (owner, 2026-06-28):** Q1 → **hand-rolled tiny TOON encoder** in-repo (no venv dep,
> `selom-uv-sync-footgun`). Q2 → token ceiling **~3k** default, finalized against the chosen model at
> build. Q3 → **Claude** (repo Opus default) + a **cheaper tier** (e.g. Haiku) for simple table Q&A.
> PII posture = **balanced** (gateway redaction of identifier-like values before the LLM, §7).
> Q4/Q5/Q6 → tune at build.

1. **TOON dependency vs hand-rolled encoder.** Adopt a TOON library or write a ~small
   encoder/decoder in-repo? Given `selom-uv-sync-footgun` (adding backend deps is risky on
   the hand-sewn venv) and that our payloads are narrow (uniform tables), a tiny in-repo
   encoder may be the lower-risk path. Owner call.
2. **Token ceiling number.** §5.2 proposes ~2–4k tokens for data blocks — what is the real
   budget against the chosen model's window and the cost target? (Pairs with the M-001 cost
   model.)
3. **Which provider/model behind the gateway.** Claude (consistent with the repo's Opus
   default) — confirm, and whether a cheaper model handles the table-Q&A tier.
4. **Inference-vs-compute routing depth.** How aggressively should A1.5 route to the engine?
   A simple "if the question names a count/stat, compute it" heuristic now, or a fuller
   intent classifier later?
5. **Aggregate granularity.** Default group-by keys for the aggregate path — design groups
   only, or also cluster/leiden labels when present?
6. **Does the chat ever need more than one node?** D-M2-2 scopes to a single node; a
   "compare these two figures" question would need a 2-node envelope. Defer or design the
   multi-node envelope now?

---

## 10. Rejected alternatives

| Alternative | Why not |
|---|---|
| **Byte-level compression** (Parquet/Arrow/MsgPack) for the chat payload | Solves the wrong problem — D5: the pain is *tokens in the prompt*, not bytes on the wire/disk. Those formats aren't even text the model reads. (They remain right for M-001 storage.) |
| **Serialize-only, keep JSON→TOON the whole fix** | Ignores the bigger lever — still ships the whole matrix, still blows the window (§1). Shaping is mandatory. |
| **Send the whole table, raise the context window** | Doesn't scale to a real omics matrix (24×18k, 5M-row trees); linear cost growth; a window is finite. Shaping is O(budget), not O(matrix). |
| **CSV everywhere** | Leanest, but flattens structure the model needs for nested schema/summary/provenance blocks; kept only as a per-block choice for flat tables (§4.2). |
| **FE-side LLM calls** | Leaks keys, ships the matrix to the browser and back, and fragments cost/redaction/honesty control — rejected by D-M2-1. |
| **Naive head() sampling** | Biased on sorted/grouped data (the scRNA batch≈genotype trap); replaced by stratified + rank-aware sampling (§5.1, A1). |
