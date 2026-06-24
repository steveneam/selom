# Spec — Skill references / "Skill Information" section (`skill-references`)

## What
Give every skill a structured **references / background** block in its `skill.json`, surfaced in the
Skill Store detail + install screen as a "Skill Information" section, so someone deciding whether to
install a skill can read its publication basis, source repo, the standard it implements, and the
datasets it was validated against. It pairs with the existing `origin` (proprietary/commodity) +
`catalog.license` metadata to form a single **skill provenance card**: *what is this, where does it
come from, can I trust/cite it.*

> **Scope (owner-set 2026-06-24): FULL first build** — schema (R1–R2) + Store provenance-card UI (R3)
> + validation (R4) + the R5 seed wave (ERG family · `gsea` · `melody` · `cepo`). Wider backfill +
> auto-population remain follow-ups (Out of Scope).

## Context
### Why this matters
Most Selom skills have a real provenance — a paper, a library/repo, a community standard, or a
validation dataset — but today that lives only in code comments, the methods builder, and the spec
files, invisible to someone browsing the Store. Surfacing it:
- is on-brand: Selom's positioning is **provenance-first / open-core** (`docs/proprietary-skills.md`,
  the lit-synthesizer, the Reproducibility Score). A "cite this skill" affordance is differentiating.
- supports the install decision: license + origin + references together answer "is this a thin
  wrapper or original IP, what's it based on, is it license-clean for my use."
- is mostly **assembly, not research** — the citations already exist: the methods/lit-synthesizer
  output (`methods.build_body`, `/citations/*`), the embedded code comments (e.g. the ERG refs added
  in T15: ISCEV 2022, Bush 2019, Lyubarsky 1999, Saszik 2002, Naka-Rushton 1966), and the spec files.

### What exists today (verified)
- **`SkillSpec`** (`app/backend/skills/contract.py`) — fields `id/version/title/engine/omics/
  entrypoint/inputs/param_spec/outputs`, plus the additive presentation/provenance fields `origin`
  (default `"commodity"`), `omics_type` (default `["transcriptomics"]`), and `catalog` (optional dict
  for Store display: name/summary/category/tier/status/license/input_formats/chains_with/popularity).
  The additive-field-with-default pattern is exactly how a new `references` field should land (zero
  runner change, existing skills omit it).
- **`registry.to_catalog_entry(spec)`** (`skills/registry.py`) maps a `SkillSpec` → the FE catalog
  entry shape (`app/frontend/lib/catalog/types.ts`), already lifting `origin`/`proprietary`/`omicsType`
  /`summary`/`license`. This is the one place to also emit `references` + `background`.
- **FE catalog** — `app/frontend/lib/catalog/types.ts` (the `SkillCatalogEntry` shape) + the Store
  detail/cards consume it. The `tier`/`license`/`origin` chips already render; the references section
  slots beside them.
- **lit-synthesizer** (`docs` + [[selom-lit-synthesizer]]) — `methods.build_body`, PubMed/bioRxiv
  `/citations/*`, and per-paper Methods. A reference entry's shape should be compatible with what the
  citation lookup already returns so the two can share a formatter and (later) auto-populate.

## Requirements
- **R1 — schema.** `SkillSpec` gains two additive, optional fields:
  - `background: str = ""` — 1–3 sentences of plain-language "what this skill is and where it comes
    from" (the human paragraph).
  - `references: list[dict] = []` — each entry: `{ "type": publication|repo|standard|dataset|method|
    tool, "title": str, "authors"?: str, "year"?: int, "doi"?: str, "url"?: str, "note"?: str }`.
    `title` + `type` required; everything else optional. Order = display order (primary basis first).
- **R2 — serialization.** `to_catalog_entry` emits `background` + `references` (verbatim, validated
  shapes) onto the catalog entry; absent → omitted/empty (no FE change needed for skills without
  them).
- **R3 — FE surface.** The Store **detail** view (and the install/confirm screen) renders a **"Skill
  Information"** section: the `background` paragraph + a references list grouped/labelled by `type`,
  each a linked citation (DOI→`https://doi.org/…`, else `url`), beside the existing origin/license/
  tier chips → the provenance card. A skill with no references shows no section (graceful).
- **R4 — validation.** A lightweight check (extend the skill-contract test) asserts every
  `references[*]` has a `type` in the allowed set + a non-empty `title`, and that `doi`/`url` look
  well-formed when present. Invalid entries fail the test, not the runtime (the runtime tolerates and
  skips a malformed entry).
- **R5 — seed/backfill.** Backfill `references` + `background` for a first wave of skills whose basis
  is unambiguous, as the worked examples (not all skills at once):
  - ERG family (`erg_traces`/`erg_bwave_bar`/`erg_intensity_response`/`erg_flicker`): ISCEV full-field
    ERG Standard 2022; Naka-Rushton 1966; Bush 2019 / Lyubarsky 1999 / Saszik 2002 (mouse cone/rod
    timing); the iWorx LabScribe + Diagnosys Espion format basis.
  - `gsea`: gseapy (BSD, GitHub) + Subramanian 2005 (GSEA); `melody` (integration): Korsunsky 2019
    Harmony (clean-room, paper-derived — note origin proprietary); `cepo`: the Cepo paper.
  - A handful more with obvious bases (edgeR-derived DE, STRING for `string_network`, GO for the
    enrichment skills) as the pattern is proven.

## Design
### Backend
- Add `background: str = ""` and `references: list[dict] = []` to `SkillSpec` (additive, defaulted).
- `to_catalog_entry`: include `"background": spec.background` and `"references": spec.references` when
  non-empty.
- Optional helper `skills/references.py::validate_reference(entry) -> bool` reused by the contract
  test and (defensively) by serialization.
- Backfill the R5 skills' `skill.json` with `background` + `references` arrays.

### Frontend
- Extend `SkillCatalogEntry` (`lib/catalog/types.ts`) with `background?: string` +
  `references?: SkillReference[]` (`{type,title,authors?,year?,doi?,url?,note?}`).
- A `SkillInfo`/`ReferenceList` component renders the section in the Store detail + install screen;
  reuse the existing chip/typography vocabulary (and, where present, the confidence/tint chip).
- A reference link resolves `doi` → `https://doi.org/<doi>` else `url`; `type` shown as a small label
  (Publication · Repository · Standard · Dataset · Method · Tool).

### Reference entry shape (shared with citations, future-proof)
Keep the entry shape a **subset/superset of** what `/citations/*` returns so a later "auto-populate
references from the methods/citation lookup" is a mapping, not a redesign. `note` carries the
"why it's here" (e.g. "clean-room reimplementation — algorithm from the paper, no GPL code").

## Decisions
- **D1 — top-level `references`/`background`, not nested under `catalog`.** Alternative: put them in
  `catalog`. Chosen top-level: they are *provenance* (peer to `origin`/`license`), not just Store
  cosmetics, and several non-Store consumers (methods text, the provenance card, future export) want
  them. Reversible: yes (the FE reads them from the catalog entry either way).
- **D2 — structured list, not a free-text blob.** Alternative: one markdown string. Chosen structured
  so links render, types group, and the citation lookup can populate/validate it. The free-text need
  is met by `background`. Reversible: yes.
- **D3 — manual backfill now; auto-populate later.** Alternative: wire the PubMed/DOI lookup to fill
  references at build time now. Chosen manual-first: the bases are known and small, and the entry
  shape is citation-compatible so auto-population is an additive follow-up. Reversible: yes.
- **D4 — `type` enum fixed at `publication|repo|standard|dataset|method|tool`.** Covers the observed
  bases (papers, GitHub repos, ISCEV/community standards, validation datasets/accessions, named
  methods like Naka-Rushton, and tools/libraries). Assumption: this set is sufficient; extendable.

## Invariants
- A skill with no `background`/`references` serializes and renders exactly as today (additive,
  defaulted) — the Store is unaffected for un-backfilled skills.
- `GET /skills` shape stays backward-compatible (new optional keys only).

## Error Behavior
- A malformed reference entry (missing `title`/`type`) is skipped in serialization and flagged by the
  contract test (build-time), never a runtime error.
- A reference with neither `doi` nor `url` renders as plain text (no dead link).

## Testing Strategy
- Backend: `SkillSpec` accepts the new fields; `to_catalog_entry` round-trips them; the contract test
  validates every backfilled `references` entry; a skill without them is unchanged.
- FE (vitest): the SkillInfo section renders a backfilled skill's references with resolved links and
  hides for a skill without references.
- Manual: open the Store detail for `erg_traces` and `gsea` → the provenance card shows background +
  linked references beside origin/license.

## Out of Scope
- Auto-fetching/refreshing citation metadata from PubMed/CrossRef at build time (future; the entry
  shape is designed for it).
- An in-app references **editor** (references are authored in `skill.json` for now).
- Backfilling *every* skill in one pass — R5 seeds the pattern with the unambiguous bases; the rest
  follow incrementally.
- A formal "cite this skill" BibTeX/RIS export (natural follow-up once references are structured).
