# `skills/proprietary/` — Selom's branded skill namespace

Genuinely-original Selom IP lives here. The skill loader (`skills/contract.py`)
scans this folder **alongside** the flat `skills/<id>/` dirs, so a skill placed at
`skills/proprietary/<id>/skill.json` is registered and runnable exactly like any
other — same `skill.json` + `run.py` contract, same `GET /skills` catalog entry.

This namespace realizes the **open-core boundary** (DECISIONS #8: trade-secret +
copyright; the moat = curation / UX / verified-reproducibility) and #10 (the
editable-figure last-mile bet). It is the physical home for *new* proprietary skills;
existing proprietary skills that already shipped flat stay in place to preserve their
import entrypoints and golden images, and are marked instead by the `origin` flag.

## The `origin` flag is the source of truth

Folder location is a convenience; the authoritative marker is the **`origin`** field
in `skill.json` (top-level, `skills/contract.py::SkillSpec`):

```jsonc
{
  "id": "cepo",
  "origin": "proprietary",          // "proprietary" | "commodity" (default)
  "entrypoint": "skills.proprietary.cepo.run:run",
  "catalog": { "name": "Selom Cepo", ... }   // branded display name
}
```

- `origin: "proprietary"` — novel or clean-room-reimplemented algorithms, and the
  editable graph-figure skills that turn public-API data into editable Plotly figures.
- `origin: "commodity"` (default) — a thin wrapper over a public library; the value is
  the editable output + provenance, not the algorithm.

`GET /skills` surfaces both `origin` and a derived `proprietary: true|false` so the
Skill Store can badge proprietary skills and the future open-core release split can
filter by it. `catalog.name` carries the branded display name (falls back to `title`).

## What belongs here vs. what doesn't

See **`docs/proprietary-skills.md`** for the honest unique-vs-commodity classification
(and why the biggest moat — the cross-cutting reproducibility / editable-figure layer —
is not a "skill" at all). Don't over-brand commodity wrappers.

## Members

Resolved by the loader at runtime; current residents:

- `cepo` — Cepo differential-stability cell-type markers (clean-room Python reimpl; no
  Python port exists upstream). Validated against the Hani `mmc2` boolean oracle.
