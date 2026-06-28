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
| `architecture-consistency-gate/` | spec | Review gate — bespoke panes on one consistent spine |
| `engine-spine/spec.md` | spec | Shared engine spine |
| `reproduction-engine/` | spec | Repro SOP, spec, schemas, skill-table-contract (living reference) |
| `figure-editor-contract/spec.md` | spec | Figure-editor contract |
| `figure-data-capabilities/` | spec | Capability-gated figure-data window |
| `ai-chat-context/spec.md` · `ai-skills-safe-slice/spec.md` | spec | Ask-Selom + AI-skills slice |
| `real-datasets.md` · `proprietary-skills.md` · `build-charter.md` | spec | Living references |

## Records (completed — archive candidates)

| Path | What |
|---|---|
| `reproduction-dogfood/` | Dogfood phase (CLOSED s55) |
| `rpgrip1-figrepro.md` · `dorgau-figrepro/` · `erg-module/findings-2026-06-23.md` | Figure-repro records |
| `lit-synthesizer-scope.md` · `skill-keyword-index/` · `table-synthesis/spec.md` | Shipped-feature scopes |
| `selom-integrate/` · `harmony-reimplementation-scope.md` · `harmony2-scope/` | Melody (shipped) — consolidation candidate |
| `osca-sc-workflow-study.md` · `external-tools-study.md` · `external-integrations.md` · `skill-audit/` · `competitors/` | Studies & audits (OmicVerse/sklearn/R-oracle porting research) |
| `erg-manual-marks/` · `diagnosys-erg/` · `erg-module/spec.md` · `gene-set-builder-design.md` | Feature specs (shipped) |
| `stack-and-graphing-notes.md` · `skill-gaps.md` · `hani-skill-gap-roadmap.md` · `p1-skills-scope.md` | Notes / scoping |

## Parked (on-hold)

| Path | What |
|---|---|
| `on-hold/README.md` | P6 parking-lot registry (the index for parked work) |
| `command-center/design.md` | C/B platform — parked, largely superseded by `pillars/plan.md` |
| `journal-styles/` · `extract-reproduction-bridge/` · `workspace-library/` | Parked specs |

## Buckets are logical (the physical `docs/records/` move is a deferred task)

The **record** rows above are not *yet* moved into a `docs/records/` tree — that physical
move is **deferred to its own focused session** (it touches ~80 inbound code-comment/docstring
path pointers across both lanes, heavily in the active ERG + skill-keyword-index clusters; see
`repo-structure/plan.md` §2C). Until then, this index *is* the bucketing (spec / record /
parked) — keep it current.

`external-integrations.md` (OmicVerse / scikit-learn / R-oracle porting research) is the old
"External Integrations" doc, renamed 2026-06-29 to stop colliding with
`aws-materialization/integrations.md` (the GitHub↔AWS↔Vercel backbone).
