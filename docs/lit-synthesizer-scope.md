# lit-synthesizer — scope (Phase A+B+C SHIPPED; D remains)

> Status: **Phase A + B + C SHIPPED 2026-06-18** (A `2a982be`, B `e460fd5`, C this commit) — `litsynth/`
> + `POST /methods/compose` (deterministic multi-skill methods synthesizer, offline, no new deps,
> `methods.build_body` single-sourcing the citations) **+** `GET /citations/search` · `/citations/by-doi`
> (NCBI E-utilities PubMed lookup **+ bioRxiv/medRxiv preprint lookup with per-record `license`**: stdlib
> `urllib`+`xml.etree`+`json`, self-throttled + on-disk cache, fetcher behind a single shared seam →
> offline-tested AND live-verified against the real APIs). bioRxiv `license` field + the **no-free-text-
> search-API** constraint re-verified live at build 2026-06-18. NCBI facts (NBK25497: **3 req/s keyless,
> 10 with a key**). The 2nd ClawBio platform capability (sibling of the shipped `data-extractor`/X4).
> **Phase D (reproduction `Ledger` → paper-level `MethodsSection`) NOT built.**

## What it is

Turn **a record of what Selom did to a dataset** into two publication artifacts:

- **(a) Auto-methods prose** — deterministic, template-driven Methods paragraphs describing the
  skills that ran, with resolved params/thresholds + dataset modality. **No LLM** (deterministic,
  license-clean, non-hallucinating).
- **(b) License-clean citations** — per-skill *canonical* tool references + optional topical
  PubMed/bioRxiv lookups, pure-stdlib `urllib`.

## Key insight (re-verify at build)

**Half of this already exists.** `app/backend/methods.py` is already a deterministic auto-methods +
canonical-citations engine: ~20 per-skill templates returning `(text, citations)`, no LLM, with
`tests/test_methods.py` asserting cited prose per skill. lit-synth is therefore: **(1)** promote
`methods.py` from single-skill to a **multi-skill "analysis story" synthesizer** (stitch a *sequence*
of skill runs into one Methods section, dedup citations), and **(2)** add a **network citation-lookup
layer** (`litsynth/`) mirroring the `extract/` package. _Re-read `methods.py` lines 19–35 (canonical
refs) + `build()` before building — single source of truth for refs; import them, don't copy._

## Capability surface

- **Methods synthesizer (deterministic, offline, no new deps).** Input: an ordered list of skill
  runs `(skill_id, resolved_params)` + modality (+ optional dataset descriptor). This is exactly what
  `ReproRun.params` already records. Emits one `MethodsSection` (intro sentence → per-skill paragraphs
  in run order, deduped) + a deduped ordered citation list (reuses each skill's existing
  `methods.build()` output verbatim; adds only connective/intro/dedup logic).
- **Citation lookup (network, stdlib `urllib`, mockable).** Input: a free-text topic or a DOI. Emits
  `Citation[]` (title/authors/year/venue/doi/pmid/url/source/`metadata_license`). Degrades to an
  empty list + `degraded=True` offline — the prose half must never fail over a lookup timeout
  (mirror `reproduction.run_panel`'s "never fail over the prose half").

## Module layout (mirror `extract/`)

```
app/backend/litsynth/
  models.py     Citation, SkillRunRef, MethodsSection (pydantic v2, mirror extract/models.py)
  synth.py      compose_methods(runs, modality, dataset=None) — the deterministic core, NO network
  citations.py  per-skill canonical refs keyed by skill_id, IMPORTED from methods.py (no copy)
  pubmed.py     NCBI E-utilities client (urllib + xml.etree): esearch -> efetch/esummary
  biorxiv.py    bioRxiv/medRxiv client (urllib + json): details/{server}/{doi}/na/json
  cache.py      on-disk JSON response cache (reproducible lookups + offline tests)
```
`synth.py` imports nothing from `pubmed`/`biorxiv` at module load — lookups are dependency-passed
(like the gated oracle), so the offline core test is trivial.

## Endpoints (additive, mirror main.py)

- `POST /methods/compose` — `{runs:[{skill_id,params,order}], modality, dataset?}` → `MethodsSection`
  (deterministic, offline). **The headline.**
- `GET /citations/search` — `q, source=both|pubmed|biorxiv, max_results, min_year?` →
  `{results:[Citation], degraded}`. Network, cached.
- `GET /citations/by-doi` — `doi=...` → one `Citation`.
- **Do NOT** change the shipped `/skills/{id}/run` response shape in Phase A (FE contract = cross-lane).

## Citation sourcing (trust order)

1. **Canonical per-skill tool refs** — always, confidence 1.0, offline (the backbone, from `methods.py`).
2. **DOI resolution** — deterministic, network, cached (exact, reproducible).
3. **Topical lookups** — advisory, confidence < 1.0, **off by default** (free-text results drift as
   the index grows → bad for a reproducible-figure product; the cache pins a query→result snapshot).

## License analysis — VERIFIED 2026-06-18

- **Code deps: none new; stdlib only** (`urllib`, `xml.etree.ElementTree`, `json`). Matches existing
  precedent: `skills/string_network/run_real.py` + `scripts/build_wikipathways.py` already use
  `urllib` for live APIs. No AGPL/GPL surface.
- **NCBI E-utilities** (verified against NBK25497): **3 req/s without an API key, up to 10 req/s with
  a key**; `tool`/`email` params recommended (required to lift an IP block). Client MUST self-throttle
  (≥0.34 s spacer keyless) + set `tool=selom` + a contact `email` on every request. API key optional
  via env (`SELOM_NCBI_API_KEY`). Bibliographic metadata (title/PMID/DOI) is US-gov, not copyrightable;
  do not redistribute abstract corpora without checking terms.
- **bioRxiv API** (re-verified live at build against api.biorxiv.org): endpoint
  `details/{server}/{doi}/na/{format}`, `server ∈ {biorxiv, medrxiv}` (shared `10.1101` DOI prefix →
  `by_doi` tries biorxiv then medrxiv). Response is `{messages, collection}`; **each record carries its
  own `license` field** (confirmed live: `cc_by_nc_nd`, `cc_no`=all-rights-reserved) — surfaced on
  `Citation.metadata_license`, never assumed CC. Quirks handled: `authors` is one `"Last, F.; …"` string
  (not a list), `date` is ISO `YYYY-MM-DD`, `collection` holds one record **per version** (take the max),
  a miss is `{"status":"no posts found"}` + empty collection (clean `None`, not an error). **No documented
  rate limit** (polite 0.5 s self-throttle + descriptive `User-Agent`, reusing Phase B's `ThrottledFetcher`).
- **bioRxiv has NO free-text search API** (verified): the public API is DOI/date/interval-addressed only.
  So bioRxiv's role is **DOI resolution + license capture** (deterministic tier-2), not topical search —
  `/citations/search?source=biorxiv` returns `[]` honestly rather than fabricating results (`source=both`
  topical search resolves via PubMed, which already indexes many preprints).

## Risks
- NCBI rate-limit/IP-block → mandatory throttle + tool/email + cache.
- bioRxiv metadata-redistribution → store bibliographic fields + the per-record license tag only;
  defer any abstract-corpus use to the pre-launch gate ([[commercial-gated-tools-build-now-gate-later]]).
- Topical-lookup reproducibility → cache pins snapshots; tiers 1–2 are exact, tier 3 advisory.
- Hallucination → prose is template-only (no LLM); citations are static-table-or-API-echo only.
- Ledger intersection → the synthesizer **consumes** `ReproRun.params` and re-derives the section
  (single algorithm); don't write `MethodsSection` back into the ledger in Phase A.

## Phased build
- **Phase A — SHIPPED `2a982be` (deterministic core, zero deps, zero network):** `litsynth/`
  (`models.py` `SkillRunRef`/`MethodsSection` + `synth.py` `compose_methods` + `citations.py`
  single-sourcing `methods.build_body`) + `POST /methods/compose`. The one refactor: `methods.py`
  gained `build_body()` (prose + citations, no attribution) so `build()` stays byte-identical and
  `/skills/{id}/run` is untouched. Dedups citations first-seen; one consolidated Selom attribution
  names all skills+versions. pytest 349 (+9); ruff clean; `tests/test_litsynth.py`.
- **Phase B — SHIPPED `e460fd5` (PubMed lookup):** `pubmed.py` (NCBI E-utilities, `esearch`→`esummary`;
  `ThrottledFetcher` 3/s keyless · 10/s keyed, injectable clock/sleep/opener) + `cache.py` (tolerant
  on-disk JSON, `has()` ≠ miss vs cached-None) + `lookup.py` (env-wired singletons, all injectable,
  degrade to `[]`/None + `degraded=True`) + `GET /citations/search` · `/citations/by-doi`. Network behind
  one fetcher seam → 13 offline cases (real-format fixtures) **and** live-verified (real SCANPY parse).
  Stdlib only. pytest 362 (+13); ruff clean; `tests/test_litsynth_citations.py`.
- **Phase C — SHIPPED (bioRxiv/medRxiv lookup):** `biorxiv.py` (DOI-addressed `details` client, stdlib
  `urllib`+`json`, **reusing Phase B's `ThrottledFetcher`/`Fetcher` seam** — no new transport code; parses
  the `; `-joined author string, ISO date, multi-version `collection` → latest; captures the per-record
  `license` on `Citation.metadata_license`) wired into `/citations/by-doi` + `lookup.citation_by_doi`
  via a `source ∈ {both, pubmed, biorxiv}` selector (both = PubMed first, bioRxiv/medRxiv fallback that
  also carries the license). `/citations/search` gained `source` too (biorxiv → honest `[]`; no term API).
  Network behind the shared fetcher seam → 8 offline cases (real-format fixtures) **and** live-verified
  (real preprint: PubMed-miss → bioRxiv fallback resolved `cc_by_nc_nd`). Stdlib only. pytest 370 (+8);
  ruff clean; `tests/test_litsynth_citations.py`.
- **Phase D (next):** feed a full reproduction `Ledger` → a paper-level `MethodsSection` (the headline
  tie-in of lit-synth to the reproduction engine — `methods.build_body` is already the reusable unit).

## Open questions (owner)
1. Keep `/skills/{id}/run` returning the bare `{text, citations}` dict in Phase A (recommend: yes).
2. NCBI contact `email` to register + key now vs keyless — _Resolved Phase B: keyless (3/s + self-throttle
   + `tool=selom`); `email` + `api_key` read from `SELOM_NCBI_EMAIL` / `SELOM_NCBI_API_KEY` (unset in dev).
   Registering a key/email is a pre-launch gate, not needed to build/test._
3. Topical lookups off-by-default (recommend: yes).
4. Include medRxiv alongside bioRxiv — _Resolved Phase C: yes; `by_doi` tries `biorxiv` then `medrxiv`
   (shared `10.1101` prefix), `source` selector exposes both._
