# Selom docs index

Map of `docs/`. Each entry is bucketed: **spec** (live design), **record** (completed
work / study / findings), **parked** (on-hold). Keep this current when adding docs (see
the docs convention in `docs/repo-structure/plan.md` §1.3).

## Live specs & references

| Path | Bucket | What |
|---|---|---|
| `repo-structure/plan.md` | spec | Repo structure conventions + cleanup/refactor plan |
| `aws-materialization/` | spec | Active deploy work — plan, spec, integrations, 7c FE-state migration |
| `pillars/plan.md` | spec | Master engine-spine map (P1–P5) — the current backlog |
| `restructure/plan.md` | spec | **Architecture-audit tracker (2026-07-02)** — live task board (WS1–WS6) for the Product-A-first arch/process hardening; points into pillars + the followups |
| `architecture-consistency-gate/` | spec | Review gate — bespoke panes on one consistent spine |
| `engine-spine/spec.md` | spec | Shared engine spine |
| `reproduction-engine/` | spec | Repro SOP, spec, schemas, skill-table-contract (living reference) |
| `figure-editor-contract/spec.md` | spec | Figure-editor contract |
| `figure-data-capabilities/` | spec | Capability-gated figure-data window |
| `ai-chat-context/spec.md` · `ai-skills-safe-slice/spec.md` | spec | Ask-Selom + AI-skills slice |
| `ai-helpers/spec.md` | spec | AI Helpers end-to-end — Probabilistic Shell / Action Gateway over the engine spine |
| `ai-helpers/s5-frontend-spec.md` | spec | S5 FE build blueprint — ✨ attribution marker (fuchsia), pending-changes author counter, AI panel (Activity\|Gaps) |
| `operating/playbook.md` | spec | The Selom Playbook — operating system: dispatch table, named pipelines, review-gauntlet |
| `p1-ingest-engine-hooks/spec.md` | spec | Deferred (post-S5): column-override + cleaning-step-toggle engine hooks — flip the S3 map_columns/apply_cleaning_step gaps to wired |
| `real-datasets.md` · `proprietary-skills.md` · `build-charter.md` | spec | Living references |

## Records (completed — under `docs/records/`)

| Path | What |
|---|---|
| `records/reproduction-dogfood/` | Dogfood phase (CLOSED s55) |
| `records/rpgrip1-figrepro.md` · `records/dorgau-figrepro/` · `records/erg-module/findings-2026-06-23.md` | Figure-repro records |
| `records/lit-synthesizer-scope.md` · `records/skill-keyword-index/` · `records/table-synthesis/spec.md` | Shipped-feature scopes |
| `records/selom-integrate/` · `records/harmony-reimplementation-scope.md` · `records/harmony2-scope/` | Melody (shipped) — consolidation candidate |
| `records/osca-sc-workflow-study.md` · `records/external-tools-study.md` · `records/external-integrations.md` · `records/skill-audit/` · `records/competitors/` | Studies & audits (OmicVerse/sklearn/R-oracle porting research) |
| `records/erg-manual-marks/` · `records/diagnosys-erg/` · `records/erg-module/spec.md` · `records/gene-set-builder-design.md` | Feature specs (shipped) |
| `records/stack-and-graphing-notes.md` · `records/skill-gaps.md` · `records/hani-skill-gap-roadmap.md` · `records/p1-skills-scope.md` | Notes / scoping |

## Parked (on-hold)

| Path | What |
|---|---|
| `on-hold/README.md` | P6 parking-lot registry (the index for parked work) |
| `command-center/design.md` | C/B platform — parked, largely superseded by `pillars/plan.md` |
| `journal-styles/` · `extract-reproduction-bridge/` · `workspace-library/` | Parked specs |

## Buckets are physical

The **record** rows above now live under `docs/records/` (physical move done 2026-06-29 —
~78 inbound code-comment/docstring path pointers rewritten across both lanes). New completed
work goes under `docs/records/`; live design under `docs/<feature>/`; on-hold under
`docs/on-hold/` (or a `parked` row here). Keep this index current — it is the map.

`records/external-integrations.md` (OmicVerse / scikit-learn / R-oracle porting research) is
the old "External Integrations" doc, renamed 2026-06-29 to stop colliding with
`aws-materialization/integrations.md` (the GitHub↔AWS↔Vercel backbone).
